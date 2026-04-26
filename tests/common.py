"""Helpers for irrigation_computer tests."""

from __future__ import annotations

import uuid
from typing import Any

from homeassistant.core import HomeAssistant

from custom_components.irrigation_computer.const import (
    CONF_RADIATION_SOURCE_ENTITY,
    CONF_RADIATION_SOURCE_UNIT,
    DOMAIN,
    OPT_ZONES,
    UNIT_W_PER_M2,
    ZONE_FALLBACK_ENABLED,
    ZONE_FALLBACK_END,
    ZONE_FALLBACK_MINUTES,
    ZONE_FALLBACK_START,
    ZONE_ID,
    ZONE_MAX_RUNS_24H,
    ZONE_MIN_INTERVAL_MINUTES,
    ZONE_NAME,
    ZONE_PHASE,
    ZONE_POWER_ALERT_DELAY,
    ZONE_POWER_ENTITY,
    ZONE_POWER_MAX,
    ZONE_POWER_MIN,
    ZONE_RADIATION_TRIGGER_ENABLED,
    ZONE_RELAY_ENTITY,
    ZONE_SOIL_MOISTURE_DWELL_MINUTES,
    ZONE_SOIL_MOISTURE_ENTITIES,
    ZONE_SOIL_MOISTURE_THRESHOLD,
    ZONE_SOIL_MOISTURE_TRIGGER_ENABLED,
    ZONE_THRESHOLD_FRUIT_SET,
    ZONE_THRESHOLD_PLANTING,
    ZONE_THRESHOLD_RIPENING,
    ZONE_WATERING_DURATION,
    PHASE_PLANTING,
)


def make_zone(
    *,
    name: str = "Test Zone",
    relay: str = "switch.test_relay",
    power: str | None = None,
    duration: int = 3,
    fallback_enabled: bool = True,
    fallback_minutes: int = 5,
    fallback_start: str = "00:00:00",
    fallback_end: str = "23:59:59",
    radiation_trigger_enabled: bool = True,
    threshold_planting: float = 100.0,
    power_alert_delay_sec: int = 0,
    max_runs_24h: int = 0,
    soil_moisture_entity_ids: list[str] | None = None,
    soil_moisture_trigger_enabled: bool = False,
    soil_moisture_threshold: float = 30.0,
    soil_moisture_dwell_minutes: int = 0,
    min_interval_minutes: int = 0,
) -> dict[str, Any]:
    return {
        ZONE_ID: uuid.uuid4().hex,
        ZONE_NAME: name,
        ZONE_RELAY_ENTITY: relay,
        ZONE_POWER_ENTITY: power,
        ZONE_WATERING_DURATION: duration,
        ZONE_PHASE: PHASE_PLANTING,
        ZONE_THRESHOLD_PLANTING: threshold_planting,
        ZONE_THRESHOLD_FRUIT_SET: 200.0,
        ZONE_THRESHOLD_RIPENING: 80.0,
        ZONE_POWER_ALERT_DELAY: power_alert_delay_sec,
        ZONE_POWER_MIN: 5.0,
        ZONE_POWER_MAX: 500.0,
        ZONE_MAX_RUNS_24H: max_runs_24h,
        ZONE_FALLBACK_ENABLED: fallback_enabled,
        ZONE_FALLBACK_MINUTES: fallback_minutes,
        ZONE_FALLBACK_START: fallback_start,
        ZONE_FALLBACK_END: fallback_end,
        ZONE_RADIATION_TRIGGER_ENABLED: radiation_trigger_enabled,
        ZONE_SOIL_MOISTURE_ENTITIES: list(soil_moisture_entity_ids or []),
        ZONE_SOIL_MOISTURE_TRIGGER_ENABLED: soil_moisture_trigger_enabled,
        ZONE_SOIL_MOISTURE_THRESHOLD: soil_moisture_threshold,
        ZONE_SOIL_MOISTURE_DWELL_MINUTES: soil_moisture_dwell_minutes,
        ZONE_MIN_INTERVAL_MINUTES: min_interval_minutes,
    }


def base_entry_kwargs(
    radiation_source: str | None = None, zones: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "domain": DOMAIN,
        "data": {
            CONF_RADIATION_SOURCE_ENTITY: radiation_source,
            CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
        },
        "options": {OPT_ZONES: zones or []},
        "title": "Irrigation Computer",
    }


def seed_relay_states(
    hass: HomeAssistant, zones: list[dict[str, Any]], state: str = "off"
) -> None:
    """Populate ``hass.states`` for each zone's relay entity.

    The coordinator's pre-start availability check treats a missing relay
    state as unavailable, so tests that exercise ``async_start_zone`` must
    seed the underlying switch entity to simulate a loaded switch platform.
    """
    for zone in zones:
        relay = zone.get(ZONE_RELAY_ENTITY)
        if relay:
            hass.states.async_set(relay, state)
