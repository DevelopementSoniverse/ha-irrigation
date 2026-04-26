# Alerts, Errors and Warnings

This page lists every runtime condition the Irrigation Computer integration can
report, what triggers it and what the user-visible consequence is.

*Deutsche Fassung: [`ALERTS.de.md`](ALERTS.de.md).*

## How alerts are delivered

Every alert is raised in **two** places (the second one is optional):

1. **Persistent notification** in Home Assistant
   (Settings → Notifications). The notification id follows the pattern
   `irrigation_computer_<suffix>_<zone_id>` (or `irrigation_computer_<suffix>`
   for controller-level alerts) so the same condition updates the existing
   card instead of creating a duplicate.
2. **Push notification** on the configured mobile app devices, if
   *“Send custom component alerts as push notifications”* is enabled in the
   integration's options and at least one smartphone device is selected.

Alerts are **deduplicated**: while an alert is active, it will not be re-posted.
When a zone starts a new run, all zone-specific alerts for that zone are
cleared automatically, so the next failure can fire again.

Zone alerts additionally update the zone's
`sensor.<zone>_relay_error` entity (machine-readable error code) and are
surfaced on the zone's dashboard card under *Alerts & Sicherheit*.

## Zone-level alerts

Each row below is an alert that is raised for a single zone. The **Error code**
column matches the value of `sensor.<zone>_relay_error` after the incident.

| Error code | Triggered by | Effect on the current run | Notification |
|---|---|---|---|
| `relay_unavailable` | Relay entity missing or in state `unavailable` / `unknown` when a run is about to start | Run is **aborted before the relay is switched on** | Persistent + push |
| `turn_on_failed_<id>` <br> (`turn_on failed: …`) | `switch.turn_on` service call raised an exception | Run is **aborted**, zone left in stopped state | Persistent + push |
| `turn_off_failed_<id>` <br> (`turn_off failed: …`) | `switch.turn_off` raised an exception at the end of the run | Run ends anyway; a **watchdog is scheduled** to retry `turn_off` up to 3 times | Persistent + push |
| `watchdog_turn_off_failed` | All watchdog retries failed to shut the relay off | Relay may still be on – **manual intervention required** | Persistent + push |
| `manual_turn_off_failed` | User requested a manual stop but `switch.turn_off` raised | Zone is marked as stopped; relay state unknown | Persistent + push |
| `power_sensor_unavailable` | Configured power sensor never returned a numeric reading during the start-up window (`POWER_WAIT_SECONDS = 30 s`) | Run continues; power checks are skipped | Persistent + push |
| `power_no_consumption` | Power sensor reported `≤ 0 W` for the entire start-up window | Run continues; suggests the motor did not actually start or the wrong sensor is linked | Persistent + push |
| `power_low` | Measured startup power was `≤ zone.power_min` (undercurrent threshold) | Run continues; indicates a weak pump / dry running | Persistent + push |
| `power_high` | Measured startup power was `≥ zone.power_max` (overcurrent threshold) | Run continues; indicates a blocked or overloaded motor | Persistent + push |
| `power_after_off` | Power sensor reported `> 0 W` two seconds after the run ended | Run already ended, but **the relay may still be powering the motor** | Persistent + push |
| `power_sensor_unavailable_after_off` | Power sensor became unavailable during the post-run check | Cannot verify the motor has stopped | Persistent + push |
| `power_sensor_invalid_after_off` | Power sensor returned a value that cannot be parsed as a number after stop | Cannot verify the motor has stopped | Persistent + push |
| `run_timeout` | Zone is still marked as running `watering_duration + 5 s` after it was started | Run is **not force-stopped**, but surfaces a potential stuck-task condition | Persistent + push |
| `too_many_runs_24h` | Number of runs in the last 24 h exceeded the configured *“24h run alert threshold”* (set to `0` to disable) | **Informational** – the current run and future scheduling are not blocked | Persistent + push |
| `soil_moisture_sensors_unavailable` | Soil-moisture trigger is enabled for a zone but none of the configured sensors returned a valid numeric reading at the current tick | Trigger cannot evaluate; the dwell timer is intentionally kept as-is (no reset) so a brief sensor outage does not restart the countdown. Cleared automatically as soon as at least one sensor delivers a value | Persistent + push |

### Delayed power check

The *“Power alert delay (seconds)”* per zone lets slow pumps ramp up before the
first power evaluation begins. If the zone is stopped during the delay (e.g.
by a user or a crashing task), the post-delay checks are skipped silently – no
false alerts while the zone is no longer running.

## Controller-level alerts

These alerts are not tied to a single zone and appear once per integration
instance.

| Error code | Triggered by | Effect | Notification |
|---|---|---|---|
| `radiation_source_unavailable` | Configured radiation source entity is missing or in state `unavailable` / `unknown` | Radiation integration pauses; **radiation-based triggers cannot fire** until the source is available again | Persistent + push |
| `radiation_source_stale` | Source reports `> 0 W/m²` but has not updated in more than `RADIATION_STALE_SECONDS` (2 h) | Same as above – the sensor is considered stuck, radiation triggers are effectively paused | Persistent + push |

Both alerts are automatically cleared as soon as the source reports a fresh
and valid value (including `0 W/m²` at night, which is a legitimate reading).

## Log-only warnings

These conditions do not create a notification, but show up in the Home
Assistant log and are useful for debugging.

| Log level | Message | Context |
|---|---|---|
| `WARNING` | `Zone … appears to have been running across restart – forcing relay off` | Persisted state said a zone was running when Home Assistant restarted; coordinator defensively issues `switch.turn_off`. |
| `WARNING` | `start_zone: unknown zone_id …` | Service called with a zone id that no longer exists in the config entry. |
| `WARNING` | `start_zone: no controller for zone_id …` | Zone id exists but its controller was unloaded. |
| `WARNING` | `No mobile_app notify service found for device …; skipping push notification` | A device id was saved in the options but the matching `notify.mobile_app_<slug>` service is not registered (mobile app uninstalled or device removed). Persistent notification still fires. |
| `EXCEPTION` | `Relay turn_on failed for zone …` / `Relay turn_off failed for zone …` / `Force relay off failed for …` / `Manual stop relay_off failed for …` | Backing trace for the corresponding zone alert above. |
| `EXCEPTION` | `Failed to create persistent notification` | Home Assistant's notification service was not available; the alert is lost. |
| `EXCEPTION` | `Failed to send push notification to device … via …` | Calling the mobile app notify service failed (e.g. device offline). Persistent notification already succeeded. |
| `EXCEPTION` | `Failed to persist runtime state` | Storage write for run history / radiation accumulator failed. |
| `EXCEPTION` | `Failed to update dashboard '…'` | Auto-managed Lovelace dashboard rebuild failed; no user-visible impact on zone control. |

## Clearing alerts manually

- Starting a zone resets all active zone alerts for that zone
  (new `switch.<zone>_start` or `irrigation_computer.start_zone` service call).
- Dismissing the persistent notification in the Home Assistant UI only hides
  it once – if the underlying condition is still present at the next check,
  the notification is recreated.
- The `sensor.<zone>_relay_error` entity keeps the last error code until the
  zone runs again successfully.
