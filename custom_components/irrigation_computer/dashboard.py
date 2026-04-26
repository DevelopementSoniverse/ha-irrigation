"""Auto-generated Lovelace dashboard for the Irrigation Computer integration.

Whenever the integration is set up or its options change (i.e. zones are
added / removed / edited), this module rebuilds the "Irrigation Computer"
dashboard so it always reflects the current set of zones – without forcing
the user to edit YAML.

A marker key ``AUTO_MANAGED_KEY`` is stored alongside the dashboard config.
If the user removes it (e.g. by manually editing the dashboard), the
integration leaves the dashboard alone on subsequent updates.

Lovelace storage dashboards are plain JSON and are NOT run through Home
Assistant's entity translation system. We therefore localise visible labels
(card titles, button captions, gauge names) at build time using
``hass.config.language`` and rebuild the dashboard when the language changes
(see ``__init__.py``).
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_DASHBOARD_LANGUAGE,
    DASHBOARD_LANGUAGE_AUTO,
    DEFAULT_DASHBOARD_LANGUAGE,
)
from .coordinator import IrrigationController
from .models import ZoneConfig

_LOGGER = logging.getLogger(__name__)

DASHBOARD_URL_PATH = "irrigation"
LOVELACE_DATA_KEY = "lovelace"
AUTO_MANAGED_KEY = "auto_managed_by_irrigation_computer"

# Built-in dashboard labels per language. English is the fallback for any
# unsupported locale; add new languages by extending this mapping.
_DASHBOARD_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "dashboard_title": "Irrigation Computer",
        "view_zones_title": "Zones",
        "controller_card_title": "Controller",
        "radiation_gauge_suffix": "Radiation since last irrigation",
        "moisture_gauge_suffix": "Average soil moisture",
        "gauge_irrigation_label": "Irrigation",
        "action_start": "Start",
        "action_stop": "Stop",
        "action_settings": "Settings",
        "metric_power": "Power",
        "metric_time_since_last": "Since last irrigation",
        "metric_runs_24h": "Runs 24 h",
        "settings_view_suffix": "Settings",
        "card_status": "Status",
        "card_irrigation": "Irrigation",
        "card_crop_radiation": "Crop & radiation",
        "card_alerts_safety": "Alerts & safety",
        "card_fallback": "Fallback",
        "card_soil_moisture": "Soil moisture",
        "empty_markdown": (
            "## No zones configured\n\n"
            "Please add a first zone via *Settings → Devices & Services → "
            "Irrigation Computer → Configure → Add zone*."
        ),
    },
    "de": {
        "dashboard_title": "Bewässerungscomputer",
        "view_zones_title": "Zonen",
        "controller_card_title": "Controller",
        "radiation_gauge_suffix": "Strahlung seit letzter Bewässerung",
        "moisture_gauge_suffix": "Mittlere Bodenfeuchte",
        "gauge_irrigation_label": "Bewässerung",
        "action_start": "Start",
        "action_stop": "Stopp",
        "action_settings": "Einstellungen",
        "metric_power": "Leistung",
        "metric_time_since_last": "Seit letzter Bewässerung",
        "metric_runs_24h": "Läufe 24 h",
        "settings_view_suffix": "Einstellungen",
        "card_status": "Status",
        "card_irrigation": "Bewässerung",
        "card_crop_radiation": "Kulturart & Strahlung",
        "card_alerts_safety": "Alerts & Sicherheit",
        "card_fallback": "Fallback",
        "card_soil_moisture": "Bodenfeuchte",
        "empty_markdown": (
            "## Keine Zonen konfiguriert\n\n"
            "Bitte über *Einstellungen → Geräte & Dienste → "
            "Irrigation Computer → Konfigurieren → Zone hinzufügen* "
            "eine erste Zone anlegen."
        ),
    },
    "th": {
        "dashboard_title": "คอมพิวเตอร์ชลประทาน",
        "view_zones_title": "โซน",
        "controller_card_title": "ตัวควบคุม",
        "radiation_gauge_suffix": "รังสีตั้งแต่รดน้ำครั้งล่าสุด",
        "moisture_gauge_suffix": "ความชื้นดินเฉลี่ย",
        "gauge_irrigation_label": "รดน้ำ",
        "action_start": "เริ่ม",
        "action_stop": "หยุด",
        "action_settings": "ตั้งค่า",
        "metric_power": "กำลังไฟ",
        "metric_time_since_last": "ตั้งแต่รดน้ำครั้งล่าสุด",
        "metric_runs_24h": "จำนวนรอบ 24 ชม.",
        "settings_view_suffix": "ตั้งค่า",
        "card_status": "สถานะ",
        "card_irrigation": "รดน้ำ",
        "card_crop_radiation": "พืชและรังสี",
        "card_alerts_safety": "การแจ้งเตือนและความปลอดภัย",
        "card_fallback": "Fallback",
        "card_soil_moisture": "ความชื้นดิน",
        "empty_markdown": (
            "## ยังไม่ได้กำหนดค่าโซน\n\n"
            "กรุณาเพิ่มโซนแรกผ่าน *การตั้งค่า → อุปกรณ์และบริการ → "
            "คอมพิวเตอร์ชลประทาน → กำหนดค่า → เพิ่มโซน*"
        ),
    },
}


def _active_language(
    hass: HomeAssistant, controller: IrrigationController
) -> str:
    """Resolve the effective dashboard language.

    Priority:
    1. Explicit ``CONF_DASHBOARD_LANGUAGE`` option on the config entry
       (values other than ``"auto"`` win).
    2. ``hass.config.language`` (server language), region stripped.
    3. ``"en"`` fallback.
    """
    entry = controller.entry
    configured = entry.options.get(
        CONF_DASHBOARD_LANGUAGE,
        entry.data.get(CONF_DASHBOARD_LANGUAGE, DEFAULT_DASHBOARD_LANGUAGE),
    )
    if configured and configured != DASHBOARD_LANGUAGE_AUTO:
        return str(configured)
    server = (getattr(hass.config, "language", None) or "en").split("-")[0]
    return server


def _t(lang: str, key: str) -> str:
    """Return a dashboard label for an already-resolved language code.

    Falls back to English if the language is not explicitly supported or
    the key is missing in the requested language.
    """
    bundle = _DASHBOARD_STRINGS.get(lang) or _DASHBOARD_STRINGS["en"]
    return bundle.get(key) or _DASHBOARD_STRINGS["en"].get(key, key)


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
    hass: HomeAssistant, entity_id: str, threshold: float, zone_name: str
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
        "name": f"{zone_name}: {_t(hass, 'radiation_gauge_suffix')}",
        "needle": True,
        "min": 0,
        "max": gauge_max,
        "segments": [
            {"from": 0, "color": "#9e9e9e"},
            {
                "from": safe_threshold,
                "color": "#00bcd4",
                "label": _t(hass, "gauge_irrigation_label"),
            },
        ],
    }


def _moisture_gauge_card(
    hass: HomeAssistant, entity_id: str, threshold: float, zone_name: str
) -> dict[str, Any]:
    """Return a gauge card visualising the zone's average soil moisture.

    The blue segment marks the range in which irrigation starts (i.e. the
    moisture has fallen at or below the configured threshold), mirroring
    the semantics of the radiation gauge where the blue band also marks
    'irrigation about to fire'.
    """
    safe_threshold = max(min(float(threshold), 100.0), 0.0)
    return {
        "type": "gauge",
        "entity": entity_id,
        "name": f"{zone_name}: {_t(hass, 'moisture_gauge_suffix')}",
        "needle": True,
        "min": 0,
        "max": 100,
        "segments": [
            {
                "from": 0,
                "color": "#00bcd4",
                "label": _t(hass, "gauge_irrigation_label"),
            },
            {"from": safe_threshold, "color": "#9e9e9e"},
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
    moisture_eid = entity_map.get("average_soil_moisture")

    gauges: list[dict[str, Any]] = []
    if zone.radiation_trigger_enabled:
        gauges.append(
            _radiation_gauge_card(
                hass, radiation_eid, zone.current_threshold(), zone.name
            )
        )
    if (
        zone.soil_moisture_trigger_enabled
        and zone.soil_moisture_entity_ids
        and moisture_eid is not None
    ):
        gauges.append(
            _moisture_gauge_card(
                hass, moisture_eid, zone.soil_moisture_threshold, zone.name
            )
        )

    cards: list[dict[str, Any]] = []
    if len(gauges) == 1:
        cards.append(gauges[0])
    elif len(gauges) >= 2:
        cards.append({"type": "horizontal-stack", "cards": gauges})

    cards.append(
        {
            "type": "grid",
            "columns": 3,
            "square": False,
            "cards": [
                _action_button_card(
                    name=_t(hass, "action_start"),
                    icon="mdi:play",
                    action="button.press",
                    target_entity_id=start_button,
                )
                if start_button
                else {"type": "markdown", "content": ""},
                _action_button_card(
                    name=_t(hass, "action_stop"),
                    icon="mdi:stop",
                    action="button.press",
                    target_entity_id=stop_button,
                )
                if stop_button
                else {"type": "markdown", "content": ""},
                _action_button_card(
                    name=_t(hass, "action_settings"),
                    icon="mdi:cog-outline",
                    action="navigate",
                    navigation_path=f"/{DASHBOARD_URL_PATH}/{_zone_view_path(zone)}",
                ),
            ],
        }
    )

    metric_cards: list[dict[str, Any]] = []
    if current_power:
        metric_cards.append(
            _metric_tile_card(current_power, _t(hass, "metric_power"), "mdi:flash")
        )
    if time_since:
        metric_cards.append(
            _metric_tile_card(
                time_since,
                _t(hass, "metric_time_since_last"),
                "mdi:clock-outline",
            )
        )
    if runs_24h:
        metric_cards.append(
            _metric_tile_card(
                runs_24h, _t(hass, "metric_runs_24h"), "mdi:counter"
            )
        )

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
            _t(hass, "card_status"),
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
            _t(hass, "card_irrigation"),
            [
                entity_map.get("running_switch"),
                entity_map.get("watering_duration_sec"),
                entity_map.get("start_button"),
                entity_map.get("stop_button"),
            ],
        ),
        _entities_card(
            _t(hass, "card_crop_radiation"),
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
            _t(hass, "card_alerts_safety"),
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
            _t(hass, "card_fallback"),
            [
                entity_map.get("fallback_enabled"),
                entity_map.get("fallback_active"),
                entity_map.get("fallback_minutes"),
                entity_map.get("fallback_start"),
                entity_map.get("fallback_end"),
            ],
        ),
        _entities_card(
            _t(hass, "card_soil_moisture"),
            [
                entity_map.get("soil_moisture_trigger_enabled"),
                entity_map.get("average_soil_moisture"),
                entity_map.get("soil_moisture_threshold"),
                entity_map.get("soil_moisture_dwell_minutes"),
                entity_map.get("min_interval_minutes"),
                *list(zone.soil_moisture_entity_ids),
            ],
        ),
    ]

    return {
        "title": f"{zone.name} {_t(hass, 'settings_view_suffix')}",
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
                "title": _t(hass, "controller_card_title"),
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
                "content": _t(hass, "empty_markdown"),
            }
        )

    return {
        AUTO_MANAGED_KEY: True,
        "title": _t(hass, "dashboard_title"),
        "views": [
            {
                "title": _t(hass, "view_zones_title"),
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
