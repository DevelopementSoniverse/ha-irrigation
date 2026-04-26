"""Diagnostics for the Irrigation Computer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_PUSH_ALERT_DEVICE_IDS, DOMAIN
from .coordinator import IrrigationController

REDACT_KEYS = {"radiation_source_entity", CONF_PUSH_ALERT_DEVICE_IDS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    controller: IrrigationController | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    data: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), REDACT_KEYS),
            "options": async_redact_data(dict(entry.options), REDACT_KEYS),
        }
    }
    if controller is not None:
        data["controller"] = {
            "radiation_total_wh": controller.radiation_total_wh,
            "radiation_source_entity": controller.radiation_source_entity,
            "zones": [
                {
                    "config": z.to_dict(),
                    "runtime": (
                        controller.get_runtime(z.zone_id).to_dict()
                        if controller.get_runtime(z.zone_id)
                        else None
                    ),
                    "radiation_since_last_run": controller.radiation_since_last_run(
                        z.zone_id
                    ),
                }
                for z in controller.zones
            ],
        }
    return data
