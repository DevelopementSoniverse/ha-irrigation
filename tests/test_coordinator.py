"""Tests for radiation trigger logic in the coordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from homeassistant.core import HomeAssistant, State
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.coordinator import IrrigationController
from tests.common import base_entry_kwargs, make_zone, seed_relay_states


async def test_radiation_trigger_starts_zone(hass: HomeAssistant) -> None:
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=True,
        threshold_planting=10.0,
        fallback_enabled=False,
        fallback_start="00:00:00",
        fallback_end="23:59:59",
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    controller._radiation_total_wh = 25.0  # exceeds threshold

    async def noop(*a, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=noop):
        await controller.async_refresh()
        for t in list(controller._zone_tasks.values()):
            await t

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.last_reason == "radiation"

    await controller.async_shutdown()


async def test_radiation_trigger_disabled_does_not_start(hass: HomeAssistant) -> None:
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=False,
        threshold_planting=10.0,
        fallback_enabled=False,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    controller._radiation_total_wh = 999.0

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()
        assert not any(
            c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list
        )

    await controller.async_shutdown()


async def test_radiation_trigger_outside_fallback_window_blocked(
    hass: HomeAssistant,
) -> None:
    # Window 06:00-06:01 (essentially never current unless we're inside it).
    zone = make_zone(
        duration=1,
        radiation_trigger_enabled=True,
        threshold_planting=10.0,
        fallback_enabled=False,
        fallback_start="06:00:00",
        fallback_end="06:01:00",
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    controller._radiation_total_wh = 999.0

    from datetime import datetime, time
    from homeassistant.util import dt as dt_util

    fixed = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.now",
        return_value=fixed,
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()
        assert not any(
            c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list
        )

    await controller.async_shutdown()


async def test_radiation_source_unavailable_sends_alert_after_grace(
    hass: HomeAssistant,
) -> None:
    """Without a power switch, alert fires after the 10-minute grace period."""
    zone = make_zone(radiation_trigger_enabled=True)
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.solar_radiation", "unavailable")
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    from homeassistant.util import dt as dt_util

    t0 = dt_util.utcnow()

    # First tick within the grace period: no alert should be sent yet.
    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0,
    ), patch.object(hass.services, "async_call") as mock_call_early:
        await controller.async_refresh()

    assert not any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"]
        == "irrigation_computer_radiation_source_unavailable"
        for c in mock_call_early.call_args_list
    )

    # Advance past the 10-minute grace period: alert must fire now.
    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0 + timedelta(minutes=11),
    ), patch.object(hass.services, "async_call") as mock_call_late:
        await controller.async_refresh()

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"]
        == "irrigation_computer_radiation_source_unavailable"
        for c in mock_call_late.call_args_list
    )

    await controller.async_shutdown()


async def test_radiation_source_brief_outage_does_not_alert(
    hass: HomeAssistant,
) -> None:
    """A short outage that recovers within the grace period must not alert."""
    zone = make_zone(radiation_trigger_enabled=True)
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    unavailable_state = State("sensor.solar_radiation", "unavailable")
    recovered_state = State(
        "sensor.solar_radiation",
        "120",
        last_updated=datetime.now(timezone.utc),
    )

    with patch.object(hass.services, "async_call") as mock_call:
        # Several ticks while unavailable, all well within the 10 min grace period.
        await controller._async_check_radiation_source_alert(unavailable_state)
        await controller._async_check_radiation_source_alert(unavailable_state)
        # Source recovers before the grace period expires.
        await controller._async_check_radiation_source_alert(recovered_state)

    assert not any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"]
        == "irrigation_computer_radiation_source_unavailable"
        for c in mock_call.call_args_list
    )
    assert controller._radiation_unavailable_since is None

    await controller.async_shutdown()


async def test_radiation_source_zero_does_not_send_stale_alert(
    hass: HomeAssistant,
) -> None:
    zone = make_zone(radiation_trigger_enabled=True)
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()
    stale_zero_state = State(
        "sensor.solar_radiation",
        "0",
        last_updated=datetime.now(timezone.utc) - timedelta(hours=8),
    )

    with patch.object(hass.services, "async_call") as mock_call:
        await controller._async_check_radiation_source_alert(stale_zero_state)

    assert not any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_radiation_source_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


def _unavailable_alert_calls(mock_call) -> list:
    return [
        c
        for c in mock_call.call_args_list
        if c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"]
        == "irrigation_computer_radiation_source_unavailable"
    ]


def _switch_calls(mock_call, service: str, entity_id: str) -> list:
    return [
        c
        for c in mock_call.call_args_list
        if c.args[:2] == ("switch", service)
        and c.args[2].get("entity_id") == entity_id
    ]


async def test_weather_station_power_cycle_then_alert(
    hass: HomeAssistant,
) -> None:
    """With power switch: cycle after 5 min, alert only after recovery wait."""
    zone = make_zone(radiation_trigger_enabled=True)
    power = "switch.weather_psu"
    entry = MockConfigEntry(
        **base_entry_kwargs(
            radiation_source="sensor.solar_radiation",
            zones=[zone],
            weather_station_power=power,
        )
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.solar_radiation", "unavailable")
    hass.states.async_set(power, "on")
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    from homeassistant.util import dt as dt_util

    t0 = dt_util.utcnow()

    async def fake_sleep(_seconds: float) -> None:
        return None

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0 + timedelta(minutes=5),
    ), patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        side_effect=fake_sleep,
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()

    assert _switch_calls(mock_call, "turn_off", power)
    assert _switch_calls(mock_call, "turn_on", power)
    assert not _unavailable_alert_calls(mock_call)
    assert controller._radiation_power_cycle_attempted is True
    assert controller._radiation_power_cycle_finished_at is not None

    finished = controller._radiation_power_cycle_finished_at

    # Still within recovery window: no alert.
    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=finished + timedelta(minutes=4),
    ), patch.object(hass.services, "async_call") as mock_call_mid:
        await controller.async_refresh()

    assert not _unavailable_alert_calls(mock_call_mid)

    # Past recovery window: alert fires once.
    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=finished + timedelta(minutes=5, seconds=1),
    ), patch.object(hass.services, "async_call") as mock_call_late:
        await controller.async_refresh()

    assert _unavailable_alert_calls(mock_call_late)

    await controller.async_shutdown()


async def test_weather_station_no_double_power_cycle(
    hass: HomeAssistant,
) -> None:
    """Multiple ticks during the OFF phase must not start a second cycle."""
    zone = make_zone(radiation_trigger_enabled=True)
    power = "switch.weather_psu"
    entry = MockConfigEntry(
        **base_entry_kwargs(
            radiation_source="sensor.solar_radiation",
            zones=[zone],
            weather_station_power=power,
        )
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.solar_radiation", "unavailable")
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    from homeassistant.util import dt as dt_util

    t0 = dt_util.utcnow()
    sleep_started = asyncio.Event()
    continue_sleep = asyncio.Event()

    async def controlled_sleep(_seconds: float) -> None:
        sleep_started.set()
        await continue_sleep.wait()

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0 + timedelta(minutes=5),
    ), patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        side_effect=controlled_sleep,
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await asyncio.wait_for(sleep_started.wait(), timeout=2)
        # Second tick while first cycle is still sleeping.
        await controller.async_refresh()
        assert controller._radiation_power_cycle_attempted is True
        continue_sleep.set()
        await hass.async_block_till_done()

    assert len(_switch_calls(mock_call, "turn_off", power)) == 1
    assert len(_switch_calls(mock_call, "turn_on", power)) == 1

    await controller.async_shutdown()


async def test_weather_station_recovery_cancels_cycle_without_alert(
    hass: HomeAssistant,
) -> None:
    """Recovery mid-cycle cancels the task and must not alert."""
    zone = make_zone(radiation_trigger_enabled=True)
    power = "switch.weather_psu"
    entry = MockConfigEntry(
        **base_entry_kwargs(
            radiation_source="sensor.solar_radiation",
            zones=[zone],
            weather_station_power=power,
        )
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.solar_radiation", "unavailable")
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    from homeassistant.util import dt as dt_util

    t0 = dt_util.utcnow()
    sleep_started = asyncio.Event()
    continue_sleep = asyncio.Event()

    async def controlled_sleep(_seconds: float) -> None:
        sleep_started.set()
        await continue_sleep.wait()

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0 + timedelta(minutes=5),
    ), patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        side_effect=controlled_sleep,
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await asyncio.wait_for(sleep_started.wait(), timeout=2)
        assert controller._radiation_power_cycle_attempted is True

        hass.states.async_set("sensor.solar_radiation", "50")
        await controller.async_refresh()

        assert controller._radiation_unavailable_since is None
        assert controller._radiation_power_cycle_attempted is False
        assert not _unavailable_alert_calls(mock_call)

        # Allow cancelled task to finish its finally turn_on if still waiting.
        continue_sleep.set()
        await hass.async_block_till_done()

    await controller.async_shutdown()


async def test_weather_station_zero_does_not_power_cycle(
    hass: HomeAssistant,
) -> None:
    """A legitimate night-time zero must not trigger a power-cycle."""
    zone = make_zone(radiation_trigger_enabled=True)
    power = "switch.weather_psu"
    entry = MockConfigEntry(
        **base_entry_kwargs(
            radiation_source="sensor.solar_radiation",
            zones=[zone],
            weather_station_power=power,
        )
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    zero_state = State(
        "sensor.solar_radiation",
        "0",
        last_updated=datetime.now(timezone.utc),
    )

    with patch.object(hass.services, "async_call") as mock_call:
        await controller._async_check_radiation_source_alert(zero_state)
        await controller._async_check_radiation_source_alert(zero_state)

    assert not _switch_calls(mock_call, "turn_off", power)
    assert not _switch_calls(mock_call, "turn_on", power)
    assert controller._radiation_power_cycle_attempted is False

    await controller.async_shutdown()


async def test_weather_station_switch_error_still_alerts_after_recovery_wait(
    hass: HomeAssistant,
) -> None:
    """Switch failures still count as a cycle attempt and alert after wait."""
    zone = make_zone(radiation_trigger_enabled=True)
    power = "switch.weather_psu"
    entry = MockConfigEntry(
        **base_entry_kwargs(
            radiation_source="sensor.solar_radiation",
            zones=[zone],
            weather_station_power=power,
        )
    )
    entry.add_to_hass(hass)
    hass.states.async_set("sensor.solar_radiation", "unavailable")
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    from homeassistant.util import dt as dt_util

    t0 = dt_util.utcnow()

    async def failing_call(domain, service, *args, **kwargs):
        if domain == "switch":
            raise RuntimeError("switch unavailable")
        return None

    async def fake_sleep(_seconds: float) -> None:
        return None

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=t0 + timedelta(minutes=5),
    ), patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        side_effect=fake_sleep,
    ), patch.object(hass.services, "async_call", side_effect=failing_call):
        await controller.async_refresh()
        await hass.async_block_till_done()

    assert controller._radiation_power_cycle_attempted is True
    assert controller._radiation_power_cycle_finished_at is not None
    finished = controller._radiation_power_cycle_finished_at

    with patch(
        "custom_components.irrigation_computer.coordinator.dt_util.utcnow",
        return_value=finished + timedelta(minutes=5, seconds=1),
    ), patch.object(hass.services, "async_call") as mock_call_late:
        await controller.async_refresh()

    assert _unavailable_alert_calls(mock_call_late)

    await controller.async_shutdown()
