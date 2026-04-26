"""Switch platform for the Irrigation Computer integration.

Provides three switches per zone:
- ``running``: starting/stopping the irrigation manually
- ``fallback_enabled``: toggle fallback trigger for this zone
- ``radiation_trigger_enabled``: toggle radiation trigger for this zone
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    OPT_ZONES,
    REASON_MANUAL,
    ZONE_FALLBACK_ENABLED,
    ZONE_ID,
    ZONE_RADIATION_TRIGGER_ENABLED,
    ZONE_SOIL_MOISTURE_TRIGGER_ENABLED,
)
from .coordinator import IrrigationController
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
                ZoneRunningSwitch(controller, zone),
                ZoneFallbackEnabledSwitch(controller, zone),
                ZoneRadiationTriggerEnabledSwitch(controller, zone),
                ZoneSoilMoistureTriggerEnabledSwitch(controller, zone),
            ]
        )
    async_add_entities(entities)


def _update_zone_option(
    hass: HomeAssistant,
    controller: IrrigationController,
    zone_id: str,
    field: str,
    value: Any,
) -> None:
    """Persist a single option-flag change for a zone."""
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


class _ZoneSwitchBase(IrrigationZoneEntity, SwitchEntity):
    pass


class ZoneRunningSwitch(_ZoneSwitchBase):
    _attr_name = "Run"
    _attr_icon = "mdi:water-pump"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "running_switch")

    @property
    def is_on(self) -> bool:
        rt = self._controller.get_runtime(self._zone_id)
        return bool(rt and rt.is_running)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._controller.async_start_zone(self._zone_id, REASON_MANUAL)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._controller.async_stop_zone(self._zone_id)


class ZoneFallbackEnabledSwitch(_ZoneSwitchBase):
    _attr_name = "Fallback enabled"
    _attr_icon = "mdi:clock-alert"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "fallback_enabled")

    @property
    def is_on(self) -> bool:
        zone = self.zone
        return bool(zone and zone.fallback_enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass, self._controller, self._zone_id, ZONE_FALLBACK_ENABLED, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass, self._controller, self._zone_id, ZONE_FALLBACK_ENABLED, False
        )


class ZoneRadiationTriggerEnabledSwitch(_ZoneSwitchBase):
    _attr_name = "Radiation trigger enabled"
    _attr_icon = "mdi:weather-sunny-alert"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "radiation_trigger_enabled")

    @property
    def is_on(self) -> bool:
        zone = self.zone
        return bool(zone and zone.radiation_trigger_enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass,
            self._controller,
            self._zone_id,
            ZONE_RADIATION_TRIGGER_ENABLED,
            True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass,
            self._controller,
            self._zone_id,
            ZONE_RADIATION_TRIGGER_ENABLED,
            False,
        )


class ZoneSoilMoistureTriggerEnabledSwitch(_ZoneSwitchBase):
    _attr_name = "Soil moisture trigger enabled"
    _attr_icon = "mdi:water-percent-alert"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "soil_moisture_trigger_enabled")

    @property
    def is_on(self) -> bool:
        zone = self.zone
        return bool(zone and zone.soil_moisture_trigger_enabled)

    async def async_turn_on(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass,
            self._controller,
            self._zone_id,
            ZONE_SOIL_MOISTURE_TRIGGER_ENABLED,
            True,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        _update_zone_option(
            self.hass,
            self._controller,
            self._zone_id,
            ZONE_SOIL_MOISTURE_TRIGGER_ENABLED,
            False,
        )
