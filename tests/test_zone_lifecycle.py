"""Lifecycle tests: starting, stopping and watchdog behaviour of zones."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.irrigation_computer.const import (
    CONF_PUSH_ALERT_DEVICE_IDS,
    CONF_PUSH_ALERTS_ENABLED,
    DOMAIN,
    OPT_ZONES,
    REASON_MANUAL,
)
from custom_components.irrigation_computer.coordinator import IrrigationController

from tests.common import base_entry_kwargs, make_zone, seed_relay_states


async def _setup_controller(
    hass: HomeAssistant, zones: list[dict]
) -> tuple[MockConfigEntry, IrrigationController]:
    entry = MockConfigEntry(**base_entry_kwargs(zones=zones))
    entry.add_to_hass(hass)
    seed_relay_states(hass, zones)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()
    return entry, controller


@pytest.mark.asyncio
async def test_zone_run_turns_relay_on_then_off(hass: HomeAssistant) -> None:
    zone = make_zone(duration=1)
    entry, controller = await _setup_controller(hass, [zone])

    calls: list[tuple[str, str, dict]] = []

    async def fake_call(domain, service, data, blocking=False, **kw):
        calls.append((domain, service, dict(data)))

    with patch.object(hass.services, "async_call", side_effect=fake_call):
        ok = await controller.async_start_zone(zone["zone_id"], REASON_MANUAL)
        assert ok is True
        # Wait for run task to finish
        task = controller._zone_tasks[zone["zone_id"]]
        await task

    services = [(d, s) for d, s, _ in calls]
    assert ("switch", "turn_on") in services
    assert ("switch", "turn_off") in services

    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    assert rt.is_running is False
    assert rt.last_run_at is not None
    assert rt.last_reason == REASON_MANUAL

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_double_start_blocked(hass: HomeAssistant) -> None:
    zone = make_zone(duration=2)
    entry, controller = await _setup_controller(hass, [zone])

    async def fake_call(domain, service, data, blocking=False, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=fake_call):
        ok1 = await controller.async_start_zone(zone["zone_id"])
        assert ok1 is True
        # The lock is acquired inside the task, so give it a tick.
        await _yield()
        ok2 = await controller.async_start_zone(zone["zone_id"])
        assert ok2 is False
        await controller._zone_tasks[zone["zone_id"]]

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_power_alert_delay_waits_before_start_threshold_check(
    hass: HomeAssistant,
) -> None:
    zone = make_zone(
        power="sensor.test_power",
        power_alert_delay_sec=7,
    )
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.is_running = True
    hass.states.async_set("sensor.test_power", "999")

    calls: list[tuple[str, str, dict]] = []

    async def fake_call(domain, service, data, blocking=False, **kw):
        calls.append((domain, service, dict(data)))

    with patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ) as sleep_mock, patch.object(
        hass.services, "async_call", side_effect=fake_call
    ):
        await controller._async_monitor_power_start(zone_config)

    sleep_mock.assert_awaited_once_with(7)
    assert ("persistent_notification", "create") in [
        (domain, service) for domain, service, _ in calls
    ]

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_power_alert_delay_skips_check_if_zone_stopped(
    hass: HomeAssistant,
) -> None:
    zone = make_zone(
        power="sensor.test_power",
        power_alert_delay_sec=7,
    )
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.is_running = True
    hass.states.async_set("sensor.test_power", "999")

    async def mark_stopped(delay):
        rt.is_running = False

    with patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        new=AsyncMock(side_effect=mark_stopped),
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller._async_monitor_power_start(zone_config)

    assert not any(
        c.args[:2] == ("persistent_notification", "create")
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_power_sensor_unavailable_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(power="sensor.test_power")
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.is_running = True

    with patch(
        "custom_components.irrigation_computer.coordinator.POWER_WAIT_SECONDS", 0
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller._async_monitor_power_start(zone_config)

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_power_sensor_unavailable_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_no_positive_power_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(power="sensor.test_power")
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.is_running = True
    hass.states.async_set("sensor.test_power", "0")

    with patch(
        "custom_components.irrigation_computer.coordinator.POWER_WAIT_SECONDS", 0.001
    ), patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller._async_monitor_power_start(zone_config)

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_power_no_consumption_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_notify_sends_persistent_and_configured_push_alerts(
    hass: HomeAssistant,
) -> None:
    zone = make_zone()
    entry_kwargs = base_entry_kwargs(zones=[zone])
    entry_kwargs["options"] = {
        OPT_ZONES: [zone],
        CONF_PUSH_ALERTS_ENABLED: True,
        CONF_PUSH_ALERT_DEVICE_IDS: ["phone_1", "phone_2"],
    }
    entry = MockConfigEntry(**entry_kwargs)
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    def resolve(_hass, device_id):
        return {
            "phone_1": "mobile_app_phone_one",
            "phone_2": "mobile_app_phone_two",
        }.get(device_id)

    with patch.object(hass.services, "async_call") as mock_call, patch(
        "custom_components.irrigation_computer.coordinator."
        "mobile_app_notify_service",
        side_effect=resolve,
    ):
        await controller._async_notify("test", "Alert title", "Alert message")

    mock_call.assert_any_call(
        "persistent_notification",
        "create",
        {
            "notification_id": "irrigation_computer_test",
            "title": "Alert title",
            "message": "Alert message",
        },
        blocking=False,
    )
    push_calls = [
        call
        for call in mock_call.call_args_list
        if call.args[:1] == ("notify",)
    ]
    assert [call.args[1] for call in push_calls] == [
        "mobile_app_phone_one",
        "mobile_app_phone_two",
    ]
    for call in push_calls:
        assert call.args[2] == {"title": "Alert title", "message": "Alert message"}
        assert call.kwargs.get("blocking") is False

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_notify_skips_push_when_notify_service_missing(
    hass: HomeAssistant,
) -> None:
    zone = make_zone()
    entry_kwargs = base_entry_kwargs(zones=[zone])
    entry_kwargs["options"] = {
        OPT_ZONES: [zone],
        CONF_PUSH_ALERTS_ENABLED: True,
        CONF_PUSH_ALERT_DEVICE_IDS: ["phone_missing"],
    }
    entry = MockConfigEntry(**entry_kwargs)
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    with patch.object(hass.services, "async_call") as mock_call, patch(
        "custom_components.irrigation_computer.coordinator."
        "mobile_app_notify_service",
        return_value=None,
    ):
        await controller._async_notify("test", "Alert title", "Alert message")

    assert not any(
        call.args[:1] == ("notify",) for call in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_turn_on_failure_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(duration=1)
    _, controller = await _setup_controller(hass, [zone])
    calls: list[tuple[str, str, dict]] = []

    async def fake_call(domain, service, data, blocking=False, **kw):
        calls.append((domain, service, dict(data)))
        if (domain, service) == ("switch", "turn_on"):
            raise RuntimeError("boom")

    with patch.object(hass.services, "async_call", side_effect=fake_call):
        await controller.async_start_zone(zone["zone_id"], REASON_MANUAL)
        await controller._zone_tasks[zone["zone_id"]]

    assert any(
        call[0:2] == ("persistent_notification", "create")
        and call[2]["notification_id"].startswith(
            "irrigation_computer_turn_on_failed_"
        )
        for call in calls
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_relay_unavailable_before_start_sends_alert(
    hass: HomeAssistant,
) -> None:
    zone = make_zone(duration=1)
    _, controller = await _setup_controller(hass, [zone])
    hass.states.async_set(zone["relay_entity_id"], "unavailable")

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_start_zone(zone["zone_id"], REASON_MANUAL)
        await controller._zone_tasks[zone["zone_id"]]

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_relay_unavailable_"
        )
        for c in mock_call.call_args_list
    )
    assert not any(c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list)

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_turn_off_failure_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(duration=1)
    _, controller = await _setup_controller(hass, [zone])

    async def fake_call(domain, service, data, blocking=False, **kw):
        if (domain, service) == ("switch", "turn_off"):
            raise RuntimeError("boom")

    with patch.object(hass.services, "async_call", side_effect=fake_call) as mock_call, patch.object(
        controller, "_async_watchdog_off", new=AsyncMock()
    ):
        await controller.async_start_zone(zone["zone_id"], REASON_MANUAL)
        await controller._zone_tasks[zone["zone_id"]]

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_turn_off_failed_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_watchdog_failure_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone()
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None

    with patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ), patch.object(
        controller, "_async_relay_off", new=AsyncMock(side_effect=RuntimeError("boom"))
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller._async_watchdog_off(zone_config, retries=2)

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_watchdog_turn_off_failed_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_run_timeout_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(duration=1)
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.is_running = True
    rt.started_at = datetime.now(timezone.utc)

    with patch(
        "custom_components.irrigation_computer.coordinator.asyncio.sleep",
        new=AsyncMock(),
    ), patch.object(hass.services, "async_call") as mock_call:
        await controller._async_monitor_run_timeout(zone_config, rt.started_at)

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith(
            "irrigation_computer_run_timeout_"
        )
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_too_many_runs_24h_sends_alert(hass: HomeAssistant) -> None:
    zone = make_zone(max_runs_24h=1)
    _, controller = await _setup_controller(hass, [zone])
    zone_config = controller.get_zone(zone["zone_id"])
    assert zone_config is not None
    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    now = datetime.now(timezone.utc)
    rt.run_history = [now.timestamp(), now.timestamp()]

    with patch.object(hass.services, "async_call") as mock_call:
        await controller._async_check_runs_24h_alert(zone_config, now)

    assert any(
        c.args[:2] == ("persistent_notification", "create")
        and c.args[2]["notification_id"].startswith("irrigation_computer_runs_24h_")
        for c in mock_call.call_args_list
    )

    await controller.async_shutdown()


@pytest.mark.asyncio
async def test_stop_cancels_running_zone(hass: HomeAssistant) -> None:
    zone = make_zone(duration=60)
    entry, controller = await _setup_controller(hass, [zone])

    async def fake_call(domain, service, data, blocking=False, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=fake_call):
        await controller.async_start_zone(zone["zone_id"])
        await _yield()
        await controller.async_stop_zone(zone["zone_id"])
        # The task should finish quickly after cancel.
        await controller._zone_tasks[zone["zone_id"]]

    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    assert rt.is_running is False

    await controller.async_shutdown()


async def _yield() -> None:
    """Yield control to the event loop a few times."""
    import asyncio

    for _ in range(3):
        await asyncio.sleep(0)
