"""The Irrigation Computer integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, Platform
from homeassistant.core import Event, HomeAssistant

from .const import DOMAIN
from .coordinator import IrrigationController
from .dashboard import async_update_dashboard
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.TIME,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Irrigation Computer from a config entry."""
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async_register_services(hass)

    # Rebuild the auto-managed Lovelace dashboard from the current zone list.
    # Runs after platform forwarding so the entity registry is populated.
    await async_update_dashboard(hass, controller)

    # Rebuild the dashboard when HA's language changes, so card titles,
    # button captions and gauge names pick up the new locale. Storage
    # dashboards are not translated on the fly by Lovelace.
    current_language = hass.config.language

    async def _handle_core_config_update(event: Event) -> None:
        nonlocal current_language
        new_language = hass.config.language
        if new_language == current_language:
            return
        current_language = new_language
        _LOGGER.debug(
            "HA language changed to %s – rebuilding dashboard", new_language
        )
        await async_update_dashboard(hass, controller)

    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_CORE_CONFIG_UPDATE, _handle_core_config_update
        )
    )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change so zone changes take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    controller: IrrigationController | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if controller is not None:
        await controller.async_shutdown()

    if not hass.data.get(DOMAIN):
        async_unregister_services(hass)

    return unload_ok
