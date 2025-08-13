from homeassistant.components.application_credentials import AuthImplementation, AuthorizationServer, ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


class OAuth2Impl(AuthImplementation):
    """Custom OAuth2 implementation."""


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""

    return config_entry_oauth2_flow.LocalOAuth2Implementation(
        hass,
        auth_domain,
        ClientCredential(
            client_id="88ac425b4558463aa813aed1690db730",
            client_secret="88ac425b4558463aa813aed1690db740",
            name="BeHomeUltimate"
        ),
        AuthorizationServer(
            authorize_url="https://cloud.bemfa.com/web/mi/index.html",
            token_url="https://pro.bemfa.com/vs/speaker/v1/haToken"
        )
    )
