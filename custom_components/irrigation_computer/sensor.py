"""Sensor platform for the Irrigation Computer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, REASONS, UNIT_WH_PER_M2
from .coordinator import IrrigationController
from .entity import IrrigationControllerEntity, IrrigationZoneEntity
from .models import ZoneConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list = [GlobalRadiationEnergySensor(controller)]
    for zone in controller.zones:
        entities.extend(
            [
                TimeSinceLastIrrigationSensor(controller, zone),
                RadiationSinceLastIrrigationSensor(controller, zone),
                CurrentRadiationThresholdSensor(controller, zone),
                CurrentPowerSensor(controller, zone),
                Runs24hSensor(controller, zone),
                LastRunSensor(controller, zone),
                LastReasonSensor(controller, zone),
            ]
        )
    async_add_entities(entities)


# ---------------------------------------------------------------- Controller


class GlobalRadiationEnergySensor(IrrigationControllerEntity, SensorEntity):
    _attr_translation_key = "global_radiation_energy"
    _attr_name = "Global radiation energy"
    _attr_native_unit_of_measurement = UNIT_WH_PER_M2
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, controller: IrrigationController) -> None:
        super().__init__(controller, "global_radiation_energy")

    @property
    def native_value(self) -> float:
        return round(self._controller.radiation_total_wh, 3)


# --------------------------------------------------------------------- Zone


class _ZoneSensorBase(IrrigationZoneEntity, SensorEntity):
    pass


class TimeSinceLastIrrigationSensor(_ZoneSensorBase):
    _attr_name = "Time since last irrigation"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "time_since_last_irrigation")

    @property
    def native_value(self) -> float | None:
        rt = self._controller.get_runtime(self._zone_id)
        if rt is None or rt.last_run_at is None:
            return None
        delta = dt_util.now() - rt.last_run_at
        return round(delta.total_seconds() / 60.0, 1)


class RadiationSinceLastIrrigationSensor(_ZoneSensorBase):
    _attr_name = "Radiation since last irrigation"
    _attr_native_unit_of_measurement = UNIT_WH_PER_M2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:sun-wireless"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "radiation_since_last_irrigation")

    @property
    def native_value(self) -> float:
        return round(self._controller.radiation_since_last_run(self._zone_id), 3)


class CurrentRadiationThresholdSensor(_ZoneSensorBase):
    _attr_name = "Current radiation threshold"
    _attr_native_unit_of_measurement = UNIT_WH_PER_M2
    _attr_icon = "mdi:sun-wireless-outline"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "current_radiation_threshold")

    @property
    def native_value(self) -> float | None:
        zone = self.zone
        return zone.current_threshold() if zone else None


class CurrentPowerSensor(_ZoneSensorBase):
    _attr_name = "Current power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "current_power")

    def _power_entity_id(self) -> str | None:
        zone = self.zone
        if zone is None:
            return None
        return self._controller._power_entity_for(zone)  # noqa: SLF001

    @property
    def native_value(self) -> float | None:
        eid = self._power_entity_id()
        if not eid:
            return None
        state = self.hass.states.get(eid)
        if state is None or state.state in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        eid = self._power_entity_id()
        if not eid:
            return False
        state = self.hass.states.get(eid)
        return bool(state and state.state not in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"source_entity_id": self._power_entity_id()}


class Runs24hSensor(_ZoneSensorBase):
    _attr_name = "Runs 24h"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:counter"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "runs_24h")

    @property
    def native_value(self) -> int:
        rt = self._controller.get_runtime(self._zone_id)
        if rt is None:
            return 0
        cutoff = dt_util.now().timestamp() - 24 * 3600
        return sum(1 for t in rt.run_history if t >= cutoff)


class LastRunSensor(_ZoneSensorBase):
    _attr_name = "Last run"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:history"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "last_run")

    @property
    def native_value(self) -> datetime | None:
        rt = self._controller.get_runtime(self._zone_id)
        return rt.last_run_at if rt else None


class LastReasonSensor(_ZoneSensorBase):
    _attr_name = "Last reason"
    _attr_icon = "mdi:information-outline"
    _attr_options = list(REASONS)
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "last_reason")

    @property
    def native_value(self) -> str | None:
        rt = self._controller.get_runtime(self._zone_id)
        return rt.last_reason if rt else None
