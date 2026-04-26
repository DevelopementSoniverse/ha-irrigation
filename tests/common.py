"""Helpers for irrigation_computer tests."""

from __future__ import annotations

import uuid
from typing import Any

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
        ZONE_POWER_MIN: 5.0,
        ZONE_POWER_MAX: 500.0,
        ZONE_FALLBACK_ENABLED: fallback_enabled,
        ZONE_FALLBACK_MINUTES: fallback_minutes,
        ZONE_FALLBACK_START: fallback_start,
        ZONE_FALLBACK_END: fallback_end,
        ZONE_RADIATION_TRIGGER_ENABLED: radiation_trigger_enabled,
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
