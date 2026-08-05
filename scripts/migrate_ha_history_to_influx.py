#!/usr/bin/env python3
"""Migrate Home Assistant SQLite history to InfluxDB 1.x.

Reads ``states`` + ``states_meta`` + ``state_attributes`` and writes points
using the same mapping as the Home Assistant InfluxDB integration (API 1.x),
matching the Triesdorf live YAML filter/format:

- measurement = ``unit_of_measurement`` else ``state`` (default_measurement)
- tags: ``domain``, ``entity_id`` (object id only), ``source=HA``,
  optional ``friendly_name`` (tags_attributes)
- fields: numeric → ``value`` (+ ``state`` when coerced via state_as_number);
  otherwise ``state``; remaining attributes as fields (``*_str`` when not float)
- ignore_attributes: icon, friendly_name, supported_features, attribution
- exclude domains: persistent_notification, update
- timestamp precision: nanoseconds

Password is read only from an environment variable (``--password-env``).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import math
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Sequence

LOG = logging.getLogger("migrate_ha_history_to_influx")

# Defaults aligned with Triesdorf live InfluxDB YAML config.
DEFAULT_MEASUREMENT = "state"
DEFAULT_BATCH_SIZE = 1000
DEFAULT_EXCLUDE_DOMAINS = ("persistent_notification", "update")
DEFAULT_TAGS: dict[str, str] = {"source": "HA"}
DEFAULT_TAGS_ATTRIBUTES = ("friendly_name",)
DEFAULT_IGNORE_ATTRIBUTES = (
    "icon",
    "friendly_name",
    "supported_features",
    "attribution",
)
SKIP_STATES = frozenset({"unknown", "unavailable", ""})

# From homeassistant/components/influxdb/const.py
RE_DIGIT_TAIL = re.compile(r"^[^\.]*\d+\.?\d+[^\.]*$")
RE_DECIMAL = re.compile(r"[^\d.]+")

# From homeassistant.helpers.state.state_as_number
STATE_AS_NUMBER_ONE = frozenset(
    {"on", "locked", "above_horizon", "open", "home"}
)
STATE_AS_NUMBER_ZERO = frozenset(
    {"off", "unlocked", "unknown", "below_horizon", "closed", "not_home"}
)

@dataclass(frozen=True)
class MigrateConfig:
    """Runtime mapping options mirroring HA InfluxDB YAML."""

    default_measurement: str = DEFAULT_MEASUREMENT
    tags: Mapping[str, str] = field(default_factory=lambda: dict(DEFAULT_TAGS))
    tags_attributes: Sequence[str] = DEFAULT_TAGS_ATTRIBUTES
    ignore_attributes: Sequence[str] = DEFAULT_IGNORE_ATTRIBUTES
    exclude_domains: Sequence[str] = DEFAULT_EXCLUDE_DOMAINS


@dataclass(frozen=True)
class ResumeOffset:
    """Exclusive resume cursor after ``(metadata_id, last_updated_ts, state_id)``.

    Prefer the 3-part form so rows that share the same timestamp are not skipped.
    Two-part ``METADATA_ID:TS`` is accepted for compatibility and treats
    ``state_id`` as 0 (may rewrite same-ts rows; safe due to Influx merge).
    """

    metadata_id: int
    last_updated_ts: float
    state_id: int = 0

    @classmethod
    def parse(cls, value: str) -> ResumeOffset:
        """Parse ``METADATA_ID:LAST_UPDATED_TS[:STATE_ID]``."""
        try:
            parts = value.split(":")
            if len(parts) == 2:
                return cls(int(parts[0]), float(parts[1]), 0)
            if len(parts) == 3:
                return cls(int(parts[0]), float(parts[1]), int(parts[2]))
            raise ValueError("wrong number of parts")
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "expected METADATA_ID:LAST_UPDATED_TS[:STATE_ID], "
                f"e.g. 42:1712345678.123:1001 (got {value!r})"
            ) from exc

    def __str__(self) -> str:
        # Use repr(ts) for a stable float round-trip in shell/logs.
        return f"{self.metadata_id}:{self.last_updated_ts!r}:{self.state_id}"

    @classmethod
    def from_point(cls, point: Point) -> ResumeOffset:
        return cls(point.metadata_id, point.last_updated_ts, point.state_id)


@dataclass
class Point:
    """One InfluxDB point prior to Line Protocol encoding."""

    measurement: str
    tags: dict[str, str]
    fields: dict[str, Any]
    time_ns: int
    metadata_id: int
    last_updated_ts: float
    entity_id: str
    state_id: int = 0


@dataclass
class Stats:
    """Migration counters."""

    scanned: int = 0
    written: int = 0
    skipped_domain: int = 0
    skipped_state: int = 0
    skipped_empty: int = 0
    skipped_bad_ts: int = 0
    skipped_bad_entity: int = 0
    skipped_bad_attrs: int = 0
    batches: int = 0
    http_errors: int = 0


def state_as_number(state: str) -> float:
    """Mirror ``homeassistant.helpers.state.state_as_number`` (string-only)."""
    if state in STATE_AS_NUMBER_ONE:
        return 1.0
    if state in STATE_AS_NUMBER_ZERO:
        return 0.0
    return float(state)


def split_entity_id(entity_id: str) -> tuple[str, str]:
    """Return ``(domain, object_id)``; raises ValueError if invalid."""
    if not entity_id or "." not in entity_id:
        raise ValueError(f"invalid entity_id: {entity_id!r}")
    domain, object_id = entity_id.split(".", 1)
    if not domain or not object_id:
        raise ValueError(f"invalid entity_id: {entity_id!r}")
    return domain, object_id


def ts_to_ns(ts: float) -> int:
    """Convert Unix timestamp (seconds, float) to nanoseconds."""
    return int(round(float(ts) * 1_000_000_000))


def parse_attributes(raw: str | None) -> dict[str, Any]:
    """Parse ``shared_attrs`` JSON; empty/invalid → {}."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def map_state_to_point(
    *,
    entity_id: str,
    state: str | None,
    attributes: Mapping[str, Any],
    last_updated_ts: float,
    metadata_id: int,
    config: MigrateConfig,
    state_id: int = 0,
) -> Point | None:
    """Map one HA state row to an Influx point (HA integration semantics).

    Returns ``None`` when the live integration would skip the event
    (unknown/unavailable/empty) or when the domain is excluded.
    """
    if state is None or state in SKIP_STATES:
        return None

    try:
        domain, object_id = split_entity_id(entity_id)
    except ValueError:
        return None

    if domain in config.exclude_domains:
        return None

    include_state = False
    include_value = False
    state_as_value: float | None = None

    try:
        state_as_value = float(state)
        include_value = True
    except (TypeError, ValueError):
        try:
            state_as_value = state_as_number(state)
            include_state = True
            include_value = True
        except (TypeError, ValueError):
            include_state = True

    # measurement_attr = unit_of_measurement (HA default)
    include_uom = True
    uom = attributes.get("unit_of_measurement")
    if uom in (None, ""):
        measurement = config.default_measurement
    else:
        measurement = str(uom)
        include_uom = False

    tags: dict[str, str] = {
        "domain": domain,
        "entity_id": object_id,
    }
    for key in config.tags_attributes:
        # HA copies tag attribute values as-is; Influx clients stringify them.
        if key in attributes:
            tags[key] = str(attributes[key])
    for key, value in config.tags.items():
        tags[key] = str(value)

    fields: dict[str, Any] = {}
    if include_state:
        fields["state"] = state
    if include_value and state_as_value is not None:
        fields["value"] = float(state_as_value)

    ignore = set(config.ignore_attributes)
    tags_attr_set = set(config.tags_attributes)

    for key, value in attributes.items():
        if key in tags_attr_set:
            continue
        if key == "unit_of_measurement" and not include_uom:
            continue
        if key in ignore:
            continue

        field_key = key
        if field_key in fields:
            field_key = f"{field_key}_"

        try:
            fields[field_key] = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            new_key = f"{field_key}_str"
            new_value = str(value)
            fields[new_key] = new_value
            if RE_DIGIT_TAIL.match(new_value):
                try:
                    fields[field_key] = float(RE_DECIMAL.sub("", new_value))
                except ValueError:
                    pass

        # Infinity / NaN are not valid InfluxDB floats (HA attribute path).
        if field_key in fields:
            numeric = fields[field_key]
            if isinstance(numeric, float) and not math.isfinite(numeric):
                del fields[field_key]

    # Also drop non-finite numeric state ``value`` (HA leaves it, but Influx
    # rejects the whole batch — skip the bad field for robust migration).
    value_field = fields.get("value")
    if isinstance(value_field, float) and not math.isfinite(value_field):
        del fields["value"]

    if not fields:
        return None

    try:
        time_ns = ts_to_ns(last_updated_ts)
    except (TypeError, ValueError):
        return None

    return Point(
        measurement=str(measurement),
        tags=tags,
        fields=fields,
        time_ns=time_ns,
        metadata_id=metadata_id,
        last_updated_ts=float(last_updated_ts),
        entity_id=entity_id,
        state_id=state_id,
    )


def _escape_measurement_tag_key_value(value: str) -> str:
    """Escape Line Protocol measurement / tag key / tag value / field key."""
    # Backslash must be escaped first.
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("=", "\\=")
        .replace(" ", "\\ ")
    )


def _format_field_value(value: Any) -> str:
    if isinstance(value, bool):
        # bool is a subclass of int; HA float() path rarely leaves bools,
        # but keep Line Protocol correct if present.
        return "t" if value else "f"
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value}i"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float")
        # Influx accepts float literals; repr keeps full precision safely.
        return repr(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def point_to_line_protocol(point: Point) -> str:
    """Encode a point as InfluxDB Line Protocol (precision=ns)."""
    measurement = _escape_measurement_tag_key_value(point.measurement)
    # Stable tag order helps readability; Influx series key is order-insensitive.
    tag_parts = [
        f"{_escape_measurement_tag_key_value(k)}="
        f"{_escape_measurement_tag_key_value(v)}"
        for k, v in sorted(point.tags.items())
    ]
    field_parts = [
        f"{_escape_measurement_tag_key_value(k)}={_format_field_value(v)}"
        for k, v in sorted(point.fields.items())
    ]
    if not field_parts:
        raise ValueError("point has no fields")
    head = measurement
    if tag_parts:
        head = f"{measurement},{','.join(tag_parts)}"
    return f"{head} {','.join(field_parts)} {point.time_ns}"


class InfluxWriter:
    """Minimal InfluxDB 1.x HTTP writer (Line Protocol, Basic Auth)."""

    def __init__(
        self,
        url: str,
        database: str,
        username: str,
        password: str,
        *,
        timeout: float = 60.0,
    ) -> None:
        base = url.rstrip("/")
        db_q = urllib.parse.quote(database, safe="")
        self.write_url = f"{base}/write?db={db_q}&precision=ns"
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._auth_header = f"Basic {token}"
        self.timeout = timeout
        self._opener = urllib.request.build_opener()

    def write_lines(self, lines: Sequence[str]) -> None:
        """POST a batch of Line Protocol lines. Raises on HTTP/auth errors."""
        if not lines:
            return
        body = ("\n".join(lines) + "\n").encode("utf-8")
        request = urllib.request.Request(
            self.write_url,
            data=body,
            method="POST",
            headers={
                "Authorization": self._auth_header,
                "Content-Type": "application/octet-stream",
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                # 204 No Content is success for /write
                if response.status not in (204, 200):
                    payload = response.read().decode("utf-8", errors="replace")
                    raise RuntimeError(
                        f"InfluxDB write unexpected status "
                        f"{response.status}: {payload}"
                    )
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            if exc.code in (401, 403):
                raise RuntimeError(
                    "InfluxDB authentication/authorization failed "
                    f"(HTTP {exc.code}). Check username and --password-env."
                ) from exc
            raise RuntimeError(
                f"InfluxDB write failed (HTTP {exc.code}): {payload}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"InfluxDB connection failed: {exc.reason}"
            ) from exc


def open_db(path: str) -> sqlite3.Connection:
    """Open HA recorder DB read-only."""
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def iter_state_rows(
    conn: sqlite3.Connection,
    resume: ResumeOffset | None,
) -> Iterator[sqlite3.Row]:
    """Yield states joined with meta + attributes, ordered for resume."""
    sql = """
        SELECT
            s.state_id AS state_id,
            s.metadata_id AS metadata_id,
            s.state AS state,
            s.last_updated_ts AS last_updated_ts,
            s.attributes_id AS attributes_id,
            sm.entity_id AS entity_id,
            sa.shared_attrs AS shared_attrs
        FROM states AS s
        JOIN states_meta AS sm ON sm.metadata_id = s.metadata_id
        LEFT JOIN state_attributes AS sa ON sa.attributes_id = s.attributes_id
        WHERE s.metadata_id IS NOT NULL
          AND s.last_updated_ts IS NOT NULL
    """
    params: list[Any] = []
    if resume is not None:
        # Exclusive cursor on the full sort key (metadata_id, ts, state_id).
        sql += """
          AND (
                s.metadata_id > ?
             OR (s.metadata_id = ? AND s.last_updated_ts > ?)
             OR (
                    s.metadata_id = ?
                AND s.last_updated_ts = ?
                AND s.state_id > ?
             )
          )
        """
        params.extend(
            [
                resume.metadata_id,
                resume.metadata_id,
                resume.last_updated_ts,
                resume.metadata_id,
                resume.last_updated_ts,
                resume.state_id,
            ]
        )
    sql += """
        ORDER BY s.metadata_id ASC, s.last_updated_ts ASC, s.state_id ASC
    """
    cursor = conn.execute(sql, params)
    while True:
        rows = cursor.fetchmany(5000)
        if not rows:
            break
        yield from rows


def row_to_point(
    row: sqlite3.Row,
    config: MigrateConfig,
    attr_cache: dict[int | None, dict[str, Any] | None],
    stats: Stats,
) -> Point | None:
    """Convert a SQL row to a Point; update skip stats."""
    stats.scanned += 1
    entity_id = row["entity_id"]
    if not entity_id or "." not in entity_id:
        stats.skipped_bad_entity += 1
        return None

    domain = entity_id.split(".", 1)[0]
    if domain in config.exclude_domains:
        stats.skipped_domain += 1
        return None

    state = row["state"]
    if state is None or state in SKIP_STATES:
        stats.skipped_state += 1
        return None

    ts = row["last_updated_ts"]
    if ts is None:
        stats.skipped_bad_ts += 1
        return None

    attributes_id = row["attributes_id"]
    raw_attrs = row["shared_attrs"]
    if attributes_id not in attr_cache:
        if raw_attrs:
            try:
                parsed = json.loads(raw_attrs)
            except (TypeError, json.JSONDecodeError):
                stats.skipped_bad_attrs += 1
                attr_cache[attributes_id] = None
            else:
                if not isinstance(parsed, dict):
                    stats.skipped_bad_attrs += 1
                    attr_cache[attributes_id] = None
                else:
                    attr_cache[attributes_id] = parsed
        else:
            attr_cache[attributes_id] = {}

    attributes = attr_cache[attributes_id]
    if attributes is None:
        # Corrupt shared_attrs would yield the wrong measurement/fields.
        return None

    point = map_state_to_point(
        entity_id=entity_id,
        state=state,
        attributes=attributes,
        last_updated_ts=float(ts),
        metadata_id=int(row["metadata_id"]),
        config=config,
        state_id=int(row["state_id"]),
    )
    if point is None:
        stats.skipped_empty += 1
    return point


def format_point_preview(point: Point) -> str:
    """Human-readable mapping preview for dry-run / samples."""
    return (
        f"{point.entity_id} meta={point.metadata_id} "
        f"ts={point.last_updated_ts} → "
        f"measurement={point.measurement!r} "
        f"tags={point.tags} fields={point.fields} "
        f"time_ns={point.time_ns}\n"
        f"  LP: {point_to_line_protocol(point)}"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI definition."""
    parser = argparse.ArgumentParser(
        description=(
            "Migrate Home Assistant SQLite history to InfluxDB 1.x "
            "using the HA InfluxDB integration schema."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to Home Assistant recorder SQLite DB (consistent backup)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help=(
            "InfluxDB base URL, e.g. http://100.67.226.35:8086 "
            "(required unless --dry-run)"
        ),
    )
    parser.add_argument(
        "--database",
        default="homeassistant",
        help="InfluxDB database name",
    )
    parser.add_argument(
        "--username",
        default="homeassistant",
        help="InfluxDB username (Basic Auth)",
    )
    parser.add_argument(
        "--password-env",
        default=None,
        help=(
            "Name of environment variable holding the InfluxDB password "
            "(required unless --dry-run)"
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of Line Protocol points per HTTP write",
    )
    parser.add_argument(
        "--resume-from",
        type=ResumeOffset.parse,
        default=None,
        metavar="METADATA_ID:TS[:STATE_ID]",
        help="Resume after this exclusive offset (prefer 3-part with state_id)",
    )
    parser.add_argument(
        "--resume-metadata-id",
        type=int,
        default=None,
        help="Resume metadata_id (use with --resume-ts)",
    )
    parser.add_argument(
        "--resume-ts",
        type=float,
        default=None,
        help="Resume last_updated_ts (use with --resume-metadata-id)",
    )
    parser.add_argument(
        "--exclude-domain",
        action="append",
        dest="exclude_domains",
        default=None,
        help=(
            "Domain to exclude (repeatable). "
            f"Default: {', '.join(DEFAULT_EXCLUDE_DOMAINS)}"
        ),
    )
    parser.add_argument(
        "--default-measurement",
        default=DEFAULT_MEASUREMENT,
        help="Measurement when unit_of_measurement is missing",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Map and count only; print sample points; do not write",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="Number of mapped sample points to print (dry-run / progress)",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Log progress periodically",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10000,
        help="Log progress every N scanned rows when --progress is set",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser


def resolve_resume(args: argparse.Namespace) -> ResumeOffset | None:
    """Resolve resume flags into a single offset."""
    if args.resume_from is not None:
        if args.resume_metadata_id is not None or args.resume_ts is not None:
            raise SystemExit(
                "Use either --resume-from or --resume-metadata-id/--resume-ts, "
                "not both."
            )
        return args.resume_from
    if args.resume_metadata_id is not None or args.resume_ts is not None:
        if args.resume_metadata_id is None or args.resume_ts is None:
            raise SystemExit(
                "--resume-metadata-id and --resume-ts must be provided together."
            )
        return ResumeOffset(args.resume_metadata_id, args.resume_ts)
    return None


def get_password(env_name: str) -> str:
    """Read password from env; never log the value."""
    value = os.environ.get(env_name)
    if value is None or value == "":
        raise SystemExit(
            f"Environment variable {env_name!r} is unset or empty. "
            f"Export it before running (password is never read from CLI)."
        )
    return value


def run(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.batch_size < 1:
        raise SystemExit("--batch-size must be >= 1")

    if not os.path.isfile(args.db):
        raise SystemExit(f"DB not found: {args.db}")

    if not args.dry_run and not args.url:
        raise SystemExit("--url is required unless --dry-run")

    resume = resolve_resume(args)
    exclude = (
        tuple(args.exclude_domains)
        if args.exclude_domains is not None
        else DEFAULT_EXCLUDE_DOMAINS
    )
    config = MigrateConfig(
        default_measurement=args.default_measurement,
        tags=dict(DEFAULT_TAGS),
        tags_attributes=DEFAULT_TAGS_ATTRIBUTES,
        ignore_attributes=DEFAULT_IGNORE_ATTRIBUTES,
        exclude_domains=exclude,
    )

    writer: InfluxWriter | None = None
    if not args.dry_run:
        if not args.password_env:
            raise SystemExit("--password-env is required unless --dry-run")
        password = get_password(args.password_env)
        writer = InfluxWriter(
            args.url,
            args.database,
            args.username,
            password,
        )
        LOG.info(
            "Writing to %s database=%s user=%s (password from env %s)",
            args.url,
            args.database,
            args.username,
            args.password_env,
        )

    LOG.info(
        "Reading %s (resume=%s, exclude_domains=%s, dry_run=%s)",
        args.db,
        resume,
        ",".join(exclude),
        args.dry_run,
    )

    stats = Stats()
    attr_cache: dict[int | None, dict[str, Any] | None] = {}
    batch_points: list[Point] = []
    samples: list[Point] = []
    last_flushed_offset: ResumeOffset | None = None
    started = time.monotonic()

    def flush() -> None:
        nonlocal batch_points, last_flushed_offset
        if not batch_points:
            return
        lines = [point_to_line_protocol(p) for p in batch_points]
        if writer is not None:
            try:
                writer.write_lines(lines)
            except RuntimeError:
                stats.http_errors += 1
                if last_flushed_offset is not None:
                    LOG.error(
                        "Write failed; resume with --resume-from %s",
                        last_flushed_offset,
                    )
                else:
                    LOG.error(
                        "Write failed before any successful batch; "
                        "re-run without --resume-from"
                    )
                raise
        stats.batches += 1
        stats.written += len(batch_points)
        last_flushed_offset = ResumeOffset.from_point(batch_points[-1])
        batch_points = []

    try:
        with open_db(args.db) as conn:
            for row in iter_state_rows(conn, resume):
                point = row_to_point(row, config, attr_cache, stats)
                if point is None:
                    continue
                if len(samples) < args.sample:
                    samples.append(point)
                batch_points.append(point)
                if len(batch_points) >= args.batch_size:
                    flush()

                if args.progress and stats.scanned % args.progress_every == 0:
                    elapsed = time.monotonic() - started
                    rate = stats.scanned / elapsed if elapsed else 0.0
                    LOG.info(
                        "progress scanned=%s written=%s skipped_state=%s "
                        "skipped_domain=%s rate=%.0f rows/s "
                        "last_flushed=%s",
                        stats.scanned,
                        stats.written,
                        stats.skipped_state,
                        stats.skipped_domain,
                        rate,
                        last_flushed_offset or "-",
                    )

            if batch_points:
                flush()
    except RuntimeError as exc:
        LOG.error("%s", exc)
        return 1

    if samples:
        LOG.info("Sample mapped points (%d):", len(samples))
        for sample in samples:
            print(format_point_preview(sample), file=sys.stderr)

    elapsed = time.monotonic() - started
    LOG.info(
        "Done in %.1fs | scanned=%s written=%s batches=%s "
        "skipped_domain=%s skipped_state=%s skipped_empty=%s "
        "skipped_bad_entity=%s skipped_bad_ts=%s skipped_bad_attrs=%s "
        "http_errors=%s",
        elapsed,
        stats.scanned,
        stats.written,
        stats.batches,
        stats.skipped_domain,
        stats.skipped_state,
        stats.skipped_empty,
        stats.skipped_bad_entity,
        stats.skipped_bad_ts,
        stats.skipped_bad_attrs,
        stats.http_errors,
    )
    if last_flushed_offset is not None:
        LOG.info(
            "Last successful offset (for --resume-from): %s",
            last_flushed_offset,
        )
    return 0


def _self_check() -> None:
    """Tiny offline mapping sanity check (run via --self-check)."""
    cfg = MigrateConfig()
    p = map_state_to_point(
        entity_id="sensor.bodenfeuchte_1",
        state="42.5",
        attributes={
            "unit_of_measurement": "%",
            "friendly_name": "Bodenfeuchte 1",
            "icon": "mdi:water",
            "device_class": "moisture",
            "state_class": "measurement",
        },
        last_updated_ts=1712345678.123456789,
        metadata_id=7,
        config=cfg,
    )
    assert p is not None
    assert p.measurement == "%"
    assert p.tags["entity_id"] == "bodenfeuchte_1"
    assert p.tags["domain"] == "sensor"
    assert p.tags["source"] == "HA"
    assert p.tags["friendly_name"] == "Bodenfeuchte 1"
    assert "icon" not in p.fields
    assert "friendly_name" not in p.fields
    assert "friendly_name_str" not in p.fields
    assert "unit_of_measurement" not in p.fields
    assert p.fields["value"] == 42.5
    assert "state" not in p.fields
    line = point_to_line_protocol(p)
    assert line.startswith("%,"), line
    assert 'entity_id=bodenfeuchte_1' in line
    assert "value=42.5" in line

    p2 = map_state_to_point(
        entity_id="switch.pump",
        state="on",
        attributes={"friendly_name": "Pumpe"},
        last_updated_ts=1712345678.0,
        metadata_id=1,
        config=cfg,
        state_id=99,
    )
    assert p2 is not None
    assert p2.measurement == "state"
    assert p2.fields["value"] == 1.0
    assert p2.fields["state"] == "on"
    assert p2.state_id == 99

    assert (
        map_state_to_point(
            entity_id="update.core",
            state="on",
            attributes={},
            last_updated_ts=1.0,
            metadata_id=1,
            config=cfg,
        )
        is None
    )

    # Non-float attribute + digit-tail dual field
    p3 = map_state_to_point(
        entity_id="sensor.x",
        state="ok",
        attributes={"raw": "23.5°C", "note": "hello"},
        last_updated_ts=1.0,
        metadata_id=1,
        config=cfg,
    )
    assert p3 is not None
    assert p3.fields["state"] == "ok"
    assert p3.fields["raw_str"] == "23.5°C"
    assert p3.fields["raw"] == 23.5
    assert p3.fields["note_str"] == "hello"

    # Line protocol escapes backslash / space / comma in tags
    p4 = map_state_to_point(
        entity_id="sensor.y",
        state="1",
        attributes={
            "unit_of_measurement": "%",
            "friendly_name": r"a\b, c",
        },
        last_updated_ts=1.0,
        metadata_id=1,
        config=cfg,
    )
    assert p4 is not None
    lp4 = point_to_line_protocol(p4)
    assert r"friendly_name=a\\b\,\ c" in lp4 or r"friendly_name=a\\b\\,\ c" in lp4
    # space and comma escaped; backslash doubled
    assert "friendly_name=" in lp4
    assert r"\\b" in lp4
    assert r"\," in lp4
    assert r"\ " in lp4

    # Resume parse round-trip
    off = ResumeOffset(7, 1712345678.1234567, 1001)
    assert ResumeOffset.parse(str(off)) == off
    assert ResumeOffset.parse("7:1.5") == ResumeOffset(7, 1.5, 0)

    # inf state value dropped (would break Influx batch)
    p5 = map_state_to_point(
        entity_id="sensor.z",
        state="inf",
        attributes={"unit_of_measurement": "W"},
        last_updated_ts=1.0,
        metadata_id=1,
        config=cfg,
    )
    assert p5 is None

    print("self-check OK")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        _self_check()
        raise SystemExit(0)
    raise SystemExit(run())
