"""Coordinator and zone runtime for the Irrigation Computer integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_PUSH_ALERT_DEVICE_IDS,
    CONF_PUSH_ALERTS_ENABLED,
    CONF_RADIATION_SOURCE_ENTITY,
    CONF_RADIATION_SOURCE_UNIT,
    DEFAULT_PUSH_ALERTS_ENABLED,
    DEFAULT_RADIATION_SOURCE_UNIT,
    DOMAIN,
    NOTIFICATION_ID_PREFIX,
    OPT_ZONES,
    POWER_WAIT_SECONDS,
    RADIATION_STALE_SECONDS,
    REASON_FALLBACK,
    REASON_MANUAL,
    REASON_MOISTURE,
    REASON_RADIATION,
    STORAGE_KEY,
    STORAGE_VERSION,
    UNIT_WH_PER_M2,
    UPDATE_INTERVAL_SECONDS,
    WATCHDOG_GRACE_SECONDS,
)
from .models import ZoneConfig, ZoneRuntimeState
from .util import mobile_app_notify_service, normalize_device_ids

_LOGGER = logging.getLogger(__name__)


class IrrigationController(DataUpdateCoordinator[dict[str, Any]]):
    """Per-config-entry controller managing all zones and the radiation accumulator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.entry = entry
        self._zones: dict[str, ZoneConfig] = {}
        self._runtime: dict[str, ZoneRuntimeState] = {}
        self._zone_locks: dict[str, asyncio.Lock] = {}
        self._zone_tasks: dict[str, asyncio.Task] = {}
        self._monitor_tasks: set[asyncio.Task] = set()
        self._active_alerts: set[str] = set()
        self._unsub_listeners: list[CALLBACK_TYPE] = []
        self._store: Store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}")

        # Radiation accumulator state (Wh/m²).
        self._radiation_total_wh: float = 0.0
        self._radiation_last_value: float | None = None
        self._radiation_last_ts: datetime | None = None
        self._radiation_source: str | None = (
            entry.data.get(CONF_RADIATION_SOURCE_ENTITY)
            or entry.options.get(CONF_RADIATION_SOURCE_ENTITY)
        )
        self._radiation_unit: str = (
            entry.options.get(CONF_RADIATION_SOURCE_UNIT)
            or entry.data.get(CONF_RADIATION_SOURCE_UNIT)
            or DEFAULT_RADIATION_SOURCE_UNIT
        )
        self._push_alerts_enabled: bool = bool(
            entry.options.get(
                CONF_PUSH_ALERTS_ENABLED,
                entry.data.get(CONF_PUSH_ALERTS_ENABLED, DEFAULT_PUSH_ALERTS_ENABLED),
            )
        )
        self._push_alert_device_ids: list[str] = normalize_device_ids(
            entry.options.get(
                CONF_PUSH_ALERT_DEVICE_IDS,
                entry.data.get(CONF_PUSH_ALERT_DEVICE_IDS, []),
            )
        )

    # ------------------------------------------------------------------ setup

    async def async_initialize(self) -> None:
        """Load persisted state, parse zones and start tracking listeners."""
        stored = await self._store.async_load() or {}
        self._radiation_total_wh = float(stored.get("radiation_total_wh", 0.0))

        zones_raw = self.entry.options.get(OPT_ZONES, [])
        for raw in zones_raw:
            zone = ZoneConfig.from_dict(raw)
            self._zones[zone.zone_id] = zone
            self._zone_locks[zone.zone_id] = asyncio.Lock()
            rt = stored.get("zones", {}).get(zone.zone_id, {})
            self._runtime[zone.zone_id] = ZoneRuntimeState.from_dict(rt)
            # If a zone was running across HA restart, defensively turn off the relay.
            if self._runtime[zone.zone_id].is_running:
                _LOGGER.warning(
                    "Zone %s appears to have been running across restart – "
                    "forcing relay off",
                    zone.name,
                )
                self._runtime[zone.zone_id].is_running = False
                self._runtime[zone.zone_id].started_at = None
                self.hass.async_create_task(self._async_force_relay_off(zone))

        if self._radiation_source:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass,
                    [self._radiation_source],
                    self._handle_radiation_change,
                )
            )
            current = self.hass.states.get(self._radiation_source)
            if current is not None:
                self._update_radiation_from_state(current)

        # Persist runtime state every 60s.
        self._unsub_listeners.append(
            async_track_time_interval(
                self.hass, self._async_persist_tick, timedelta(seconds=60)
            )
        )

        # First refresh seeds coordinator.data.
        await self.async_refresh()

    async def async_shutdown(self) -> None:
        """Cancel listeners and pending zone tasks."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        for task in list(self._zone_tasks.values()):
            task.cancel()
        for task in list(self._monitor_tasks):
            task.cancel()
        for task in list(self._zone_tasks.values()):
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        for task in list(self._monitor_tasks):
            try:
                await task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._zone_tasks.clear()
        self._monitor_tasks.clear()
        await self._async_persist()

    # ------------------------------------------------------------------ zones

    @property
    def zones(self) -> list[ZoneConfig]:
        return list(self._zones.values())

    def get_zone(self, zone_id: str) -> ZoneConfig | None:
        return self._zones.get(zone_id)

    def get_runtime(self, zone_id: str) -> ZoneRuntimeState | None:
        return self._runtime.get(zone_id)

    @property
    def radiation_source_entity(self) -> str | None:
        return self._radiation_source

    @property
    def radiation_total_wh(self) -> float:
        return self._radiation_total_wh

    @property
    def push_alerts_enabled(self) -> bool:
        return self._push_alerts_enabled

    @property
    def push_alert_device_ids(self) -> list[str]:
        return list(self._push_alert_device_ids)

    def radiation_since_last_run(self, zone_id: str) -> float:
        rt = self._runtime.get(zone_id)
        if rt is None:
            return 0.0
        return max(0.0, self._radiation_total_wh - rt.accumulated_radiation_at_last_run)

    def average_soil_moisture(self, zone_id: str) -> tuple[float | None, int]:
        """Return ``(average_percent, valid_sensor_count)`` for a zone.

        Non-numeric, missing, ``unavailable`` or ``unknown`` states are skipped.
        ``(None, 0)`` indicates that no sensor produced a usable reading.
        """
        zone = self._zones.get(zone_id)
        if zone is None or not zone.soil_moisture_entity_ids:
            return None, 0
        values: list[float] = []
        for eid in zone.soil_moisture_entity_ids:
            state = self.hass.states.get(eid)
            if state is None or state.state in (
                None,
                "",
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                continue
            try:
                values.append(float(state.state))
            except (TypeError, ValueError):
                continue
        if not values:
            return None, 0
        return sum(values) / len(values), len(values)

    # ----------------------------------------------------------- radiation

    @callback
    def _handle_radiation_change(self, event: Event) -> None:
        """Track radiation source state changes and integrate over time."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        self._update_radiation_from_state(new_state)

    def _update_radiation_from_state(self, state: State) -> None:
        if state.state in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
            # Pause integration without resetting the accumulator.
            self._radiation_last_value = None
            self._radiation_last_ts = None
            return
        try:
            value = float(state.state)
        except (TypeError, ValueError):
            return
        now = dt_util.utcnow()

        if self._radiation_unit == UNIT_WH_PER_M2:
            # Source already integrated -> use as absolute reading.
            # Treat as monotonic; only add positive deltas.
            if self._radiation_last_value is not None and value >= self._radiation_last_value:
                self._radiation_total_wh += value - self._radiation_last_value
            self._radiation_last_value = value
            self._radiation_last_ts = now
            self.async_update_listeners()
            return

        # W/m² -> trapezoidal integration to Wh/m²
        if self._radiation_last_value is not None and self._radiation_last_ts is not None:
            dt_h = (now - self._radiation_last_ts).total_seconds() / 3600.0
            if dt_h > 0:
                avg_w = (self._radiation_last_value + value) / 2.0
                if avg_w > 0:
                    self._radiation_total_wh += avg_w * dt_h
        self._radiation_last_value = value
        self._radiation_last_ts = now
        self.async_update_listeners()

    # ------------------------------------------------------------- triggers

    async def _async_update_data(self) -> dict[str, Any]:
        """Coordinator tick: integrate radiation and evaluate triggers."""
        # Pull a fresh sample from the radiation source so we keep accumulating
        # even when the source value is constant between state changes.
        if self._radiation_source:
            current = self.hass.states.get(self._radiation_source)
            await self._async_check_radiation_source_alert(current)
            if current is not None:
                self._update_radiation_from_state(current)

        now = dt_util.now()
        for zone in list(self._zones.values()):
            await self._async_check_runs_24h_alert(zone, now)
            await self._evaluate_zone_triggers(zone, now)

        return {
            "radiation_total_wh": self._radiation_total_wh,
            "zones": {
                zid: {
                    "is_running": rt.is_running,
                    "last_run_at": rt.last_run_at,
                    "last_reason": rt.last_reason,
                    "started_at": rt.started_at,
                    "accumulated_radiation_at_last_run": rt.accumulated_radiation_at_last_run,
                    "radiation_since_last_run": self.radiation_since_last_run(zid),
                    "last_relay_error": rt.last_relay_error,
                    "runs_24h": _count_recent_runs(rt.run_history, now),
                }
                for zid, rt in self._runtime.items()
            },
        }

    async def _evaluate_zone_triggers(self, zone: ZoneConfig, now: datetime) -> None:
        rt = self._runtime.get(zone.zone_id)
        if rt is None or rt.is_running:
            return

        # Global min-interval gate: applies to ALL automatic triggers
        # (radiation, fallback, soil moisture). Manual starts via service /
        # button bypass this because they don't go through this evaluator.
        if (
            zone.min_interval_minutes > 0
            and rt.last_run_at is not None
            and (now - rt.last_run_at).total_seconds() / 60.0
            < zone.min_interval_minutes
        ):
            return

        # Soil moisture trigger – intentionally evaluated outside the fallback
        # time window because moisture-driven irrigation should work 24/7.
        if zone.soil_moisture_trigger_enabled and zone.soil_moisture_entity_ids:
            avg, valid = self.average_soil_moisture(zone.zone_id)
            suffix = f"soil_moisture_sensors_unavailable_{zone.zone_id}"
            if valid == 0:
                # Leave moisture_below_since unchanged to avoid oscillating
                # when a single sensor drops out briefly.
                await self._async_notify_once(
                    suffix,
                    f"Soil moisture sensors unavailable for {zone.name}",
                    f"Zone {zone.name} has a soil-moisture trigger enabled but "
                    "none of the configured sensors produced a valid reading.",
                )
            else:
                self._clear_alert(suffix)
                if avg is not None and avg >= zone.soil_moisture_threshold:
                    rt.moisture_below_since = None
                else:
                    if rt.moisture_below_since is None:
                        rt.moisture_below_since = now
                    dwell = (now - rt.moisture_below_since).total_seconds() / 60.0
                    if dwell >= max(0, zone.soil_moisture_dwell_minutes):
                        await self.async_start_zone(
                            zone.zone_id, REASON_MOISTURE
                        )
                        return

        if not in_fallback_window(zone, now.time()):
            # Radiation + fallback triggers only fire while we are inside the
            # configured time window (preserves the original YAML semantics).
            return

        # Radiation trigger
        if zone.radiation_trigger_enabled:
            threshold = zone.current_threshold()
            if (
                threshold > 0
                and self.radiation_since_last_run(zone.zone_id) >= threshold
            ):
                await self.async_start_zone(zone.zone_id, REASON_RADIATION)
                return

        # Fallback trigger
        if zone.fallback_enabled and rt.last_run_at is not None:
            mins = (now - rt.last_run_at).total_seconds() / 60.0
            need = max(5, min(240, zone.fallback_minutes))
            if mins >= need:
                await self.async_start_zone(zone.zone_id, REASON_FALLBACK)

    # ------------------------------------------------------------- runtime

    async def async_start_zone(
        self, zone_id: str, reason: str = REASON_MANUAL
    ) -> bool:
        """Start a zone respecting its lock; returns True if a run was scheduled."""
        zone = self._zones.get(zone_id)
        if zone is None:
            _LOGGER.warning("start_zone: unknown zone_id %s", zone_id)
            return False
        lock = self._zone_locks.setdefault(zone_id, asyncio.Lock())
        if lock.locked():
            _LOGGER.info("Zone %s already running, ignoring start", zone.name)
            return False

        # Schedule the actual run as a background task so callers don't block.
        task = self.hass.async_create_task(self._zone_run(zone, reason))
        self._zone_tasks[zone_id] = task
        return True

    async def _zone_run(self, zone: ZoneConfig, reason: str) -> None:
        lock = self._zone_locks.setdefault(zone.zone_id, asyncio.Lock())
        async with lock:
            rt = self._runtime.setdefault(zone.zone_id, ZoneRuntimeState())
            now = dt_util.now()
            rt.is_running = True
            rt.started_at = now
            rt.last_run_at = now
            rt.last_reason = reason
            rt.accumulated_radiation_at_last_run = self._radiation_total_wh
            rt.run_history.append(now.timestamp())
            rt.run_history = _trim_runs(rt.run_history, now)
            rt.last_relay_error = None
            rt.moisture_below_since = None
            self._clear_zone_alerts(zone.zone_id)
            self.async_update_listeners()

            if not await self._async_check_relay_available_before_start(zone, rt):
                return

            try:
                await self._async_relay_on(zone)
            except Exception as err:  # noqa: BLE001
                rt.last_relay_error = f"turn_on failed: {err}"
                rt.is_running = False
                rt.started_at = None
                _LOGGER.exception("Relay turn_on failed for zone %s", zone.name)
                await self._async_notify_once(
                    f"turn_on_failed_{zone.zone_id}",
                    f"Relay {zone.relay_entity_id} failed to turn on",
                    f"Zone {zone.name} could not start because turn_on failed: {err}",
                )
                self.async_update_listeners()
                return

            await self._async_check_runs_24h_alert(zone, now)
            self._track_monitor_task(
                self.hass.async_create_task(
                    self._async_monitor_run_timeout(zone, rt.started_at)
                )
            )

            # Power monitoring
            self._track_monitor_task(
                self.hass.async_create_task(self._async_monitor_power_start(zone))
            )

            try:
                await asyncio.sleep(zone.watering_duration_sec)
            except asyncio.CancelledError:
                _LOGGER.info("Zone %s run cancelled", zone.name)
            finally:
                try:
                    await self._async_relay_off(zone)
                except Exception as err:  # noqa: BLE001
                    rt.last_relay_error = f"turn_off failed: {err}"
                    _LOGGER.exception(
                        "Relay turn_off failed for zone %s", zone.name
                    )
                    await self._async_notify_once(
                        f"turn_off_failed_{zone.zone_id}",
                        f"Relay {zone.relay_entity_id} failed to turn off",
                        f"Zone {zone.name} could not stop cleanly because "
                        f"turn_off failed: {err}",
                    )
                    # Schedule a watchdog retry just in case.
                    self.hass.async_create_task(
                        self._async_watchdog_off(zone, retries=3)
                    )

                rt.is_running = False
                rt.started_at = None
                self.async_update_listeners()
                # Power-after-stop check
                self._track_monitor_task(
                    self.hass.async_create_task(self._async_monitor_power_end(zone))
                )
                await self._async_persist()

    async def async_stop_zone(self, zone_id: str) -> None:
        task = self._zone_tasks.get(zone_id)
        zone = self._zones.get(zone_id)
        if task and not task.done():
            task.cancel()
        if zone is not None:
            try:
                await self._async_relay_off(zone)
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Manual stop relay_off failed for %s", zone.name)
                await self._async_set_zone_error(
                    zone,
                    "manual_turn_off_failed",
                    f"Relay {zone.relay_entity_id} failed to turn off",
                    f"Manual stop for zone {zone.name} failed because turn_off "
                    f"failed: {err}",
                )
            rt = self._runtime.get(zone_id)
            if rt is not None:
                rt.is_running = False
                rt.started_at = None
                self.async_update_listeners()

    async def async_reset_radiation(self, zone_id: str) -> None:
        rt = self._runtime.get(zone_id)
        if rt is None:
            return
        rt.accumulated_radiation_at_last_run = self._radiation_total_wh
        self.async_update_listeners()
        await self._async_persist()

    # ----------------------------------------------------- relay/power

    async def _async_relay_on(self, zone: ZoneConfig) -> None:
        await self.hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {"entity_id": zone.relay_entity_id},
            blocking=True,
        )

    async def _async_relay_off(self, zone: ZoneConfig) -> None:
        await self.hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {"entity_id": zone.relay_entity_id},
            blocking=True,
        )

    async def _async_force_relay_off(self, zone: ZoneConfig) -> None:
        try:
            await self._async_relay_off(zone)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Force relay off failed for %s", zone.name)

    async def _async_check_relay_available_before_start(
        self, zone: ZoneConfig, rt: ZoneRuntimeState
    ) -> bool:
        state = self.hass.states.get(zone.relay_entity_id)
        if state is not None and state.state not in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            return True
        rt.last_relay_error = "relay_unavailable"
        rt.is_running = False
        rt.started_at = None
        self.async_update_listeners()
        reported_state = state.state if state is not None else "missing"
        await self._async_notify_once(
            f"relay_unavailable_{zone.zone_id}",
            f"Relay {zone.relay_entity_id} is unavailable",
            f"Zone {zone.name} was not started because relay state is "
            f"{reported_state}.",
        )
        return False

    async def _async_watchdog_off(self, zone: ZoneConfig, retries: int = 3) -> None:
        last_err: Exception | None = None
        for _ in range(retries):
            await asyncio.sleep(WATCHDOG_GRACE_SECONDS)
            try:
                await self._async_relay_off(zone)
                return
            except Exception as err:  # noqa: BLE001
                last_err = err
                continue
        rt = self._runtime.get(zone.zone_id)
        if rt is not None:
            rt.last_relay_error = "watchdog_turn_off_failed"
            self.async_update_listeners()
        await self._async_notify_once(
            f"watchdog_turn_off_failed_{zone.zone_id}",
            f"Relay {zone.relay_entity_id} could not be forced off",
            f"Zone {zone.name} watchdog failed to turn the relay off after "
            f"{retries} retries."
            + (f" Last error: {last_err}" if last_err else ""),
        )

    def _power_entity_for(self, zone: ZoneConfig) -> str | None:
        if zone.power_entity_id:
            return zone.power_entity_id
        if zone.relay_entity_id and "." in zone.relay_entity_id:
            obj_id = zone.relay_entity_id.split(".", 1)[1]
            return f"sensor.{obj_id}_power"
        return None

    async def _async_monitor_power_start(self, zone: ZoneConfig) -> None:
        entity = self._power_entity_for(zone)
        if entity is None:
            return

        if zone.power_alert_delay_sec > 0:
            await asyncio.sleep(zone.power_alert_delay_sec)
            rt = self._runtime.get(zone.zone_id)
            if rt is None or not rt.is_running:
                return

        # Wait up to POWER_WAIT_SECONDS for a positive reading.
        deadline = self.hass.loop.time() + POWER_WAIT_SECONDS
        last_value: float | None = None
        saw_sensor_state = False
        while self.hass.loop.time() < deadline:
            state = self.hass.states.get(entity)
            if state is not None:
                saw_sensor_state = True
            if state is not None and state.state not in (
                None,
                "",
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            ):
                try:
                    value = float(state.state)
                    last_value = value
                    if value > 0:
                        break
                except ValueError:
                    pass
            await asyncio.sleep(1)

        if last_value is None:
            if not zone.power_entity_id and not saw_sensor_state:
                return
            await self._async_set_zone_error(
                zone,
                "power_sensor_unavailable",
                f"Power sensor {entity} unavailable",
                f"Zone {zone.name} could not verify motor current because "
                f"power sensor {entity} did not provide a valid reading.",
            )
            return

        rt = self._runtime.get(zone.zone_id)
        if rt is None or not rt.is_running:
            return
        if last_value <= 0:
            await self._async_set_zone_error(
                zone,
                "power_no_consumption",
                f"Power consumption {zone.relay_entity_id} not detected",
                f"Measured power stayed at {last_value} W after startup. "
                "The motor may not have started or the power sensor may be wrong.",
            )
            return
        if last_value <= zone.power_min:
            await self._async_notify_once(
                f"power_low_{zone.zone_id}",
                f"Power consumption {zone.relay_entity_id} too low",
                f"Measured power ({last_value} W) is <= undercurrent threshold "
                f"({zone.power_min} W).",
            )
            rt.last_relay_error = "power_low"
            self.async_update_listeners()
        elif last_value >= zone.power_max:
            await self._async_notify_once(
                f"power_high_{zone.zone_id}",
                f"Power consumption {zone.relay_entity_id} too high",
                f"Measured power ({last_value} W) exceeds overcurrent threshold "
                f"({zone.power_max} W).",
            )
            rt.last_relay_error = "power_high"
            self.async_update_listeners()

    async def _async_monitor_power_end(self, zone: ZoneConfig) -> None:
        entity = self._power_entity_for(zone)
        if entity is None:
            return
        await asyncio.sleep(2)
        state = self.hass.states.get(entity)
        if state is None or state.state in (
            None,
            "",
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
        ):
            if state is None and not zone.power_entity_id:
                return
            await self._async_set_zone_error(
                zone,
                "power_sensor_unavailable_after_off",
                f"Power sensor {entity} unavailable after stop",
                f"Zone {zone.name} could not verify that power dropped to 0 W "
                f"because power sensor {entity} was unavailable.",
            )
            return
        try:
            value = float(state.state)
        except ValueError:
            await self._async_set_zone_error(
                zone,
                "power_sensor_invalid_after_off",
                f"Power sensor {entity} invalid after stop",
                f"Zone {zone.name} could not verify that power dropped to 0 W "
                f"because power sensor {entity} reported {state.state!r}.",
            )
            return
        if value > 0:
            await self._async_notify_once(
                f"power_after_off_{zone.zone_id}",
                f"Power consumption {zone.relay_entity_id} too high after stop",
                f"Power after script end is {value} W (should be 0 W).",
            )
            rt = self._runtime.get(zone.zone_id)
            if rt is not None:
                rt.last_relay_error = "power_after_off"
                self.async_update_listeners()

    def _track_monitor_task(self, task: asyncio.Task) -> None:
        self._monitor_tasks.add(task)
        task.add_done_callback(self._monitor_tasks.discard)

    def _clear_zone_alerts(self, zone_id: str) -> None:
        suffix = f"_{zone_id}"
        self._active_alerts = {
            alert for alert in self._active_alerts if not alert.endswith(suffix)
        }

    async def _async_set_zone_error(
        self, zone: ZoneConfig, code: str, title: str, message: str
    ) -> None:
        rt = self._runtime.get(zone.zone_id)
        if rt is not None:
            rt.last_relay_error = code
            self.async_update_listeners()
        await self._async_notify_once(f"{code}_{zone.zone_id}", title, message)

    async def _async_notify_once(self, suffix: str, title: str, message: str) -> None:
        if suffix in self._active_alerts:
            return
        self._active_alerts.add(suffix)
        await self._async_notify(suffix, title, message)

    def _clear_alert(self, suffix: str) -> None:
        self._active_alerts.discard(suffix)

    async def _async_monitor_run_timeout(
        self, zone: ZoneConfig, started_at: datetime | None
    ) -> None:
        await asyncio.sleep(zone.watering_duration_sec + WATCHDOG_GRACE_SECONDS)
        rt = self._runtime.get(zone.zone_id)
        if rt is None or not rt.is_running or rt.started_at != started_at:
            return
        await self._async_set_zone_error(
            zone,
            "run_timeout",
            f"Zone {zone.name} is running longer than expected",
            f"Zone {zone.name} is still marked as running after "
            f"{zone.watering_duration_sec + WATCHDOG_GRACE_SECONDS} seconds.",
        )

    async def _async_check_radiation_source_alert(self, state: State | None) -> None:
        suffix = "radiation_source_unavailable"
        if state is None or state.state in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
            await self._async_notify_once(
                suffix,
                "Radiation source unavailable",
                f"Radiation source {self._radiation_source} is unavailable, "
                "so radiation-based irrigation cannot be evaluated.",
            )
            return

        try:
            value = float(state.state)
        except (TypeError, ValueError):
            value = None

        stale_suffix = "radiation_source_stale"
        if value is not None and value <= 0:
            self._clear_alert(suffix)
            self._clear_alert(stale_suffix)
            return

        age = (dt_util.utcnow() - state.last_updated).total_seconds()
        if age > RADIATION_STALE_SECONDS:
            self._clear_alert(suffix)
            await self._async_notify_once(
                stale_suffix,
                "Radiation source stale",
                f"Radiation source {self._radiation_source} has not updated for "
                f"{round(age / 60)} minutes.",
            )
            return

        self._clear_alert(suffix)
        self._clear_alert(stale_suffix)

    async def _async_check_runs_24h_alert(
        self, zone: ZoneConfig, now: datetime
    ) -> None:
        suffix = f"runs_24h_{zone.zone_id}"
        if zone.max_runs_24h <= 0:
            self._clear_alert(suffix)
            return
        rt = self._runtime.get(zone.zone_id)
        if rt is None:
            self._clear_alert(suffix)
            return
        runs = _count_recent_runs(rt.run_history, now)
        if runs <= zone.max_runs_24h:
            self._clear_alert(suffix)
            return
        rt.last_relay_error = "too_many_runs_24h"
        self.async_update_listeners()
        await self._async_notify_once(
            suffix,
            f"Zone {zone.name} ran too often",
            f"Zone {zone.name} ran {runs} times in the last 24 hours, "
            f"above the configured alert threshold of {zone.max_runs_24h}.",
        )

    async def _async_notify(self, suffix: str, title: str, message: str) -> None:
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "notification_id": f"{NOTIFICATION_ID_PREFIX}_{suffix}",
                    "title": title,
                    "message": message,
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to create persistent notification")

        if not self._push_alerts_enabled or not self._push_alert_device_ids:
            return

        for device_id in self._push_alert_device_ids:
            service = mobile_app_notify_service(self.hass, device_id)
            if service is None:
                _LOGGER.warning(
                    "No mobile_app notify service found for device %s; "
                    "skipping push notification",
                    device_id,
                )
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"title": title, "message": message},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                _LOGGER.exception(
                    "Failed to send push notification to device %s via %s",
                    device_id,
                    service,
                )

    # --------------------------------------------------------------- persist

    async def _async_persist_tick(self, _now: datetime) -> None:
        await self._async_persist()

    async def _async_persist(self) -> None:
        try:
            await self._store.async_save(
                {
                    "radiation_total_wh": self._radiation_total_wh,
                    "zones": {
                        zid: rt.to_dict() for zid, rt in self._runtime.items()
                    },
                }
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to persist runtime state")


# ----------------------------------------------------------------- helpers


def in_fallback_window(zone: ZoneConfig, now_t: time) -> bool:
    """Return True if `now_t` is inside the configured fallback window.

    Mirrors the original YAML semantics: handles same-day and overnight windows.
    Empty/missing strings -> True (no constraint).
    """
    s = _parse_time(zone.fallback_start)
    e = _parse_time(zone.fallback_end)
    if s is None or e is None:
        return True
    if s <= e:
        return s <= now_t <= e
    return now_t >= s or now_t <= e


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 2:
            return time(int(parts[0]), int(parts[1]))
        if len(parts) == 3:
            return time(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    return None


def _trim_runs(history: list[float], now: datetime) -> list[float]:
    cutoff = now.timestamp() - 24 * 3600
    return [t for t in history if t >= cutoff]


def _count_recent_runs(history: list[float], now: datetime) -> int:
    cutoff = now.timestamp() - 24 * 3600
    return sum(1 for t in history if t >= cutoff)
