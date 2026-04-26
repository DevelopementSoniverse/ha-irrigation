"""Small pure helpers shared across modules."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import slugify


def normalize_device_ids(value: Any) -> list[str]:
    """Coerce a config value into a clean list of device ids.

    Accepts ``None``, a single id string, or an iterable of ids and always
    returns a list of non-empty strings in the original order.
    """
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(device_id) for device_id in value if device_id]


def mobile_app_notify_service(hass: HomeAssistant, device_id: str) -> str | None:
    """Resolve the ``notify.mobile_app_<slug>`` service for a mobile_app device.

    Returns ``None`` if the device cannot be found or no matching notify
    service is registered (e.g. the mobile app integration is not installed
    or the device was removed). Uses only public Home Assistant APIs.
    """
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        return None
    name = device.name_by_user or device.name
    if not name:
        return None
    service = f"mobile_app_{slugify(name)}"
    if not hass.services.has_service("notify", service):
        return None
    return service
