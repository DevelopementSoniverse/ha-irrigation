# Migration: YAML package → `irrigation_computer` integration

This document maps every artefact of the original
`packages/irrigation_calculator/` setup to its replacement inside the new
custom integration. Once the integration is configured for all your zones,
the old YAML files can be removed.

## High-level changes

- **Single zone → multi zone.** Zones are now first-class objects with an
  individual relay, power sensor and configuration. There is no global "the
  irrigation relay" anymore.
- **No string-based auto-derive.** The relay's matching power sensor is set
  explicitly per zone (with optional automatic fallback to
  `sensor.<switch_name>_power`).
- **No more `input_*` helpers.** Every knob is exposed as a proper
  Number / Select / Time / Switch entity tied to its zone device.
- **Internal radiation accumulator.** The previous Riemann-`integration`
  + `utility_meter` combo is replaced by an in-process trapezoidal
  accumulator on the controller. Each zone stores the accumulator value at
  the moment of its last run, so the per-zone "radiation since last
  irrigation" counter survives restarts and never needs `utility_meter.reset`.

## Mapping table

| Old (YAML package)                                            | New (this integration)                                              |
|---------------------------------------------------------------|---------------------------------------------------------------------|
| `input_select.irrigation_relay_entity`                        | per-zone field `relay_entity_id` (set in options flow)              |
| `input_number.watering_duration_sec`                          | `number.<zone>_watering_duration`                                   |
| `input_number.threshold_rad_phase1` / `_phase2` / `_phase3`   | `number.<zone>_threshold_planting` / `_fruit_set` / `_ripening`     |
| `input_select.tomato_phase`                                   | `select.<zone>_growth_phase` (per zone)                             |
| `input_number.irrigation_relais1_power_min` / `_power_max`    | `number.<zone>_undercurrent_threshold` / `_overcurrent_threshold`   |
| `input_boolean.irrigation_fallback_enabled`                   | `switch.<zone>_fallback_enabled`                                    |
| `input_number.irrigation_fallback_minutes`                    | `number.<zone>_fallback_interval`                                   |
| `input_datetime.irrigation_fallback_start` / `_end`           | `time.<zone>_fallback_start` / `_fallback_end`                      |
| `input_datetime.irrigation_last_run`                          | `sensor.<zone>_last_run` (timestamp, persisted internally)          |
| `input_select.irrigation_last_reason`                         | `sensor.<zone>_last_reason`                                         |
| `script.irrigation_run` / `irrigation_run_manual`             | `button.<zone>_start_irrigation`, service `irrigation_computer.start_zone`, switch `switch.<zone>_run` |
| `sensor.radiation_threshold_current`                          | `sensor.<zone>_current_radiation_threshold`                         |
| `sensor.time_since_last_irrigation_min`                       | `sensor.<zone>_time_since_last_irrigation`                          |
| `binary_sensor.irrigation_fallback_active`                    | `binary_sensor.<zone>_fallback_active`                              |
| `sensor.irrigation_power`                                     | `sensor.<zone>_current_power` (auto-derived if `power_entity_id` blank) |
| `sensor.global_radiation_energy` (Riemann integration)        | controller-level `sensor.irrigation_global_radiation_energy`        |
| `utility_meter.radiation_since_irrigation`                    | `sensor.<zone>_radiation_since_last_irrigation` (per zone)          |
| `sensor.irrigation_runs_24h` (history_stats)                  | `sensor.<zone>_runs_24h` (counted in the coordinator)               |

## Automation mapping

| Old automation                                  | Replacement                                                  |
|-------------------------------------------------|--------------------------------------------------------------|
| `irrigation_relay_dropdown_sync`                | Removed. The options flow uses an `EntitySelector(domain=switch)`. |
| `irrigation_by_radiation`                       | Built into the coordinator's update tick.                    |
| `irrigation_by_fallback`                        | Built into the coordinator's update tick.                    |
| `irrigation_record_last_run`                    | Set inside the zone's `start` flow; persisted to disk.       |
| `irrigation_relais_power_monitor`               | Built into the zone runner; emits notifications via `binary_sensor.<zone>_relay_error`. |
| `irrigation_switch_unavailable_alert`           | `binary_sensor.<zone>_relay_available` reflects the live state of the relay. |

The two unrelated automations (`gw3000a_radiation_stale_alert`,
`gw3000a_wh65_battery_low_alert`) and the `forward_persistent_notifications_to_all_phones`
automation are **not** part of this integration – they monitor a third-party
device respectively a generic notification group. Keep them in your
`automations.yaml` if you still need them.

## Step-by-step migration

1. Install this integration (HACS or manual copy).
2. Restart Home Assistant.
3. Add the integration via *Settings → Devices & Services*.
4. Open the integration's **Configure** dialog and create one zone for each
   relay you previously had (currently the YAML package only modelled one
   physical zone, but you can take this opportunity to add more).
5. Move dashboards over to the new entity IDs (the dashboards in
   `dashboards/irrigation_*.yaml` reference the old `input_*` helpers and
   should be replaced; an example dashboard for one zone is included in the
   docker test environment under `docker/init/provision.py`).
6. Remove the package after confirming the integration works:
   ```bash
   rm -rf packages/irrigation_calculator
   ```
7. Optional: drop these obsolete YAML automations from `automations.yaml`:
   - any automation referencing `switch.irrigation_relais1`
   - the dashboard files `dashboards/irrigation_control.yaml` and
     `dashboards/irrigation_settings.yaml`
   - the `lovelace.dashboards` entries pointing at them in
     `configuration.yaml`

The two `gw3000a_*` automations and the
`forward_persistent_notifications_to_all_phones` automation are independent
and can stay.

## Stable IDs / breakage

`zone_id` is generated as a UUID4 the first time you add a zone and stored in
the config entry. It is used as part of every entity's `unique_id` together
with the config entry ID, so renaming a zone or changing its relay won't
break entity history.
