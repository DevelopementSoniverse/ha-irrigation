"""Tests for the Irrigation Computer config and options flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_computer.const import (
    CONF_PUSH_ALERT_DEVICE_IDS,
    CONF_PUSH_ALERTS_ENABLED,
    CONF_RADIATION_SOURCE_ENTITY,
    CONF_RADIATION_SOURCE_UNIT,
    DOMAIN,
    OPT_ZONES,
    UNIT_W_PER_M2,
    ZONE_FALLBACK_ENABLED,
    ZONE_FALLBACK_END,
    ZONE_FALLBACK_MINUTES,
    ZONE_FALLBACK_START,
    ZONE_ID,
    ZONE_MAX_RUNS_24H,
    ZONE_NAME,
    ZONE_PHASE,
    ZONE_POWER_ALERT_DELAY,
    ZONE_POWER_MAX,
    ZONE_POWER_MIN,
    ZONE_RADIATION_TRIGGER_ENABLED,
    ZONE_RELAY_ENTITY,
    ZONE_THRESHOLD_FRUIT_SET,
    ZONE_THRESHOLD_PLANTING,
    ZONE_THRESHOLD_RIPENING,
    ZONE_WATERING_DURATION,
    PHASE_PLANTING,
)


async def test_user_config_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_RADIATION_SOURCE_ENTITY: "sensor.solar_radiation",
            CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
            CONF_PUSH_ALERTS_ENABLED: True,
            CONF_PUSH_ALERT_DEVICE_IDS: ["phone_1", "phone_2"],
        },
    )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_RADIATION_SOURCE_ENTITY] == "sensor.solar_radiation"
    assert result2["data"][CONF_PUSH_ALERTS_ENABLED] is True
    assert result2["data"][CONF_PUSH_ALERT_DEVICE_IDS] == ["phone_1", "phone_2"]
    assert result2["options"] == {OPT_ZONES: []}


async def test_options_flow_add_edit_delete_zone(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_RADIATION_SOURCE_ENTITY: "sensor.solar_radiation",
            CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
        },
        options={OPT_ZONES: []},
        title="Irrigation Computer",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.irrigation_computer.IrrigationController.async_initialize"
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Open menu.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] == FlowResultType.MENU

        # Add zone.
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_zone"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "add_zone"

        zone_payload = {
            ZONE_NAME: "Tomaten",
            ZONE_RELAY_ENTITY: "switch.test_relay",
            ZONE_WATERING_DURATION: 30,
            ZONE_PHASE: PHASE_PLANTING,
            ZONE_THRESHOLD_PLANTING: 50.0,
            ZONE_THRESHOLD_FRUIT_SET: 100.0,
            ZONE_THRESHOLD_RIPENING: 80.0,
            ZONE_POWER_ALERT_DELAY: 12,
            ZONE_POWER_MIN: 5.0,
            ZONE_POWER_MAX: 500.0,
            ZONE_MAX_RUNS_24H: 6,
            ZONE_FALLBACK_ENABLED: True,
            ZONE_FALLBACK_MINUTES: 60,
            ZONE_FALLBACK_START: "06:00:00",
            ZONE_FALLBACK_END: "20:00:00",
            ZONE_RADIATION_TRIGGER_ENABLED: True,
        }
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], zone_payload
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        zones = entry.options[OPT_ZONES]
        assert len(zones) == 1
        zone_id = zones[0][ZONE_ID]
        assert zones[0][ZONE_NAME] == "Tomaten"
        assert zones[0][ZONE_POWER_ALERT_DELAY] == 12
        assert zones[0][ZONE_MAX_RUNS_24H] == 6

        # Edit zone.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "edit_zone_select"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {ZONE_ID: zone_id}
        )
        assert result["step_id"] == "edit_zone"
        edited_payload = dict(zone_payload, **{ZONE_NAME: "Tomaten Hochbeet"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], edited_payload
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[OPT_ZONES][0][ZONE_NAME] == "Tomaten Hochbeet"

        # Delete zone.
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "delete_zone_select"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {ZONE_ID: zone_id, "confirm": True}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[OPT_ZONES] == []

        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_options_flow_updates_global_push_settings(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_RADIATION_SOURCE_ENTITY: "sensor.solar_radiation",
            CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
        },
        options={OPT_ZONES: []},
        title="Irrigation Computer",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.irrigation_computer.IrrigationController.async_initialize"
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "global_settings"}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "global_settings"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_RADIATION_SOURCE_ENTITY: "sensor.solar_radiation",
                CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
                CONF_PUSH_ALERTS_ENABLED: True,
                CONF_PUSH_ALERT_DEVICE_IDS: ["phone_1", "phone_2"],
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_PUSH_ALERTS_ENABLED] is True
        assert entry.options[CONF_PUSH_ALERT_DEVICE_IDS] == ["phone_1", "phone_2"]
        assert entry.options[OPT_ZONES] == []

        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()


async def test_options_flow_add_zone_validation_errors(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_RADIATION_SOURCE_ENTITY: "sensor.solar_radiation",
            CONF_RADIATION_SOURCE_UNIT: UNIT_W_PER_M2,
        },
        options={OPT_ZONES: []},
        title="Irrigation Computer",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.irrigation_computer.IrrigationController.async_initialize"
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "add_zone"}
        )
        # Schema enforces fallback_minutes >= 5; empty name is caught in _validate_zone.
        bad_payload = {
            ZONE_NAME: "",
            ZONE_RELAY_ENTITY: "switch.test_relay",
            ZONE_WATERING_DURATION: 30,
            ZONE_PHASE: PHASE_PLANTING,
            ZONE_THRESHOLD_PLANTING: 50.0,
            ZONE_THRESHOLD_FRUIT_SET: 100.0,
            ZONE_THRESHOLD_RIPENING: 80.0,
            ZONE_POWER_ALERT_DELAY: 0,
            ZONE_POWER_MIN: 5.0,
            ZONE_POWER_MAX: 500.0,
            ZONE_MAX_RUNS_24H: 0,
            ZONE_FALLBACK_ENABLED: True,
            ZONE_FALLBACK_MINUTES: 60,
            ZONE_FALLBACK_START: "06:00:00",
            ZONE_FALLBACK_END: "20:00:00",
            ZONE_RADIATION_TRIGGER_ENABLED: True,
        }
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], bad_payload
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"][ZONE_NAME] == "name_required"

        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
