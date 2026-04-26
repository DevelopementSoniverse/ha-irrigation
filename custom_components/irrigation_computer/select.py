"""Select platform for the Irrigation Computer integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, OPT_ZONES, PHASES, ZONE_ID, ZONE_PHASE
from .coordinator import IrrigationController
from .entity import IrrigationZoneEntity
from .models import ZoneConfig


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list = [PhaseSelect(controller, zone) for zone in controller.zones]
    async_add_entities(entities)


class PhaseSelect(IrrigationZoneEntity, SelectEntity):
    _attr_name = "Growth phase"
    _attr_icon = "mdi:sprout"
    _attr_options = list(PHASES)

    def __init__(self, controller: IrrigationController, zone: ZoneConfig) -> None:
        super().__init__(controller, zone, "phase")

    @property
    def current_option(self) -> str | None:
        zone = self.zone
        return zone.phase if zone else None

    async def async_select_option(self, option: str) -> None:
        if option not in PHASES:
            return
        new_options = dict(self._controller.entry.options)
        zones = list(new_options.get(OPT_ZONES, []))
        for idx, z in enumerate(zones):
            if z.get(ZONE_ID) == self._zone_id:
                updated = dict(z)
                updated[ZONE_PHASE] = option
                zones[idx] = updated
                break
        new_options[OPT_ZONES] = zones
        self.hass.config_entries.async_update_entry(
            self._controller.entry, options=new_options
        )
