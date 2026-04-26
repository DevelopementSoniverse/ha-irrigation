"""Data models for the Irrigation Computer integration."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from .const import (
    DEFAULT_FALLBACK_END,
    DEFAULT_FALLBACK_MINUTES,
    DEFAULT_FALLBACK_START,
    DEFAULT_POWER_MAX,
    DEFAULT_POWER_MIN,
    DEFAULT_THRESHOLD_FRUIT_SET,
    DEFAULT_THRESHOLD_PLANTING,
    DEFAULT_THRESHOLD_RIPENING,
    DEFAULT_WATERING_DURATION,
    PHASE_PLANTING,
    PHASE_FRUIT_SET,
    PHASE_RIPENING,
    REASON_MANUAL,
    ZONE_FALLBACK_ENABLED,
    ZONE_FALLBACK_END,
    ZONE_FALLBACK_MINUTES,
    ZONE_FALLBACK_START,
    ZONE_ID,
    ZONE_NAME,
    ZONE_PHASE,
    ZONE_POWER_ENTITY,
    ZONE_POWER_MAX,
    ZONE_POWER_MIN,
    ZONE_RADIATION_TRIGGER_ENABLED,
    ZONE_RELAY_ENTITY,
    ZONE_THRESHOLD_FRUIT_SET,
    ZONE_THRESHOLD_PLANTING,
    ZONE_THRESHOLD_RIPENING,
    ZONE_WATERING_DURATION,
)


@dataclass
class ZoneConfig:
    """Persistent configuration for a single irrigation zone."""

    zone_id: str
    name: str
    relay_entity_id: str
    power_entity_id: str | None = None
    watering_duration_sec: int = DEFAULT_WATERING_DURATION
    phase: str = PHASE_PLANTING
    threshold_planting: float = DEFAULT_THRESHOLD_PLANTING
    threshold_fruit_set: float = DEFAULT_THRESHOLD_FRUIT_SET
    threshold_ripening: float = DEFAULT_THRESHOLD_RIPENING
    power_min: float = DEFAULT_POWER_MIN
    power_max: float = DEFAULT_POWER_MAX
    fallback_enabled: bool = True
    fallback_minutes: int = DEFAULT_FALLBACK_MINUTES
    fallback_start: str = DEFAULT_FALLBACK_START
    fallback_end: str = DEFAULT_FALLBACK_END
    radiation_trigger_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain dict for storage in config entry options."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneConfig":
        """Construct from a stored dict, applying defaults for missing keys."""
        return cls(
            zone_id=data[ZONE_ID],
            name=data.get(ZONE_NAME, "Zone"),
            relay_entity_id=data.get(ZONE_RELAY_ENTITY, ""),
            power_entity_id=data.get(ZONE_POWER_ENTITY) or None,
            watering_duration_sec=int(
                data.get(ZONE_WATERING_DURATION, DEFAULT_WATERING_DURATION)
            ),
            phase=str(data.get(ZONE_PHASE, PHASE_PLANTING)),
            threshold_planting=float(
                data.get(ZONE_THRESHOLD_PLANTING, DEFAULT_THRESHOLD_PLANTING)
            ),
            threshold_fruit_set=float(
                data.get(ZONE_THRESHOLD_FRUIT_SET, DEFAULT_THRESHOLD_FRUIT_SET)
            ),
            threshold_ripening=float(
                data.get(ZONE_THRESHOLD_RIPENING, DEFAULT_THRESHOLD_RIPENING)
            ),
            power_min=float(data.get(ZONE_POWER_MIN, DEFAULT_POWER_MIN)),
            power_max=float(data.get(ZONE_POWER_MAX, DEFAULT_POWER_MAX)),
            fallback_enabled=bool(data.get(ZONE_FALLBACK_ENABLED, True)),
            fallback_minutes=int(
                data.get(ZONE_FALLBACK_MINUTES, DEFAULT_FALLBACK_MINUTES)
            ),
            fallback_start=str(
                data.get(ZONE_FALLBACK_START, DEFAULT_FALLBACK_START)
            ),
            fallback_end=str(data.get(ZONE_FALLBACK_END, DEFAULT_FALLBACK_END)),
            radiation_trigger_enabled=bool(
                data.get(ZONE_RADIATION_TRIGGER_ENABLED, True)
            ),
        )

    def current_threshold(self) -> float:
        """Return the active radiation threshold for the current phase."""
        if self.phase == PHASE_FRUIT_SET:
            return self.threshold_fruit_set
        if self.phase == PHASE_RIPENING:
            return self.threshold_ripening
        return self.threshold_planting


@dataclass
class ZoneRuntimeState:
    """Volatile runtime state of a zone (persisted via RestoreEntity)."""

    last_run_at: datetime | None = None
    last_reason: str = REASON_MANUAL
    is_running: bool = False
    started_at: datetime | None = None
    accumulated_radiation_at_last_run: float = 0.0
    last_relay_error: str | None = None
    run_history: list[float] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_reason": self.last_reason,
            "is_running": self.is_running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "accumulated_radiation_at_last_run": (
                self.accumulated_radiation_at_last_run
            ),
            "last_relay_error": self.last_relay_error,
            "run_history": list(self.run_history),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ZoneRuntimeState":
        def _parse_dt(value: Any) -> datetime | None:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except (TypeError, ValueError):
                return None

        return cls(
            last_run_at=_parse_dt(data.get("last_run_at")),
            last_reason=str(data.get("last_reason", REASON_MANUAL)),
            is_running=bool(data.get("is_running", False)),
            started_at=_parse_dt(data.get("started_at")),
            accumulated_radiation_at_last_run=float(
                data.get("accumulated_radiation_at_last_run", 0.0)
            ),
            last_relay_error=data.get("last_relay_error"),
            run_history=[float(x) for x in data.get("run_history", []) if x],
        )
