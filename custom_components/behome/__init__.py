"""The BeHome integration."""
import asyncio
import logging
from datetime import timedelta
import time

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

SCAN_INTERVAL = timedelta(seconds=5)


class DummyLogger:
    """A dummy logger that does nothing but satisfies the coordinator's requirements."""
    
    def isEnabledFor(self, level):
        return False
    
    def debug(self, *args, **kwargs):
        pass
    
    def info(self, *args, **kwargs):
        pass
    
    def warning(self, *args, **kwargs):
        pass
    
    def error(self, *args, **kwargs):
        pass


class SmartDataUpdateCoordinator(DataUpdateCoordinator):
    """Smart coordinator that avoids duplicate refreshes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_manual_refresh = 0
        self._manual_refresh_cooldown = 8  # Increased to 8 seconds
        self._locked_devices = {}  # topic -> lock_end_time
        self._device_lock_duration = 5  # Lock device state for 5 seconds
        
    def update_device_state_immediately(self, topic: str, new_state: dict):
        """Update device state immediately in local cache and lock it."""
        if not self.data:
            return
            
        # Lock this device state to prevent overwrite by polling
        self._locked_devices[topic] = time.time() + self._device_lock_duration
            
        # Find and update the device in the cached data
        for device in self.data:
            if device.get("topic") == topic:
                device.update(new_state)
                break
        
        # Notify all listeners about the state change
        self.async_update_listeners()
        
    async def async_request_refresh_after_delay(self, delay: float = 3.0):
        """Request refresh after delay, avoiding conflicts with regular polling."""
        await asyncio.sleep(delay)
        self._last_manual_refresh = time.time()
        await self.async_request_refresh()
        
    async def _async_update_data(self):
        """Fetch data with smart refresh logic."""
        # Skip this update if a manual refresh happened recently
        if time.time() - self._last_manual_refresh < self._manual_refresh_cooldown:
            return self.data
            
        # Get fresh data from API
        new_data = await super()._async_update_data()
        
        # If we have locked devices, preserve their state
        if self._locked_devices and new_data:
            current_time = time.time()
            # Remove expired locks
            self._locked_devices = {
                topic: end_time for topic, end_time in self._locked_devices.items()
                if end_time > current_time
            }
            
            # Restore locked device states
            if self.data and self._locked_devices:
                for device in new_data:
                    topic = device.get("topic")
                    if topic in self._locked_devices:
                        # Find the locked state from current data
                        for old_device in self.data:
                            if old_device.get("topic") == topic:
                                # Preserve the locked state
                                device.update({
                                    "msg": old_device.get("msg"),
                                    "state": old_device.get("state", device.get("state"))
                                })
                                break
        
        return new_data


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the BeHome component."""
    hass.data.setdefault(DOMAIN, {})

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            "88ac425b4558463aa813aed1690db730",
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
    
    # Handle OAuth2 access_token: remove first 4 and last 4 characters to get real private key
    if not private_key:
        access_token = entry.data["token"]["access_token"]
        private_key = access_token[4:-4]


    session = async_get_clientsession(hass)
    api = BemfaAPI(private_key, session)

    coordinator = SmartDataUpdateCoordinator(
        hass,
        DummyLogger(),
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
