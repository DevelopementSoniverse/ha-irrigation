"""Time platform for the Irrigation Computer integration."""

from __future__ import annotations

from datetime import time as dtime

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    OPT_ZONES,
    ZONE_FALLBACK_END,
    ZONE_FALLBACK_START,
    ZONE_ID,
)
from .coordinator import IrrigationController
from .entity import IrrigationZoneEntity
from .models import ZoneConfig


_TIME_FIELDS: tuple[tuple[str, str], ...] = (
    ("fallback_start", ZONE_FALLBACK_START),
    ("fallback_end", ZONE_FALLBACK_END),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: IrrigationController = hass.data[DOMAIN][entry.entry_id]
    entities: list = []
    for zone in controller.zones:
        for key, field in _TIME_FIELDS:
            entities.append(FallbackTimeEntity(controller, zone, key, field))
    async_add_entities(entities)


def _parse(value: str | None) -> dtime | None:
    if not value:
        return None
    parts = value.split(":")
    try:
        if len(parts) == 2:
            return dtime(int(parts[0]), int(parts[1]))
        if len(parts) == 3:
            return dtime(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None
    return None


class FallbackTimeEntity(IrrigationZoneEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        controller: IrrigationController,
        zone: ZoneConfig,
        key: str,
        field: str,
    ) -> None:
        super().__init__(controller, zone, key)
        self._field = field
        self._attr_translation_key = key

    @property
    def native_value(self) -> dtime | None:
        zone = self.zone
        if zone is None:
            return None
        return _parse(getattr(zone, self._field, None))

    async def async_set_value(self, value: dtime) -> None:
        new_options = dict(self._controller.entry.options)
        zones = list(new_options.get(OPT_ZONES, []))
        for idx, z in enumerate(zones):
            if z.get(ZONE_ID) == self._zone_id:
                updated = dict(z)
                updated[self._field] = value.strftime("%H:%M:%S")
                zones[idx] = updated
                break
        new_options[OPT_ZONES] = zones
        self.hass.config_entries.async_update_entry(
            self._controller.entry, options=new_options
        )
