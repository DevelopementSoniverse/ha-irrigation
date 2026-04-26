"""Constants for the Irrigation Computer integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "irrigation_computer"

# Config Entry data keys (global)
CONF_RADIATION_SOURCE_ENTITY: Final = "radiation_source_entity"
CONF_RADIATION_SOURCE_UNIT: Final = "radiation_source_unit"

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
ZONE_POWER_MIN: Final = "power_min"
ZONE_POWER_MAX: Final = "power_max"
ZONE_FALLBACK_ENABLED: Final = "fallback_enabled"
ZONE_FALLBACK_MINUTES: Final = "fallback_minutes"
ZONE_FALLBACK_START: Final = "fallback_start"
ZONE_FALLBACK_END: Final = "fallback_end"
ZONE_RADIATION_TRIGGER_ENABLED: Final = "radiation_trigger_enabled"

# Radiation units
UNIT_W_PER_M2: Final = "W/m²"
UNIT_WH_PER_M2: Final = "Wh/m²"

# Phase enum values (string)
PHASE_PLANTING: Final = "Planting"
PHASE_FRUIT_SET: Final = "Fruit Set"
PHASE_RIPENING: Final = "Ripening"
PHASES: Final = (PHASE_PLANTING, PHASE_FRUIT_SET, PHASE_RIPENING)

# Reasons
REASON_MANUAL: Final = "Manual"
REASON_RADIATION: Final = "Radiation"
REASON_FALLBACK: Final = "Fallback"
REASONS: Final = (REASON_MANUAL, REASON_RADIATION, REASON_FALLBACK)

# Defaults
DEFAULT_WATERING_DURATION: Final = 60
DEFAULT_THRESHOLD_PLANTING: Final = 50.0
DEFAULT_THRESHOLD_FRUIT_SET: Final = 100.0
DEFAULT_THRESHOLD_RIPENING: Final = 80.0
DEFAULT_POWER_MIN: Final = 5.0
DEFAULT_POWER_MAX: Final = 500.0
DEFAULT_FALLBACK_MINUTES: Final = 60
DEFAULT_FALLBACK_START: Final = "06:00:00"
DEFAULT_FALLBACK_END: Final = "20:00:00"
DEFAULT_RADIATION_SOURCE_UNIT: Final = UNIT_W_PER_M2

# Coordinator
UPDATE_INTERVAL_SECONDS: Final = 30
WATCHDOG_GRACE_SECONDS: Final = 5
POWER_WAIT_SECONDS: Final = 30

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
