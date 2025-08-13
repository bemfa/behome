"""The BeHome integration."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, area_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_PRIVATE_KEY,
    OAUTH2_CLIENT_ID,
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_TOKEN_URL,
)
from .api import BemfaAPI

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the BeHome component."""
    hass.data.setdefault(DOMAIN, {})

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            OAUTH2_CLIENT_ID,
            "",
            OAUTH2_AUTHORIZE_URL,
            OAUTH2_TOKEN_URL,
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BeHome from a config entry."""
    # --- Area Registry Mapping ---
    # Create a mapping from area name to area_id for efficient lookup.
    ar = area_registry.async_get(hass)
    area_map = {area.name.lower(): area.id for area in ar.async_list_areas()}
    # --- End Area Registry Mapping ---

    private_key = entry.data.get(CONF_PRIVATE_KEY)
    
    # Handle manually entered keys that are not in the 'token' dict
    if not private_key:
        private_key = entry.data["token"]["access_token"][4:-1]


    session = async_get_clientsession(hass)
    api = BemfaAPI(private_key, session)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="behome_devices",
        update_method=api.get_devices,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "area_map": area_map,  # Store the map for platforms to use
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
