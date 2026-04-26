"""Config flow for the Irrigation Computer integration."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_PUSH_ALERT_DEVICE_IDS,
    CONF_PUSH_ALERTS_ENABLED,
    CONF_RADIATION_SOURCE_ENTITY,
    CONF_RADIATION_SOURCE_UNIT,
    DEFAULT_FALLBACK_END,
    DEFAULT_FALLBACK_MINUTES,
    DEFAULT_FALLBACK_START,
    DEFAULT_MAX_RUNS_24H,
    DEFAULT_POWER_ALERT_DELAY,
    DEFAULT_POWER_MAX,
    DEFAULT_POWER_MIN,
    DEFAULT_PUSH_ALERTS_ENABLED,
    DEFAULT_RADIATION_SOURCE_UNIT,
    DEFAULT_THRESHOLD_FRUIT_SET,
    DEFAULT_THRESHOLD_PLANTING,
    DEFAULT_THRESHOLD_RIPENING,
    DEFAULT_WATERING_DURATION,
    DOMAIN,
    OPT_ZONES,
    PHASES,
    PHASE_PLANTING,
    UNIT_W_PER_M2,
    UNIT_WH_PER_M2,
    ZONE_FALLBACK_ENABLED,
    ZONE_FALLBACK_END,
    ZONE_FALLBACK_MINUTES,
    ZONE_FALLBACK_START,
    ZONE_ID,
    ZONE_MAX_RUNS_24H,
    ZONE_NAME,
    ZONE_PHASE,
    ZONE_POWER_ALERT_DELAY,
    ZONE_POWER_ENTITY,
    ZONE_POWER_MAX,
    ZONE_POWER_MIN,
    ZONE_RADIATION_TRIGGER_ENABLED,
    ZONE_RELAY_ENTITY,
    ZONE_THRESHOLD_FRUIT_SET,
    ZONE_THRESHOLD_PLANTING,
    ZONE_THRESHOLD_RIPENING,
    ZONE_WATERING_DURATION,
)
from .util import normalize_device_ids

_LOGGER = logging.getLogger(__name__)


def _radiation_unit_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[UNIT_W_PER_M2, UNIT_WH_PER_M2],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _phase_selector() -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(PHASES),
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key="phase",
        )
    )


def _initial_global_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_RADIATION_SOURCE_ENTITY,
                default=defaults.get(CONF_RADIATION_SOURCE_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_RADIATION_SOURCE_UNIT,
                default=defaults.get(
                    CONF_RADIATION_SOURCE_UNIT, DEFAULT_RADIATION_SOURCE_UNIT
                ),
            ): _radiation_unit_selector(),
            vol.Required(
                CONF_PUSH_ALERTS_ENABLED,
                default=defaults.get(
                    CONF_PUSH_ALERTS_ENABLED, DEFAULT_PUSH_ALERTS_ENABLED
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_PUSH_ALERT_DEVICE_IDS,
                default=normalize_device_ids(defaults.get(CONF_PUSH_ALERT_DEVICE_IDS)),
            ): selector.DeviceSelector(
                selector.DeviceSelectorConfig(
                    integration="mobile_app",
                    multiple=True,
                )
            ),
        }
    )


def _zone_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                ZONE_NAME, default=defaults.get(ZONE_NAME, "")
            ): selector.TextSelector(),
            vol.Required(
                ZONE_RELAY_ENTITY,
                default=defaults.get(ZONE_RELAY_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="switch")
            ),
            vol.Optional(
                ZONE_POWER_ENTITY,
                default=defaults.get(ZONE_POWER_ENTITY) or vol.UNDEFINED,
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                ZONE_WATERING_DURATION,
                default=defaults.get(
                    ZONE_WATERING_DURATION, DEFAULT_WATERING_DURATION
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=10, max=3600, step=10, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_PHASE, default=defaults.get(ZONE_PHASE, PHASE_PLANTING)
            ): _phase_selector(),
            vol.Required(
                ZONE_THRESHOLD_PLANTING,
                default=defaults.get(
                    ZONE_THRESHOLD_PLANTING, DEFAULT_THRESHOLD_PLANTING
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_THRESHOLD_FRUIT_SET,
                default=defaults.get(
                    ZONE_THRESHOLD_FRUIT_SET, DEFAULT_THRESHOLD_FRUIT_SET
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_THRESHOLD_RIPENING,
                default=defaults.get(
                    ZONE_THRESHOLD_RIPENING, DEFAULT_THRESHOLD_RIPENING
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=1000, step=5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_POWER_ALERT_DELAY,
                default=defaults.get(
                    ZONE_POWER_ALERT_DELAY, DEFAULT_POWER_ALERT_DELAY
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=300, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_POWER_MIN,
                default=defaults.get(ZONE_POWER_MIN, DEFAULT_POWER_MIN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=10000, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_POWER_MAX,
                default=defaults.get(ZONE_POWER_MAX, DEFAULT_POWER_MAX),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=10000, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_MAX_RUNS_24H,
                default=defaults.get(ZONE_MAX_RUNS_24H, DEFAULT_MAX_RUNS_24H),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, max=50, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_FALLBACK_ENABLED,
                default=defaults.get(ZONE_FALLBACK_ENABLED, True),
            ): selector.BooleanSelector(),
            vol.Required(
                ZONE_FALLBACK_MINUTES,
                default=defaults.get(
                    ZONE_FALLBACK_MINUTES, DEFAULT_FALLBACK_MINUTES
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=240, step=5, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                ZONE_FALLBACK_START,
                default=defaults.get(ZONE_FALLBACK_START, DEFAULT_FALLBACK_START),
            ): selector.TimeSelector(),
            vol.Required(
                ZONE_FALLBACK_END,
                default=defaults.get(ZONE_FALLBACK_END, DEFAULT_FALLBACK_END),
            ): selector.TimeSelector(),
            vol.Required(
                ZONE_RADIATION_TRIGGER_ENABLED,
                default=defaults.get(ZONE_RADIATION_TRIGGER_ENABLED, True),
            ): selector.BooleanSelector(),
        }
    )


def _validate_zone(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input.get(ZONE_NAME):
        errors[ZONE_NAME] = "name_required"
    if not user_input.get(ZONE_RELAY_ENTITY):
        errors[ZONE_RELAY_ENTITY] = "relay_required"
    mins = user_input.get(ZONE_FALLBACK_MINUTES, DEFAULT_FALLBACK_MINUTES)
    try:
        mins_int = int(mins)
    except (TypeError, ValueError):
        errors[ZONE_FALLBACK_MINUTES] = "fallback_minutes_range"
    else:
        if mins_int < 5 or mins_int > 240:
            errors[ZONE_FALLBACK_MINUTES] = "fallback_minutes_range"
    return errors


def _normalize_zone_input(user_input: dict[str, Any]) -> dict[str, Any]:
    out = dict(user_input)
    out[ZONE_WATERING_DURATION] = int(out.get(ZONE_WATERING_DURATION, DEFAULT_WATERING_DURATION))
    out[ZONE_POWER_ALERT_DELAY] = int(
        out.get(ZONE_POWER_ALERT_DELAY, DEFAULT_POWER_ALERT_DELAY)
    )
    out[ZONE_MAX_RUNS_24H] = int(out.get(ZONE_MAX_RUNS_24H, DEFAULT_MAX_RUNS_24H))
    out[ZONE_FALLBACK_MINUTES] = int(out.get(ZONE_FALLBACK_MINUTES, DEFAULT_FALLBACK_MINUTES))
    for key in (
        ZONE_THRESHOLD_PLANTING,
        ZONE_THRESHOLD_FRUIT_SET,
        ZONE_THRESHOLD_RIPENING,
        ZONE_POWER_MIN,
        ZONE_POWER_MAX,
    ):
        out[key] = float(out.get(key, 0))
    if not out.get(ZONE_POWER_ENTITY):
        out[ZONE_POWER_ENTITY] = None
    return out


class IrrigationComputerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(
                title="Irrigation Computer",
                data={
                    CONF_RADIATION_SOURCE_ENTITY: user_input.get(
                        CONF_RADIATION_SOURCE_ENTITY
                    ),
                    CONF_RADIATION_SOURCE_UNIT: user_input.get(
                        CONF_RADIATION_SOURCE_UNIT, DEFAULT_RADIATION_SOURCE_UNIT
                    ),
                    CONF_PUSH_ALERTS_ENABLED: bool(
                        user_input.get(
                            CONF_PUSH_ALERTS_ENABLED,
                            DEFAULT_PUSH_ALERTS_ENABLED,
                        )
                    ),
                    CONF_PUSH_ALERT_DEVICE_IDS: normalize_device_ids(
                        user_input.get(CONF_PUSH_ALERT_DEVICE_IDS)
                    ),
                },
                options={OPT_ZONES: []},
            )
        return self.async_show_form(
            step_id="user", data_schema=_initial_global_schema()
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "IrrigationComputerOptionsFlow":
        return IrrigationComputerOptionsFlow()


class IrrigationComputerOptionsFlow(OptionsFlow):
    """Multi-step options flow: global / add / edit / delete zones."""

    def __init__(self) -> None:
        # NOTE: Don't assign self.config_entry here.  In HA 2024.12+ that's a
        # read-only property on the OptionsFlow base class, set automatically
        # from the entry the user clicked "Configure" on.
        self._edit_zone_id: str | None = None

    # ----------------------------------------------- helpers

    @property
    def _zones(self) -> list[dict[str, Any]]:
        return list(self.config_entry.options.get(OPT_ZONES, []))

    def _zone_choices(self) -> dict[str, str]:
        return {
            z[ZONE_ID]: z.get(ZONE_NAME, z[ZONE_ID]) for z in self._zones
        }

    def _save_zones(self, zones: list[dict[str, Any]]) -> ConfigFlowResult:
        new_options = dict(self.config_entry.options)
        new_options[OPT_ZONES] = zones
        return self.async_create_entry(title="", data=new_options)

    # ----------------------------------------------- menu

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "global_settings",
                "add_zone",
                "edit_zone_select",
                "delete_zone_select",
            ],
        )

    # ----------------------------------------------- global

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        defaults = {
            CONF_RADIATION_SOURCE_ENTITY: self.config_entry.options.get(
                CONF_RADIATION_SOURCE_ENTITY,
                self.config_entry.data.get(CONF_RADIATION_SOURCE_ENTITY),
            ),
            CONF_RADIATION_SOURCE_UNIT: self.config_entry.options.get(
                CONF_RADIATION_SOURCE_UNIT,
                self.config_entry.data.get(
                    CONF_RADIATION_SOURCE_UNIT, DEFAULT_RADIATION_SOURCE_UNIT
                ),
            ),
            CONF_PUSH_ALERTS_ENABLED: self.config_entry.options.get(
                CONF_PUSH_ALERTS_ENABLED,
                self.config_entry.data.get(
                    CONF_PUSH_ALERTS_ENABLED, DEFAULT_PUSH_ALERTS_ENABLED
                ),
            ),
            CONF_PUSH_ALERT_DEVICE_IDS: normalize_device_ids(
                self.config_entry.options.get(
                    CONF_PUSH_ALERT_DEVICE_IDS,
                    self.config_entry.data.get(CONF_PUSH_ALERT_DEVICE_IDS, []),
                )
            ),
        }
        if user_input is not None:
            new_options = dict(self.config_entry.options)
            new_options[CONF_RADIATION_SOURCE_ENTITY] = user_input.get(
                CONF_RADIATION_SOURCE_ENTITY
            )
            new_options[CONF_RADIATION_SOURCE_UNIT] = user_input.get(
                CONF_RADIATION_SOURCE_UNIT, DEFAULT_RADIATION_SOURCE_UNIT
            )
            new_options[CONF_PUSH_ALERTS_ENABLED] = bool(
                user_input.get(
                    CONF_PUSH_ALERTS_ENABLED,
                    DEFAULT_PUSH_ALERTS_ENABLED,
                )
            )
            new_options[CONF_PUSH_ALERT_DEVICE_IDS] = normalize_device_ids(
                user_input.get(CONF_PUSH_ALERT_DEVICE_IDS)
            )
            new_options.setdefault(OPT_ZONES, self._zones)
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="global_settings",
            data_schema=_initial_global_schema(defaults),
        )

    # ----------------------------------------------- add zone

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_zone(user_input)
            if not errors:
                zones = self._zones
                new_zone = _normalize_zone_input(user_input)
                new_zone[ZONE_ID] = uuid.uuid4().hex
                zones.append(new_zone)
                return self._save_zones(zones)

        return self.async_show_form(
            step_id="add_zone",
            data_schema=_zone_schema(user_input or {}),
            errors=errors,
        )

    # ----------------------------------------------- edit zone

    async def async_step_edit_zone_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        choices = self._zone_choices()
        if not choices:
            return self.async_abort(reason="zone_updated")

        if user_input is not None:
            self._edit_zone_id = user_input[ZONE_ID]
            return await self.async_step_edit_zone()

        return self.async_show_form(
            step_id="edit_zone_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ZONE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=zid, label=label)
                                for zid, label in choices.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._edit_zone_id is None:
            return await self.async_step_edit_zone_select()

        zones = self._zones
        existing = next(
            (z for z in zones if z[ZONE_ID] == self._edit_zone_id), None
        )
        if existing is None:
            return await self.async_step_edit_zone_select()

        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_zone(user_input)
            if not errors:
                normalized = _normalize_zone_input(user_input)
                normalized[ZONE_ID] = self._edit_zone_id
                zones = [
                    normalized if z[ZONE_ID] == self._edit_zone_id else z
                    for z in zones
                ]
                return self._save_zones(zones)

        return self.async_show_form(
            step_id="edit_zone",
            data_schema=_zone_schema(user_input or existing),
            errors=errors,
        )

    # ----------------------------------------------- delete zone

    async def async_step_delete_zone_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        choices = self._zone_choices()
        if not choices:
            return self.async_abort(reason="zone_deleted")

        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get("confirm"):
                errors["confirm"] = "not_confirmed"
            else:
                zid = user_input[ZONE_ID]
                zones = [z for z in self._zones if z[ZONE_ID] != zid]
                return self._save_zones(zones)

        return self.async_show_form(
            step_id="delete_zone_select",
            data_schema=vol.Schema(
                {
                    vol.Required(ZONE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=zid, label=label)
                                for zid, label in choices.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("confirm", default=False): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )
