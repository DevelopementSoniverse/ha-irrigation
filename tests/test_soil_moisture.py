"""Tests for soil-moisture trigger and min-interval gate."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.coordinator import IrrigationController
from tests.common import base_entry_kwargs, make_zone, seed_relay_states


SENSOR_A = "sensor.mock_soil_moisture_a"
SENSOR_B = "sensor.mock_soil_moisture_b"


async def _run_pending_zone_tasks(controller: IrrigationController) -> None:
    for t in list(controller._zone_tasks.values()):
        await t


async def test_moisture_trigger_fires_after_dwell(hass: HomeAssistant) -> None:
    """Trigger fires once the average stays below threshold for the dwell period."""
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=False,
        fallback_enabled=False,
        soil_moisture_entity_ids=[SENSOR_A, SENSOR_B],
        soil_moisture_trigger_enabled=True,
        soil_moisture_threshold=40.0,
        soil_moisture_dwell_minutes=5,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])

    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    # Drive the sensors only after init so the initial refresh doesn't
    # already arm the dwell timer.
    hass.states.async_set(SENSOR_A, "20")
    hass.states.async_set(SENSOR_B, "30")  # avg = 25 < 40

    async def noop(*a, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=noop):
        await controller.async_refresh()

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.moisture_below_since is not None
    assert rt.last_reason != "soil_moisture"

    # Advance wall clock past the dwell threshold by rewinding the marker.
    rt.moisture_below_since = rt.moisture_below_since - timedelta(minutes=6)

    with patch.object(hass.services, "async_call", side_effect=noop):
        await controller.async_refresh()
        await _run_pending_zone_tasks(controller)

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.last_reason == "soil_moisture"

    await controller.async_shutdown()


async def test_moisture_trigger_resets_when_above_threshold(
    hass: HomeAssistant,
) -> None:
    """Dwell timer is cleared when the average returns above the threshold."""
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=False,
        fallback_enabled=False,
        soil_moisture_entity_ids=[SENSOR_A],
        soil_moisture_trigger_enabled=True,
        soil_moisture_threshold=40.0,
        soil_moisture_dwell_minutes=5,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])

    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    hass.states.async_set(SENSOR_A, "20")

    with patch.object(hass.services, "async_call"):
        await controller.async_refresh()

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.moisture_below_since is not None

    hass.states.async_set(SENSOR_A, "60")
    with patch.object(hass.services, "async_call"):
        await controller.async_refresh()

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.moisture_below_since is None

    await controller.async_shutdown()


async def test_min_interval_blocks_moisture_and_radiation(
    hass: HomeAssistant,
) -> None:
    """While inside the min-interval window, no automatic trigger fires."""
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=True,
        threshold_planting=10.0,
        fallback_enabled=False,
        soil_moisture_entity_ids=[SENSOR_A],
        soil_moisture_trigger_enabled=True,
        soil_moisture_threshold=50.0,
        soil_moisture_dwell_minutes=0,
        min_interval_minutes=30,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])

    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    # Set sensor + last_run_at after init so the initial refresh doesn't already
    # fire the trigger (rt.last_run_at starts as None, bypassing the gate).
    hass.states.async_set(SENSOR_A, "10")
    rt = controller.get_runtime(zone["zone_id"])
    rt.last_run_at = dt_util.now() - timedelta(minutes=10)
    controller._radiation_total_wh = 100.0

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()
        assert not any(
            c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list
        )

    async def noop(*a, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=noop):
        assert await controller.async_start_zone(zone["zone_id"], "manual") is True
        await _run_pending_zone_tasks(controller)

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.last_reason == "manual"

    await controller.async_shutdown()


async def test_moisture_trigger_without_sensors_does_nothing(
    hass: HomeAssistant,
) -> None:
    """An enabled switch without configured sensors must not start a run."""
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=False,
        fallback_enabled=False,
        soil_moisture_entity_ids=[],
        soil_moisture_trigger_enabled=True,
        soil_moisture_threshold=100.0,
        soil_moisture_dwell_minutes=0,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])

    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()
        assert not any(
            c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list
        )

    await controller.async_shutdown()


async def test_moisture_sensors_unavailable_emits_alert(
    hass: HomeAssistant,
) -> None:
    """Unavailable sensors leave the dwell timer alone and create an alert."""
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=False,
        fallback_enabled=False,
        soil_moisture_entity_ids=[SENSOR_A, SENSOR_B],
        soil_moisture_trigger_enabled=True,
        soil_moisture_threshold=40.0,
        soil_moisture_dwell_minutes=5,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])
    hass.states.async_set(SENSOR_A, "unavailable")
    hass.states.async_set(SENSOR_B, "unknown")

    controller = IrrigationController(hass, entry)

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_initialize()
        await controller.async_refresh()
        await hass.async_block_till_done()

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.moisture_below_since is None

    zid = zone["zone_id"]
    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"]
        == f"irrigation_computer_soil_moisture_sensors_unavailable_{zid}"
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()
