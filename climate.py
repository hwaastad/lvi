"""Support for LVI wifi-enabled home heaters."""
import logging

from lvi import Lvi
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.components.climate.const import (
    FAN_ON,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_AWAY_TEMP,
    ATTR_COMFORT_TEMP,
    ATTR_ROOM_NAME,
    ATTR_SLEEP_TEMP,
    DOMAIN,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_SET_ROOM_TEMP,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

SET_ROOM_TEMP_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ROOM_NAME): cv.string,
        vol.Optional(ATTR_AWAY_TEMP): cv.positive_int,
        vol.Optional(ATTR_COMFORT_TEMP): cv.positive_int,
        vol.Optional(ATTR_SLEEP_TEMP): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the LVI heater."""
    lvi_data_connection = Lvi(
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        websession=async_get_clientsession(hass),
    )
    if not await lvi_data_connection.connect():
        _LOGGER.error("Failed to connect to LVI")
        return

    await lvi_data_connection.find_all_heaters()

    dev = []
    for heater in lvi_data_connection.heaters.values():
        dev.append(LviHeater(heater, lvi_data_connection))
    async_add_entities(dev)

    async def set_room_temp(service):
        """Set room temp."""
        room_name = service.data.get(ATTR_ROOM_NAME)
        sleep_temp = service.data.get(ATTR_SLEEP_TEMP)
        comfort_temp = service.data.get(ATTR_COMFORT_TEMP)
        away_temp = service.data.get(ATTR_AWAY_TEMP)
        await lvi_data_connection.set_room_temperatures_by_name(
            room_name, sleep_temp, comfort_temp, away_temp
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM_TEMP, set_room_temp, schema=SET_ROOM_TEMP_SCHEMA
    )


class LviHeater(ClimateDevice):
    """Representation of a LVI Thermostat device."""

    def __init__(self, heater,lvi_data_connection):
        """Initialize the thermostat."""
        self._heater = heater
        self._conn = lvi_data_connection

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return True if entity is available."""
        """TODO: Check up when oven is turned off"""
        #return self._heater.available
        return True

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.id_device

    @property
    def name(self):
        """Return the name of the entity."""
        return self._heater.nom_appareil

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        res = {
            "heating": self._heater.heating_up == '1'
        }
        if self._heater.room:
            res["room"] = self._heater.room.name
        else:
            res["room"] = "Independent device"
        return res

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._heater.consigne_confort

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._heater.current_temp

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return FAN_ON if self._heater.fan_speed != 0 else HVAC_MODE_OFF

    @property
    def fan_modes(self):
        """List of available fan modes."""
        return [FAN_ON, HVAC_MODE_OFF]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMP

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        """
        if self._heater.heating_up == '1':
            return HVAC_MODE_HEAT
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES.
        """
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._conn.set_heater_temp(self._heater.id_device, int(temperature))

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        fan_status = 1 if fan_mode == FAN_ON else 0
        await self._conn.heater_control(self._heater.id_device, fan_status=fan_status)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self._conn.heater_control(self._heater.id_device, power_status=1)
        elif hvac_mode == HVAC_MODE_OFF:
            await self._conn.heater_control(self._heater.id_device, power_status=0)

    async def async_update(self):
        """Retrieve latest state."""
        self._heater = await self._conn.update_device(self._heater.id_device)