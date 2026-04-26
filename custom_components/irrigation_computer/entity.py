"""Common entity base classes for the Irrigation Computer integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import IrrigationController
    from .models import ZoneConfig


class IrrigationZoneEntity(CoordinatorEntity["IrrigationController"]):
    """Base class for entities tied to a single irrigation zone."""

    _attr_has_entity_name = True

    def __init__(
        self,
        controller: "IrrigationController",
        zone: "ZoneConfig",
        key: str,
    ) -> None:
        super().__init__(controller)
        self._controller = controller
        self._zone_id = zone.zone_id
        self._key = key
        self._attr_unique_id = f"{controller.entry.entry_id}_{zone.zone_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{controller.entry.entry_id}_{zone.zone_id}")},
            name=zone.name,
            manufacturer="Irrigation Computer",
            model="Zone",
            via_device=(DOMAIN, controller.entry.entry_id),
        )

    @property
    def zone(self) -> "ZoneConfig | None":
        """Return current ZoneConfig snapshot from controller (may be None if removed)."""
        return self._controller.get_zone(self._zone_id)

    @property
    def available(self) -> bool:
        """Entity is available while its zone still exists in the config."""
        return super().available and self.zone is not None


class IrrigationControllerEntity(CoordinatorEntity["IrrigationController"]):
    """Base class for global controller-level entities."""

    _attr_has_entity_name = True

    def __init__(self, controller: "IrrigationController", key: str) -> None:
        super().__init__(controller)
        self._controller = controller
        self._key = key
        self._attr_unique_id = f"{controller.entry.entry_id}_controller_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, controller.entry.entry_id)},
            name="Irrigation Computer",
            manufacturer="Irrigation Computer",
            model="Controller",
        )
