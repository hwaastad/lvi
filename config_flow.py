"""Adds config flow for Lvi integration."""
from lvi import Lvi
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class LviConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lvi integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={},
            )

        username = user_input[CONF_USERNAME].replace(" ", "")
        password = user_input[CONF_PASSWORD].replace(" ", "")

        lvi_data_connection = Lvi(
            username,
            password,
            websession=async_get_clientsession(self.hass),
        )

        errors = {}

        if not await lvi_data_connection.connect():
            errors["cannot_connect"] = "cannot_connect"
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=errors,
            )

        unique_id = username

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={CONF_USERNAME: username, CONF_PASSWORD: password},
        )
