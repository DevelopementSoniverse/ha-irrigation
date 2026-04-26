"""Lifecycle tests: starting, stopping and watchdog behaviour of zones."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.irrigation_computer.const import (
    DOMAIN,
    REASON_MANUAL,
)
from custom_components.irrigation_computer.coordinator import IrrigationController

from tests.common import base_entry_kwargs, make_zone


async def _setup_controller(
    hass: HomeAssistant, zones: list[dict]
) -> tuple[MockConfigEntry, IrrigationController]:
    entry = MockConfigEntry(**base_entry_kwargs(zones=zones))
    entry.add_to_hass(hass)
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
