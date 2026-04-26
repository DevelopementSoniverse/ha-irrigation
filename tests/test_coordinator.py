"""Tests for radiation trigger logic in the coordinator."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.coordinator import IrrigationController
from tests.common import base_entry_kwargs, make_zone


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
    assert rt.last_reason == "Radiation"

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
