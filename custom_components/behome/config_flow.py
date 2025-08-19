"""Config flow for BeHome integration."""
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    DOMAIN,
    CONF_PRIVATE_KEY,
    OAUTH2_CLIENT_ID,
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_TOKEN_URL,
)


@config_entries.HANDLERS.register(DOMAIN)
class BeHomeConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """The main config flow. It starts by showing a menu."""

    DOMAIN = DOMAIN
    VERSION = 1

    @staticmethod
    def async_get_implementations(
        hass: HomeAssistant,
    ) -> list[config_entry_oauth2_flow.AbstractOAuth2Implementation]:
        """Return a list of OAuth2 implementations."""
        return [
            config_entry_oauth2_flow.LocalOAuth2Implementation(
                hass,
                DOMAIN,
                "88ac425b4558463aa813aed1690db730",
                "",
                OAUTH2_AUTHORIZE_URL,
                OAUTH2_TOKEN_URL,
            )
        ]


    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow after successful authorization."""
        access_token = data["token"]["access_token"]
        if len(access_token) > 8:  # Need at least 9 characters to remove first 4 and last 4
            private_key = access_token[4:-4]  # Remove first 4 and last 4 characters
        else:
            self.logger.error("Received access token is too short.")
            return self.async_abort(reason="invalid_token")

        data[CONF_PRIVATE_KEY] = private_key
        return self.async_create_entry(title="BeHome", data=data)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["oauth", "manual"],
        )

    async def async_step_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the OAuth2 flow."""
        return await self.async_step_pick_implementation()

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the manual private key entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_PRIVATE_KEY):
                return self.async_create_entry(
                    title="BeHome (Manual)", data=user_input
                )
            errors["base"] = "empty_key"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_PRIVATE_KEY): str}),
            errors=errors,
        )