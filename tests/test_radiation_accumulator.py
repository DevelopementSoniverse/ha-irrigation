"""Tests for the radiation accumulator and per-zone snapshots."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.coordinator import IrrigationController
from tests.common import base_entry_kwargs, make_zone


def _state(value: float) -> State:
    return State("sensor.solar_radiation", str(value))


async def test_trapezoidal_integration_w_per_m2(hass: HomeAssistant) -> None:
    zone = make_zone()
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    try:
        # Manually feed two samples 1h apart at 1000 W/m² constant -> 1000 Wh/m².
        now = dt_util.utcnow()
        controller._radiation_last_value = None
        controller._radiation_last_ts = None
        controller._radiation_total_wh = 0.0

        controller._radiation_last_value = 1000.0
        controller._radiation_last_ts = now - timedelta(hours=1)
        controller._update_radiation_from_state(_state(1000.0))

        assert controller.radiation_total_wh == pytest.approx(1000.0)
    finally:
        await controller.async_shutdown()


async def test_radiation_since_last_run_resets_on_start(hass: HomeAssistant) -> None:
    from unittest.mock import patch

    zone = make_zone(duration=1)
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    controller._radiation_total_wh = 500.0
    assert controller.radiation_since_last_run(zone["zone_id"]) == 500.0

    async def noop(*a, **kw):
        return None

    with patch.object(hass.services, "async_call", side_effect=noop):
        await controller.async_start_zone(zone["zone_id"])
        await controller._zone_tasks[zone["zone_id"]]

    assert controller.radiation_since_last_run(zone["zone_id"]) == 0.0

    controller._radiation_total_wh = 750.0
    assert controller.radiation_since_last_run(zone["zone_id"]) == 250.0

    await controller.async_shutdown()


async def test_unavailable_pauses_integration(hass: HomeAssistant) -> None:
    zone = make_zone()
    entry = MockConfigEntry(
        **base_entry_kwargs(radiation_source="sensor.solar_radiation", zones=[zone])
    )
    entry.add_to_hass(hass)
    controller = IrrigationController(hass, entry)
    await controller.async_initialize()

    controller._radiation_total_wh = 100.0
    controller._update_radiation_from_state(State("sensor.solar_radiation", "unavailable"))
    assert controller._radiation_last_value is None
    assert controller._radiation_last_ts is None
    assert controller.radiation_total_wh == 100.0  # untouched

    await controller.async_shutdown()
