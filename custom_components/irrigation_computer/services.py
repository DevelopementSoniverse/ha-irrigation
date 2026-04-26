"""Service handlers for the Irrigation Computer integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_REASON,
    ATTR_ZONE_ID,
    DOMAIN,
    REASON_MANUAL,
    REASONS,
    SERVICE_RESET_RADIATION,
    SERVICE_START_ALL,
    SERVICE_START_ZONE,
    SERVICE_STOP_ZONE,
)

_LOGGER = logging.getLogger(__name__)

_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE_ID): cv.string,
        vol.Optional(ATTR_REASON, default=REASON_MANUAL): vol.In(REASONS),
    }
)
_ZONE_ONLY_SCHEMA = vol.Schema({vol.Required(ATTR_ZONE_ID): cv.string})
_ALL_SCHEMA = vol.Schema({vol.Optional(ATTR_REASON, default=REASON_MANUAL): vol.In(REASONS)})


def _iter_controllers(hass: HomeAssistant):
    return list(hass.data.get(DOMAIN, {}).values())


def _find_controller_for_zone(hass: HomeAssistant, zone_id: str):
    for controller in _iter_controllers(hass):
        if controller.get_zone(zone_id) is not None:
            return controller
    return None


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_START_ZONE):
        return

    async def handle_start_zone(call: ServiceCall) -> None:
        zone_id = call.data[ATTR_ZONE_ID]
        reason = call.data.get(ATTR_REASON, REASON_MANUAL)
        controller = _find_controller_for_zone(hass, zone_id)
        if controller is None:
            _LOGGER.warning("start_zone: no controller for zone_id %s", zone_id)
            return
        await controller.async_start_zone(zone_id, reason)

    async def handle_stop_zone(call: ServiceCall) -> None:
        zone_id = call.data[ATTR_ZONE_ID]
        controller = _find_controller_for_zone(hass, zone_id)
        if controller is None:
            return
        await controller.async_stop_zone(zone_id)

    async def handle_reset_radiation(call: ServiceCall) -> None:
        zone_id = call.data[ATTR_ZONE_ID]
        controller = _find_controller_for_zone(hass, zone_id)
        if controller is None:
            return
        await controller.async_reset_radiation(zone_id)

    async def handle_start_all(call: ServiceCall) -> None:
        reason = call.data.get(ATTR_REASON, REASON_MANUAL)
        for controller in _iter_controllers(hass):
            for zone in controller.zones:
                await controller.async_start_zone(zone.zone_id, reason)
                # Wait until that zone's task is done before starting the next
                # so we don't run multiple zones in parallel.
                task = controller._zone_tasks.get(zone.zone_id)  # noqa: SLF001
                if task is not None:
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):  # noqa: BLE001
                        pass

    hass.services.async_register(
        DOMAIN, SERVICE_START_ZONE, handle_start_zone, schema=_ZONE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_ZONE, handle_stop_zone, schema=_ZONE_ONLY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RESET_RADIATION, handle_reset_radiation, schema=_ZONE_ONLY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_START_ALL, handle_start_all, schema=_ALL_SCHEMA
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    for svc in (
        SERVICE_START_ZONE,
        SERVICE_STOP_ZONE,
        SERVICE_RESET_RADIATION,
        SERVICE_START_ALL,
    ):
        if hass.services.has_service(DOMAIN, svc):
            hass.services.async_remove(DOMAIN, svc)
