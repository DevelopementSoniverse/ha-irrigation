"""Binary sensor platform for the Irrigation Computer integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import IrrigationController, in_fallback_window
from .entity import IrrigationZoneEntity
from .models import ZoneConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list = []
    for zone in controller.zones:
        entities.extend(
            [
                ZoneRunningBinarySensor(controller, zone),
                FallbackActiveBinarySensor(controller, zone),
                RelayAvailableBinarySensor(controller, zone),
                RelayErrorBinarySensor(controller, zone),
            ]
        )
    async_add_entities(entities)


class _ZoneBinaryBase(IrrigationZoneEntity, BinarySensorEntity):
    pass


class ZoneRunningBinarySensor(_ZoneBinaryBase):
    _attr_name = "Running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:water-pump"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "running")

    @property
    def is_on(self) -> bool:
        rt = self._controller.get_runtime(self._zone_id)
        return bool(rt and rt.is_running)


class FallbackActiveBinarySensor(_ZoneBinaryBase):
    _attr_name = "Fallback active"
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "fallback_active")

    @property
    def is_on(self) -> bool:
        zone = self.zone
        if zone is None or not zone.fallback_enabled:
            return False
        return in_fallback_window(zone, dt_util.now().time())


class RelayAvailableBinarySensor(_ZoneBinaryBase):
    _attr_name = "Relay available"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:lan-connect"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "relay_available")

    @property
    def is_on(self) -> bool:
        zone = self.zone
        if zone is None or not zone.relay_entity_id:
            return False
        state = self.hass.states.get(zone.relay_entity_id)
        return bool(
            state is not None
            and state.state not in (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)
        )


class RelayErrorBinarySensor(_ZoneBinaryBase):
    _attr_name = "Relay error"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "relay_error")

    @property
    def is_on(self) -> bool:
        rt = self._controller.get_runtime(self._zone_id)
        return bool(rt and rt.last_relay_error)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        rt = self._controller.get_runtime(self._zone_id)
        return {"error": rt.last_relay_error} if rt and rt.last_relay_error else {}
