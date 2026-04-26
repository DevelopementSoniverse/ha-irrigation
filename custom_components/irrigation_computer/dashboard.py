"""Auto-generated Lovelace dashboard for the Irrigation Computer integration.

Whenever the integration is set up or its options change (i.e. zones are
added / removed / edited), this module rebuilds the "Irrigation Computer"
dashboard so it always reflects the current set of zones – without forcing
the user to edit YAML.

A marker key ``AUTO_MANAGED_KEY`` is stored alongside the dashboard config.
If the user removes it (e.g. by manually editing the dashboard), the
integration leaves the dashboard alone on subsequent updates.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .coordinator import IrrigationController
from .models import ZoneConfig

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "irrigation"
LOVELACE_DATA_KEY = "lovelace"
AUTO_MANAGED_KEY = "auto_managed_by_irrigation_computer"


def _zone_entity_map(
    hass: HomeAssistant, controller: IrrigationController, zone: ZoneConfig
) -> dict[str, str]:
    """Return ``{entity_key: entity_id}`` for the given zone.

    ``entity_key`` is the suffix used by each platform when constructing
    ``unique_id`` (see ``entity.py``: ``f"{entry_id}_{zone_id}_{key}"``).
    """
    ent_reg = er.async_get(hass)
    prefix = f"{controller.entry.entry_id}_{zone.zone_id}_"
    out: dict[str, str] = {}
    for e in ent_reg.entities.values():
        uid = e.unique_id or ""
        if e.config_entry_id == controller.entry.entry_id and uid.startswith(prefix):
            out[uid[len(prefix):]] = e.entity_id
    return out


def _zone_entities(
    hass: HomeAssistant, controller: IrrigationController, zone: ZoneConfig
) -> list[str]:
    """Return all entity_ids belonging to a zone, ordered by platform."""
    ent_reg = er.async_get(hass)
    prefix = f"{controller.entry.entry_id}_{zone.zone_id}_"
    # Sort by domain to get a clean grouping in the entities card.
    domain_order = {
        "binary_sensor": 0,
        "switch": 1,
        "button": 2,
        "sensor": 3,
        "select": 4,
        "number": 5,
        "time": 6,
    }
    entries = [
        e
        for e in ent_reg.entities.values()
        if e.config_entry_id == controller.entry.entry_id
        and (e.unique_id or "").startswith(prefix)
    ]
    entries.sort(
        key=lambda e: (
            domain_order.get(e.entity_id.split(".")[0], 99),
            e.entity_id,
        )
    )
    return [e.entity_id for e in entries]


def _radiation_gauge_card(
    entity_id: str, threshold: float, zone_name: str
) -> dict[str, Any]:
    """Return a Lovelace gauge card mirroring the original YAML dashboard.

    Native HA gauge does not support templated min/max/segments in storage
    mode, so we materialise the current threshold here.  The dashboard is
    rebuilt automatically whenever the integration reloads (e.g. on phase
    change), so the gauge stays in sync with the active phase.
    """
    safe_threshold = max(float(threshold), 1.0)
    gauge_max = round(safe_threshold + 10.0, 1)
    return {
        "type": "gauge",
        "entity": entity_id,
        "name": f"{zone_name}: Strahlung seit letzter Bewässerung",
        "needle": True,
        "min": 0,
        "max": gauge_max,
        "segments": [
            {"from": 0, "color": "#9e9e9e"},
            {"from": safe_threshold, "color": "#00bcd4", "label": "Irrigation"},
        ],
    }


def _zone_view_path(zone: ZoneConfig) -> str:
    """Return stable Lovelace subview path for a zone."""
    return f"zone-{zone.zone_id[:8]}"


def _action_button_card(
    *,
    name: str,
    icon: str,
    action: str,
    target_entity_id: str | None = None,
    navigation_path: str | None = None,
) -> dict[str, Any]:
    """Return a Lovelace button card for a service action or navigation."""
    card: dict[str, Any] = {
        "type": "button",
        "name": name,
        "icon": icon,
        "show_state": False,
    }
    if action == "navigate" and navigation_path:
        card["tap_action"] = {
            "action": "navigate",
            "navigation_path": navigation_path,
        }
        return card

    if target_entity_id is not None:
        card["tap_action"] = {
            "action": "perform-action",
            "perform_action": action,
            "target": {"entity_id": target_entity_id},
        }
    return card


def _metric_tile_card(entity_id: str, name: str, icon: str) -> dict[str, Any]:
    """Return compact tile card for an operational metric."""
    return {
        "type": "tile",
        "entity": entity_id,
        "name": name,
        "icon": icon,
        "vertical": False,
        "hide_state": False,
    }


def _entities_card(title: str, entity_ids: list[str | None]) -> dict[str, Any] | None:
    """Return an entities card with missing entities removed."""
    entities = [entity_id for entity_id in entity_ids if entity_id is not None]
    if not entities:
        return None
    return {
        "type": "entities",
        "title": title,
        "show_header_toggle": False,
        "entities": entities,
    }


def _zone_overview_stack(
    hass: HomeAssistant, controller: IrrigationController, zone: ZoneConfig
) -> dict[str, Any] | None:
    """Build the main dashboard stack for one zone."""
    entity_map = _zone_entity_map(hass, controller, zone)
    radiation_eid = entity_map.get("radiation_since_last_irrigation")
    if radiation_eid is None:
        return None

    start_button = entity_map.get("start_button")
    stop_button = entity_map.get("stop_button")
    current_power = entity_map.get("current_power")
    time_since = entity_map.get("time_since_last_irrigation")
    runs_24h = entity_map.get("runs_24h")

    cards: list[dict[str, Any]] = [
        _radiation_gauge_card(radiation_eid, zone.current_threshold(), zone.name),
        {
            "type": "grid",
            "columns": 3,
            "square": False,
            "cards": [
                _action_button_card(
                    name="Start",
                    icon="mdi:play",
                    action="button.press",
                    target_entity_id=start_button,
                )
                if start_button
                else {"type": "markdown", "content": ""},
                _action_button_card(
                    name="Stop",
                    icon="mdi:stop",
                    action="button.press",
                    target_entity_id=stop_button,
                )
                if stop_button
                else {"type": "markdown", "content": ""},
                _action_button_card(
                    name="Einstellungen",
                    icon="mdi:cog-outline",
                    action="navigate",
                    navigation_path=f"/{DASHBOARD_URL_PATH}/{_zone_view_path(zone)}",
                ),
            ],
        },
    ]

    metric_cards: list[dict[str, Any]] = []
    if current_power:
        metric_cards.append(
            _metric_tile_card(current_power, "Leistung", "mdi:flash")
        )
    if time_since:
        metric_cards.append(
            _metric_tile_card(
                time_since, "Seit letzter Bewässerung", "mdi:clock-outline"
            )
        )
    if runs_24h:
        metric_cards.append(_metric_tile_card(runs_24h, "Runs 24 h", "mdi:counter"))

    if metric_cards:
        cards.append(
            {
                "type": "grid",
                "columns": 3,
                "square": False,
                "cards": metric_cards,
            }
        )

    return {
        "type": "vertical-stack",
        "cards": [
            {
                "type": "markdown",
                "content": f"## {zone.name}",
            },
            *cards,
        ],
    }


def _zone_settings_view(
    hass: HomeAssistant, controller: IrrigationController, zone: ZoneConfig
) -> dict[str, Any]:
    """Build per-zone settings subview opened via the gear button."""
    entity_map = _zone_entity_map(hass, controller, zone)

    cards = [
        _entities_card(
            "Status",
            [
                entity_map.get("running"),
                entity_map.get("relay_available"),
                entity_map.get("current_power"),
                entity_map.get("last_run"),
                entity_map.get("last_reason"),
                entity_map.get("time_since_last_irrigation"),
            ],
        ),
        _entities_card(
            "Bewässerung",
            [
                entity_map.get("running_switch"),
                entity_map.get("watering_duration_sec"),
                entity_map.get("start_button"),
                entity_map.get("stop_button"),
            ],
        ),
        _entities_card(
            "Kulturart & Strahlung",
            [
                entity_map.get("phase"),
                entity_map.get("threshold_planting"),
                entity_map.get("threshold_fruit_set"),
                entity_map.get("threshold_ripening"),
                entity_map.get("current_radiation_threshold"),
                entity_map.get("radiation_since_last_irrigation"),
                entity_map.get("radiation_trigger_enabled"),
                entity_map.get("reset_radiation_button"),
            ],
        ),
        _entities_card(
            "Alerts & Sicherheit",
            [
                entity_map.get("power_alert_delay_sec"),
                entity_map.get("power_min"),
                entity_map.get("power_max"),
                entity_map.get("max_runs_24h"),
                entity_map.get("runs_24h"),
                entity_map.get("relay_error"),
            ],
        ),
        _entities_card(
            "Fallback",
            [
                entity_map.get("fallback_enabled"),
                entity_map.get("fallback_active"),
                entity_map.get("fallback_minutes"),
                entity_map.get("fallback_start"),
                entity_map.get("fallback_end"),
            ],
        ),
    ]

    return {
        "title": f"{zone.name} Einstellungen",
        "path": _zone_view_path(zone),
        "subview": True,
        "icon": "mdi:cog-outline",
        "cards": [card for card in cards if card is not None],
    }


def _controller_entities(
    hass: HomeAssistant, controller: IrrigationController
) -> list[str]:
    """Return entity_ids for controller-level entities (non-zone)."""
    ent_reg = er.async_get(hass)
    prefix = f"{controller.entry.entry_id}_controller_"
    return sorted(
        e.entity_id
        for e in ent_reg.entities.values()
        if e.config_entry_id == controller.entry.entry_id
        and (e.unique_id or "").startswith(prefix)
    )


def _build_dashboard_config(
    hass: HomeAssistant, controller: IrrigationController
) -> dict[str, Any]:
    """Build a fresh dashboard config from current state."""
    cards: list[dict[str, Any]] = []
    views: list[dict[str, Any]] = []

    # Controller-level card (global radiation energy, etc.)
    controller_entities = _controller_entities(hass, controller)
    if controller_entities or controller.radiation_source_entity:
        controller_card_entities: list[str] = []
        if controller.radiation_source_entity:
            controller_card_entities.append(controller.radiation_source_entity)
        controller_card_entities.extend(controller_entities)
        cards.append(
            {
                "type": "entities",
                "title": "Controller",
                "entities": controller_card_entities,
            }
        )

    # One card per zone.
    for zone in controller.zones:
        zone_card = _zone_overview_stack(hass, controller, zone)
        if zone_card is None:
            continue
        cards.append(zone_card)
        views.append(_zone_settings_view(hass, controller, zone))

    if not cards:
        cards.append(
            {
                "type": "markdown",
                "content": (
                    "## Keine Zonen konfiguriert\n\n"
                    "Bitte über *Einstellungen → Geräte & Dienste → "
                    "Irrigation Computer → Konfigurieren → Zone hinzufügen* "
                    "eine erste Zone anlegen."
                ),
            }
        )

    return {
        AUTO_MANAGED_KEY: True,
        "title": "Irrigation Computer",
        "views": [
            {
                "title": "Zonen",
                "path": "zones",
                "icon": "mdi:sprinkler-variant",
                "cards": cards,
            },
            *views,
        ],
    }


async def async_update_dashboard(
    hass: HomeAssistant, controller: IrrigationController
) -> None:
    """Rebuild the dashboard if it exists and is auto-managed.

    Silently no-ops when:
    - the lovelace integration isn't loaded yet,
    - no dashboard with our URL path exists (we don't auto-create dashboards
      to avoid surprising the user),
    - the existing dashboard had its ``AUTO_MANAGED_KEY`` marker removed
      (user opt-out).
    """
    lovelace_data = hass.data.get(LOVELACE_DATA_KEY)
    if lovelace_data is None:
        return

    dashboards = getattr(lovelace_data, "dashboards", None)
    if not dashboards:
        return

    storage = dashboards.get(DASHBOARD_URL_PATH)
    if storage is None:
        # Dashboard doesn't exist yet (e.g. fresh HACS install).  Don't
        # auto-create – the user can add a "Storage" dashboard with URL
        # path "irrigation" via the UI and we'll start managing it on the
        # next reload.
        _LOGGER.debug(
            "Dashboard '%s' not found – skipping auto-update",
            DASHBOARD_URL_PATH,
        )
        return

    # Read existing config to honour the user opt-out.
    try:
        existing = await storage.async_load(False)
    except Exception:  # noqa: BLE001 (ConfigNotFound and friends)
        existing = None

    if existing is not None and not existing.get(AUTO_MANAGED_KEY, False):
        _LOGGER.debug(
            "Dashboard '%s' is no longer auto-managed (marker removed) – "
            "leaving it untouched",
            DASHBOARD_URL_PATH,
        )
        return

    new_config = _build_dashboard_config(hass, controller)
    try:
        await storage.async_save(new_config)
        _LOGGER.info(
            "Rebuilt dashboard '%s' with %d card(s)",
            DASHBOARD_URL_PATH,
            len(new_config["views"][0]["cards"]),
        )
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to update dashboard '%s'", DASHBOARD_URL_PATH)
