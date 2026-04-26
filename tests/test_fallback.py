"""Tests for fallback window evaluation and trigger."""

from __future__ import annotations

from datetime import time, timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.coordinator import (
    IrrigationController,
    in_fallback_window,
)
from custom_components.irrigation_computer.models import ZoneConfig
from tests.common import base_entry_kwargs, make_zone, seed_relay_states


def _zone_cfg(**overrides) -> ZoneConfig:
    data = make_zone(**overrides)
    return ZoneConfig.from_dict(data)


def test_fallback_window_same_day() -> None:
    z = _zone_cfg(fallback_start="06:00:00", fallback_end="20:00:00")
    assert in_fallback_window(z, time(12, 0))
    assert not in_fallback_window(z, time(5, 0))
    assert not in_fallback_window(z, time(21, 0))


def test_fallback_window_overnight() -> None:
    z = _zone_cfg(fallback_start="22:00:00", fallback_end="06:00:00")
    assert in_fallback_window(z, time(23, 30))
    assert in_fallback_window(z, time(3, 0))
    assert not in_fallback_window(z, time(12, 0))


async def test_fallback_trigger_starts_zone(hass: HomeAssistant) -> None:
    zone = make_zone(
        duration=1,
        fallback_minutes=5,
        fallback_start="00:00:00",
        fallback_end="23:59:59",
        radiation_trigger_enabled=False,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    seed_relay_states(hass, [zone])
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    rt = controller.get_runtime(zone["zone_id"])
    assert rt is not None
    rt.last_run_at = dt_util.now() - timedelta(minutes=10)

    started = []

    async def fake_call(*a, **kw):
        started.append((a, kw))
        return None

    with patch.object(hass.services, "async_call", side_effect=fake_call):
        await controller.async_refresh()
        # Wait for any spawned task.
        for t in list(controller._zone_tasks.values()):
            await t

    rt = controller.get_runtime(zone["zone_id"])
    assert rt.last_reason == "Fallback"

    await controller.async_shutdown()


async def test_fallback_disabled_does_not_trigger(hass: HomeAssistant) -> None:
    zone = make_zone(
        duration=1,
        fallback_enabled=False,
        radiation_trigger_enabled=False,
    )
    entry = MockConfigEntry(**base_entry_kwargs(zones=[zone]))
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    rt = controller.get_runtime(zone["zone_id"])
    rt.last_run_at = dt_util.now() - timedelta(hours=10)

    with patch.object(hass.services, "async_call") as mock_call:
        await controller.async_refresh()
        await hass.async_block_till_done()
        # Should not have called any service.
        assert not any(
            c.args[:2] == ("switch", "turn_on") for c in mock_call.call_args_list
        )

    await controller.async_shutdown()
