"""Button platform for the Irrigation Computer integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, REASON_MANUAL
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
                ZoneStartButton(controller, zone),
                ZoneStopButton(controller, zone),
                ZoneResetRadiationButton(controller, zone),
            ]
        )
    async_add_entities(entities)


class _ZoneButton(IrrigationZoneEntity, ButtonEntity):
    pass


class ZoneStartButton(_ZoneButton):
    _attr_name = "Start irrigation"
    _attr_icon = "mdi:play"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "start_button")

    async def async_press(self) -> None:
        await self._controller.async_start_zone(self._zone_id, REASON_MANUAL)


class ZoneStopButton(_ZoneButton):
    _attr_name = "Stop irrigation"
    _attr_icon = "mdi:stop"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "stop_button")

    async def async_press(self) -> None:
        await self._controller.async_stop_zone(self._zone_id)


class ZoneResetRadiationButton(_ZoneButton):
    _attr_name = "Reset radiation counter"
    _attr_icon = "mdi:restart"

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "reset_radiation_button")

    async def async_press(self) -> None:
        await self._controller.async_reset_radiation(self._zone_id)
