# Irrigation Computer – Test Environment

Spins up a Home Assistant container with the `irrigation_computer` integration
already installed, an admin user pre-provisioned and two example zones wired up
against simulated relays / a simulated solar radiation sensor.

## Start

```bash
cd docker
docker compose up -d
```

Wait ~30 seconds for HA to finish its first launch, then open:

  http://localhost:8123

Login:

| User  | Password |
|-------|----------|
| admin | admin    |

If port 8123 is already taken, set a different one:

```bash
HA_PORT=8124 docker compose up -d
```

## What's already configured

| Entity / object                           | Notes |
|-------------------------------------------|-------|
| `sensor.mock_solar_radiation`             | Reflects the slider `input_number.mock_solar_radiation_w_m2` (W/m²) |
| `switch.mock_relay_a` / `switch.mock_relay_b` | Template switches backed by `input_boolean.mock_relay_a/_b` |
| `sensor.mock_relay_a_power` / `_b_power`  | Returns `50 W` while the corresponding switch is on, otherwise `0 W` |
| Config entry `irrigation_computer`        | Pre-baked with two zones: **Tomaten Hochbeet** and **Kraeuter** |
| Dashboard "Irrigation Computer"           | Visible in the sidebar |

## How to test the integration

1. Open the **Irrigation Computer** dashboard (sidebar).
2. Press *Start irrigation* on **Tomaten Hochbeet** – `switch.mock_relay_a`
   should turn on, then off again after 30 s. `Last reason` becomes `Manual`,
   `Last run` updates and `Runs 24h` increases.
3. Move the **Mock Solar Radiation** slider to a high value (e.g. 1000 W/m²)
   and wait. After ~3 minutes the radiation accumulator (`Global radiation
   energy`) crosses the per-zone threshold and the radiation trigger starts a
   run automatically. `Last reason` becomes `Radiation` and the radiation
   counter resets.
4. Disable `switch.mock_relay_a` while a run is active – the watchdog will
   force the relay off again at the end of the configured duration.
5. Toggle `switch.tomaten_hochbeet_radiation_trigger_enabled` off to disable
   the radiation trigger for that zone.

## Stop / wipe

```bash
docker compose down            # stop, keep data
docker compose down -v         # stop and remove the bind-mounted state files
                               # (also removes the provisioned admin user)
```

To wipe everything except the configuration template:

```bash
rm -rf config/.storage config/home-assistant.log config/home-assistant_v2.db*
```
