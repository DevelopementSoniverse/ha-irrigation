"""Constants for the Irrigation Computer integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irrigation_computer"

# Config Entry data keys (global)
CONF_DASHBOARD_LANGUAGE: Final = "dashboard_language"
CONF_PUSH_ALERT_DEVICE_IDS: Final = "push_alert_device_ids"
CONF_PUSH_ALERTS_ENABLED: Final = "push_alerts_enabled"
CONF_RADIATION_SOURCE_ENTITY: Final = "radiation_source_entity"
CONF_RADIATION_SOURCE_UNIT: Final = "radiation_source_unit"

# Dashboard language option values. "auto" follows hass.config.language;
# an explicit code overrides the server language for the Lovelace dashboard.
DASHBOARD_LANGUAGE_AUTO: Final = "auto"
DASHBOARD_LANGUAGES: Final = (DASHBOARD_LANGUAGE_AUTO, "en", "de", "th")
DEFAULT_DASHBOARD_LANGUAGE: Final = DASHBOARD_LANGUAGE_AUTO

# Options keys
OPT_ZONES: Final = "zones"

# Per-zone option keys
ZONE_ID: Final = "zone_id"
ZONE_NAME: Final = "name"
ZONE_RELAY_ENTITY: Final = "relay_entity_id"
ZONE_POWER_ENTITY: Final = "power_entity_id"
ZONE_WATERING_DURATION: Final = "watering_duration_sec"
ZONE_PHASE: Final = "phase"
ZONE_THRESHOLD_PLANTING: Final = "threshold_planting"
ZONE_THRESHOLD_FRUIT_SET: Final = "threshold_fruit_set"
ZONE_THRESHOLD_RIPENING: Final = "threshold_ripening"
ZONE_POWER_ALERT_DELAY: Final = "power_alert_delay_sec"
ZONE_POWER_MIN: Final = "power_min"
ZONE_POWER_MAX: Final = "power_max"
ZONE_MAX_RUNS_24H: Final = "max_runs_24h"
ZONE_FALLBACK_ENABLED: Final = "fallback_enabled"
ZONE_FALLBACK_MINUTES: Final = "fallback_minutes"
ZONE_FALLBACK_START: Final = "fallback_start"
ZONE_FALLBACK_END: Final = "fallback_end"
ZONE_RADIATION_TRIGGER_ENABLED: Final = "radiation_trigger_enabled"
ZONE_SOIL_MOISTURE_ENTITIES: Final = "soil_moisture_entity_ids"
ZONE_SOIL_MOISTURE_TRIGGER_ENABLED: Final = "soil_moisture_trigger_enabled"
ZONE_SOIL_MOISTURE_THRESHOLD: Final = "soil_moisture_threshold"
ZONE_SOIL_MOISTURE_DWELL_MINUTES: Final = "soil_moisture_dwell_minutes"
ZONE_MIN_INTERVAL_MINUTES: Final = "min_interval_minutes"

# Radiation units
UNIT_W_PER_M2: Final = "W/m²"
UNIT_WH_PER_M2: Final = "Wh/m²"
UNIT_PERCENT: Final = "%"

# Phase enum values (string).
# Displayed labels live in translations/*.json under
#   entity.select.phase.state.*  (entity state)
#   selector.phase.options.*     (config-flow selector)
# Keep both blocks in sync when adding/renaming phases.
PHASE_PLANTING: Final = "planting"
PHASE_FRUIT_SET: Final = "fruit_set"
PHASE_RIPENING: Final = "ripening"
PHASES: Final = (PHASE_PLANTING, PHASE_FRUIT_SET, PHASE_RIPENING)

# Reasons. Displayed labels live in translations/*.json under
# entity.sensor.last_reason.state.*. Keep in sync when adding/renaming reasons.
REASON_MANUAL: Final = "manual"
REASON_RADIATION: Final = "radiation"
REASON_FALLBACK: Final = "fallback"
REASON_MOISTURE: Final = "soil_moisture"
REASONS: Final = (REASON_MANUAL, REASON_RADIATION, REASON_FALLBACK, REASON_MOISTURE)

# Legacy -> current mapping for values persisted before snake_case migration.
# Read-side coercion in models.py keeps old config entries and runtime stores
# working without an explicit schema version bump.
LEGACY_PHASE_MAP: Final = {
    "Planting": PHASE_PLANTING,
    "Fruit Set": PHASE_FRUIT_SET,
    "Ripening": PHASE_RIPENING,
}
LEGACY_REASON_MAP: Final = {
    "Manual": REASON_MANUAL,
    "Radiation": REASON_RADIATION,
    "Fallback": REASON_FALLBACK,
    "Soil moisture": REASON_MOISTURE,
}

# Defaults
DEFAULT_PUSH_ALERTS_ENABLED: Final = False
DEFAULT_WATERING_DURATION: Final = 60
DEFAULT_THRESHOLD_PLANTING: Final = 50.0
DEFAULT_THRESHOLD_FRUIT_SET: Final = 100.0
DEFAULT_THRESHOLD_RIPENING: Final = 80.0
DEFAULT_POWER_ALERT_DELAY: Final = 0
DEFAULT_POWER_MIN: Final = 5.0
DEFAULT_POWER_MAX: Final = 500.0
DEFAULT_MAX_RUNS_24H: Final = 0
DEFAULT_FALLBACK_MINUTES: Final = 60
DEFAULT_FALLBACK_START: Final = "06:00:00"
DEFAULT_FALLBACK_END: Final = "20:00:00"
DEFAULT_RADIATION_SOURCE_UNIT: Final = UNIT_W_PER_M2
DEFAULT_SOIL_MOISTURE_THRESHOLD: Final = 30.0
DEFAULT_SOIL_MOISTURE_DWELL_MINUTES: Final = 15
DEFAULT_MIN_INTERVAL_MINUTES: Final = 30

# Coordinator
UPDATE_INTERVAL_SECONDS: Final = 30
WATCHDOG_GRACE_SECONDS: Final = 5
POWER_WAIT_SECONDS: Final = 30
RADIATION_STALE_SECONDS: Final = 2 * 60 * 60

# Services
SERVICE_START_ZONE: Final = "start_zone"
SERVICE_STOP_ZONE: Final = "stop_zone"
SERVICE_RESET_RADIATION: Final = "reset_radiation"
SERVICE_START_ALL: Final = "start_all"

ATTR_ZONE_ID: Final = "zone_id"
ATTR_REASON: Final = "reason"

# Notifications
NOTIFICATION_ID_PREFIX: Final = "irrigation_computer"

# Storage / persistence
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}.runtime"
