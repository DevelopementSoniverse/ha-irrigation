"""Number platform for the Irrigation Computer integration.

All numeric configuration knobs of a zone are exposed as Number entities so they
can be tweaked from the dashboard without going through the options flow.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    OPT_ZONES,
    UNIT_WH_PER_M2,
    ZONE_FALLBACK_MINUTES,
    ZONE_ID,
    ZONE_MAX_RUNS_24H,
    ZONE_POWER_ALERT_DELAY,
    ZONE_POWER_MAX,
    ZONE_POWER_MIN,
    ZONE_THRESHOLD_FRUIT_SET,
    ZONE_THRESHOLD_PLANTING,
    ZONE_THRESHOLD_RIPENING,
    ZONE_WATERING_DURATION,
)
from .coordinator import IrrigationController
from .entity import IrrigationZoneEntity
from .models import ZoneConfig


@dataclass(frozen=True)
class _NumberSpec:
    key: str
    field: str
    name: str
    icon: str
    unit: str | None
    min_v: float
    max_v: float
    step: float
    is_int: bool = False


_NUMBERS: tuple[_NumberSpec, ...] = (
    _NumberSpec(
        "watering_duration_sec",
        ZONE_WATERING_DURATION,
        "Watering duration",
        "mdi:clock-end",
        UnitOfTime.SECONDS,
        10,
        3600,
        10,
        True,
    ),
    _NumberSpec(
        "threshold_planting",
        ZONE_THRESHOLD_PLANTING,
        "Threshold Planting",
        "mdi:sun-wireless",
        UNIT_WH_PER_M2,
        0,
        1000,
        5,
    ),
    _NumberSpec(
        "threshold_fruit_set",
        ZONE_THRESHOLD_FRUIT_SET,
        "Threshold Fruit Set",
        "mdi:sun-wireless",
        UNIT_WH_PER_M2,
        0,
        1000,
        5,
    ),
    _NumberSpec(
        "threshold_ripening",
        ZONE_THRESHOLD_RIPENING,
        "Threshold Ripening",
        "mdi:sun-wireless",
        UNIT_WH_PER_M2,
        0,
        1000,
        5,
    ),
    _NumberSpec(
        "power_alert_delay_sec",
        ZONE_POWER_ALERT_DELAY,
        "Power alert delay",
        "mdi:timer-alert-outline",
        UnitOfTime.SECONDS,
        0,
        300,
        1,
        True,
    ),
    _NumberSpec(
        "power_min",
        ZONE_POWER_MIN,
        "Undercurrent threshold",
        "mdi:flash-alert",
        UnitOfPower.WATT,
        0,
        10000,
        1,
    ),
    _NumberSpec(
        "power_max",
        ZONE_POWER_MAX,
        "Overcurrent threshold",
        "mdi:flash-alert",
        UnitOfPower.WATT,
        0,
        10000,
        1,
    ),
    _NumberSpec(
        "max_runs_24h",
        ZONE_MAX_RUNS_24H,
        "Max runs 24h alert threshold",
        "mdi:counter",
        None,
        0,
        50,
        1,
        True,
    ),
    _NumberSpec(
        "fallback_minutes",
        ZONE_FALLBACK_MINUTES,
        "Fallback interval",
        "mdi:timer-outline",
        UnitOfTime.MINUTES,
        5,
        240,
        5,
        True,
    ),
)


def _update_zone_field(
    hass: HomeAssistant,
    controller: IrrigationController,
    zone_id: str,
    field: str,
    value: float | int,
) -> None:
    new_options = dict(controller.entry.options)
    zones = list(new_options.get(OPT_ZONES, []))
    for idx, z in enumerate(zones):
        if z.get(ZONE_ID) == zone_id:
            updated = dict(z)
            updated[field] = value
            zones[idx] = updated
            break
    new_options[OPT_ZONES] = zones
    hass.config_entries.async_update_entry(controller.entry, options=new_options)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list = []
    for zone in controller.zones:
        for spec in _NUMBERS:
            entities.append(ZoneNumber(controller, zone, spec))
    async_add_entities(entities)


class ZoneNumber(IrrigationZoneEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        controller: IrrigationController,
        zone: ZoneConfig,
        spec: _NumberSpec,
    ) -> None:
        super().__init__(controller, zone, spec.key)
        self._spec = spec
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_native_min_value = spec.min_v
        self._attr_native_max_value = spec.max_v
        self._attr_native_step = spec.step

    @property
    def native_value(self) -> float | None:
        zone = self.zone
        if zone is None:
            return None
        value = getattr(zone, self._spec.field, None)
        return value

    async def async_set_native_value(self, value: float) -> None:
        v: float | int = int(value) if self._spec.is_int else float(value)
        _update_zone_field(
            self.hass, self._controller, self._zone_id, self._spec.field, v
        )
