#!/usr/bin/env python3
"""Pre-provision a Home Assistant config dir for the integration test container.

Creates a working admin/admin user, marks onboarding as done, sets locale/units
and writes a pre-configured `irrigation_computer` config entry with two example
zones referencing the mock relays/sensors that the configuration.yaml exposes.

Idempotent: skips files that already exist so re-running doesn't clobber state.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

CONFIG = Path(sys.argv[1] if len(sys.argv) > 1 else "/config")
STORAGE = CONFIG / ".storage"
STORAGE.mkdir(parents=True, exist_ok=True)

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, obj: dict) -> None:
    if path.exists():
        print(f"[provision] {path.name} exists, skipping", flush=True)
        return
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    print(f"[provision] wrote {path.name}", flush=True)


# --- Auth ----------------------------------------------------------------

USER_ID = uuid.uuid4().hex
CRED_ID = uuid.uuid4().hex
ADMIN_GROUP_ID = "system-admin"
USER_GROUP_ID = "system-users"
READ_GROUP_ID = "system-read-only"

PASSWORD_HASH = base64.b64encode(
    bcrypt.hashpw(b"admin", bcrypt.gensalt(rounds=12))
).decode()

write_json(
    STORAGE / "auth",
    {
        "version": 1,
        "minor_version": 1,
        "key": "auth",
        "data": {
            "users": [
                {
                    "id": USER_ID,
                    "group_ids": [ADMIN_GROUP_ID],
                    "is_owner": True,
                    "is_active": True,
                    "name": "admin",
                    "system_generated": False,
                    "local_only": False,
                }
            ],
            "groups": [
                {"id": ADMIN_GROUP_ID, "name": "Administrators"},
                {"id": USER_GROUP_ID, "name": "Users"},
                {"id": READ_GROUP_ID, "name": "Read Only"},
            ],
            "credentials": [
                {
                    "id": CRED_ID,
                    "user_id": USER_ID,
                    "auth_provider_type": "homeassistant",
                    "auth_provider_id": None,
                    "data": {"username": "admin"},
                }
            ],
            "refresh_tokens": [],
        },
    },
)

write_json(
    STORAGE / "auth_provider.homeassistant",
    {
        "version": 1,
        "minor_version": 1,
        "key": "auth_provider.homeassistant",
        "data": {
            "users": [
                {
                    "username": "admin",
                    "password": PASSWORD_HASH,
                }
            ]
        },
    },
)

# --- Onboarding ----------------------------------------------------------

write_json(
    STORAGE / "onboarding",
    {
        "version": 4,
        "minor_version": 1,
        "key": "onboarding",
        "data": {
            "done": [
                "user",
                "core_config",
                "analytics",
                "integration",
            ]
        },
    },
)

# --- Core config (German, metric) ----------------------------------------

write_json(
    STORAGE / "core.config",
    {
        "version": 1,
        "minor_version": 4,
        "key": "core.config",
        "data": {
            "latitude": 52.0,
            "longitude": 9.0,
            "elevation": 100,
            "unit_system_v2": "metric",
            "location_name": "Test",
            "time_zone": "Europe/Berlin",
            "external_url": None,
            "internal_url": None,
            "currency": "EUR",
            "country": "DE",
            "language": "de",
            "radius": 100,
        },
    },
)

# --- Pre-baked config entry for irrigation_computer ----------------------

ENTRY_ID = "ic_demo_entry"
ZONE_A_ID = "zone_tomato_demo"
ZONE_B_ID = "zone_kraeuter_demo"

zones = [
    {
        "zone_id": ZONE_A_ID,
        "name": "Tomaten Hochbeet",
        "relay_entity_id": "switch.mock_relay_a",
        "power_entity_id": "sensor.mock_relay_a_power",
        "watering_duration_sec": 30,
        "phase": "Planting",
        "threshold_planting": 50.0,
        "threshold_fruit_set": 100.0,
        "threshold_ripening": 80.0,
        "power_min": 5.0,
        "power_max": 500.0,
        "fallback_enabled": True,
        "fallback_minutes": 60,
        "fallback_start": "06:00:00",
        "fallback_end": "20:00:00",
        "radiation_trigger_enabled": True,
    },
    {
        "zone_id": ZONE_B_ID,
        "name": "Kraeuter",
        "relay_entity_id": "switch.mock_relay_b",
        "power_entity_id": "sensor.mock_relay_b_power",
        "watering_duration_sec": 20,
        "phase": "Fruit Set",
        "threshold_planting": 40.0,
        "threshold_fruit_set": 90.0,
        "threshold_ripening": 70.0,
        "power_min": 5.0,
        "power_max": 500.0,
        "fallback_enabled": True,
        "fallback_minutes": 90,
        "fallback_start": "06:00:00",
        "fallback_end": "20:00:00",
        "radiation_trigger_enabled": True,
    },
]

write_json(
    STORAGE / "core.config_entries",
    {
        "version": 1,
        "minor_version": 5,
        "key": "core.config_entries",
        "data": {
            "entries": [
                {
                    "entry_id": ENTRY_ID,
                    "version": 1,
                    "minor_version": 1,
                    "domain": "irrigation_computer",
                    "title": "Irrigation Computer",
                    "data": {
                        "radiation_source_entity": "sensor.mock_solar_radiation",
                        "radiation_source_unit": "W/m²",
                    },
                    "options": {"zones": zones},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "user",
                    "unique_id": None,
                    "disabled_by": None,
                    "discovery_keys": {},
                    "created_at": NOW,
                    "modified_at": NOW,
                    "subentries": [],
                }
            ]
        },
    },
)


# --- Example dashboard ----------------------------------------------------

DASHBOARD = {
    "version": 1,
    "minor_version": 1,
    "key": "lovelace.irrigation",
    "data": {
        "config": {
            "auto_managed_by_irrigation_computer": True,
            "title": "Irrigation Computer",
            "views": [
                {
                    "title": "Zonen",
                    "path": "zones",
                    "icon": "mdi:sprinkler-variant",
                    "cards": [
                        {
                            "type": "vertical-stack",
                            "title": "Mock-Steuerung",
                            "cards": [
                                {
                                    "type": "entities",
                                    "title": "Mock-Sensoren / Relais",
                                    "entities": [
                                        "sensor.mock_solar_radiation",
                                        "input_number.mock_solar_radiation_w_m2",
                                        "switch.mock_relay_a",
                                        "switch.mock_relay_b",
                                        "sensor.mock_relay_a_power",
                                        "sensor.mock_relay_b_power",
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "vertical-stack",
                            "title": "Tomaten Hochbeet",
                            "cards": [
                                {
                                    "type": "entities",
                                    "entities": [
                                        "binary_sensor.tomaten_hochbeet_running",
                                        "switch.tomaten_hochbeet_run",
                                        "button.tomaten_hochbeet_start_irrigation",
                                        "button.tomaten_hochbeet_stop_irrigation",
                                        "sensor.tomaten_hochbeet_time_since_last_irrigation",
                                        "sensor.tomaten_hochbeet_radiation_since_last_irrigation",
                                        "sensor.tomaten_hochbeet_current_radiation_threshold",
                                        "sensor.tomaten_hochbeet_current_power",
                                        "sensor.tomaten_hochbeet_runs_24h",
                                        "sensor.tomaten_hochbeet_last_run",
                                        "sensor.tomaten_hochbeet_last_reason",
                                        "binary_sensor.tomaten_hochbeet_fallback_active",
                                        "binary_sensor.tomaten_hochbeet_relay_available",
                                        "binary_sensor.tomaten_hochbeet_relay_error",
                                        "select.tomaten_hochbeet_growth_phase",
                                        "number.tomaten_hochbeet_watering_duration",
                                        "number.tomaten_hochbeet_threshold_planting",
                                        "number.tomaten_hochbeet_threshold_fruit_set",
                                        "number.tomaten_hochbeet_threshold_ripening",
                                        "number.tomaten_hochbeet_undercurrent_threshold",
                                        "number.tomaten_hochbeet_overcurrent_threshold",
                                        "number.tomaten_hochbeet_fallback_interval",
                                        "time.tomaten_hochbeet_fallback_start",
                                        "time.tomaten_hochbeet_fallback_end",
                                        "switch.tomaten_hochbeet_fallback_enabled",
                                        "switch.tomaten_hochbeet_radiation_trigger_enabled",
                                        "button.tomaten_hochbeet_reset_radiation_counter",
                                    ],
                                }
                            ],
                        },
                        {
                            "type": "vertical-stack",
                            "title": "Kraeuter",
                            "cards": [
                                {
                                    "type": "entities",
                                    "entities": [
                                        "binary_sensor.kraeuter_running",
                                        "switch.kraeuter_run",
                                        "button.kraeuter_start_irrigation",
                                        "button.kraeuter_stop_irrigation",
                                        "sensor.kraeuter_time_since_last_irrigation",
                                        "sensor.kraeuter_radiation_since_last_irrigation",
                                        "sensor.kraeuter_current_radiation_threshold",
                                        "sensor.kraeuter_current_power",
                                        "sensor.kraeuter_runs_24h",
                                        "sensor.kraeuter_last_run",
                                        "sensor.kraeuter_last_reason",
                                        "binary_sensor.kraeuter_fallback_active",
                                        "binary_sensor.kraeuter_relay_available",
                                        "binary_sensor.kraeuter_relay_error",
                                        "select.kraeuter_growth_phase",
                                        "number.kraeuter_watering_duration",
                                        "number.kraeuter_threshold_planting",
                                        "number.kraeuter_threshold_fruit_set",
                                        "number.kraeuter_threshold_ripening",
                                        "number.kraeuter_undercurrent_threshold",
                                        "number.kraeuter_overcurrent_threshold",
                                        "number.kraeuter_fallback_interval",
                                        "time.kraeuter_fallback_start",
                                        "time.kraeuter_fallback_end",
                                        "switch.kraeuter_fallback_enabled",
                                        "switch.kraeuter_radiation_trigger_enabled",
                                        "button.kraeuter_reset_radiation_counter",
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
    },
}

write_json(STORAGE / "lovelace.irrigation", DASHBOARD)

write_json(
    STORAGE / "lovelace_dashboards",
    {
        "version": 1,
        "minor_version": 2,
        "key": "lovelace_dashboards",
        "data": {
            "items": [
                {
                    "id": "irrigation",
                    "icon": "mdi:sprinkler-variant",
                    "title": "Irrigation Computer",
                    "url_path": "irrigation",
                    "require_admin": False,
                    "show_in_sidebar": True,
                    "mode": "storage",
                }
            ]
        },
    },
)

print("[provision] done", flush=True)
