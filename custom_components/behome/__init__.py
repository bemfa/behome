"""The BeHome integration."""
import asyncio
from datetime import timedelta
import hashlib
import logging
import time

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import (
    area_registry,
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_PRIVATE_KEY,
    CONF_SELECTED_DEVICES,
    CONF_SYNC_MODE,
    OAUTH2_CLIENT_ID,
    OAUTH2_AUTHORIZE_URL,
    OAUTH2_TOKEN_URL,
    SYNC_MODE_MANUAL,
)
from .api import BemfaAPI

SCAN_INTERVAL = timedelta(seconds=5)
_LOGGER = logging.getLogger(__name__)
_DEFAULT_ENTRY_TITLES = {"BeHome", "BeHome (WeChat)", "BeHome (Manual)"}

# This integration can only be configured via config entries
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class SmartDataUpdateCoordinator(DataUpdateCoordinator):
    """Smart coordinator that avoids duplicate refreshes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_manual_refresh = 0
        self._manual_refresh_cooldown = 8  # Increased to 8 seconds
        self._locked_devices = {}  # deviceID -> lock_end_time
        self._device_lock_duration = 5  # Lock device state for 5 seconds

    def update_device_state_immediately(self, device_id: str, new_state: dict):
        """Update device state immediately in local cache and lock it."""
        if not self.data:
            return

        # Lock this device state to prevent overwrite by polling
        self._locked_devices[device_id] = time.time() + self._device_lock_duration

        # Find and update the device in the cached data
        for device in self.data:
            if device.get("deviceID") == device_id:
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
                    device_id = device.get("deviceID")
                    if device_id in self._locked_devices:
                        # Find the locked state from current data
                        for old_device in self.data:
                            if old_device.get("deviceID") == device_id:
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

    private_key = _private_key_from_entry(entry)
    if not private_key:
        _LOGGER.error("BeHome config entry does not contain a valid private key")
        return False

    unique_id = _unique_id_from_private_key(private_key)
    entry_updates = {}
    if entry.data.get(CONF_PRIVATE_KEY) != private_key:
        entry_updates["data"] = {CONF_PRIVATE_KEY: private_key}
    if entry.unique_id != unique_id:
        entry_updates["unique_id"] = unique_id
    if entry.title in _DEFAULT_ENTRY_TITLES:
        entry_title = _entry_title_from_private_key(private_key)
        if entry.title != entry_title:
            entry_updates["title"] = entry_title

    if entry_updates:
        hass.config_entries.async_update_entry(
            entry,
            **entry_updates,
        )

    session = async_get_clientsession(hass)
    api = BemfaAPI(private_key, session)

    async def _async_get_filtered_devices():
        """Fetch devices and apply the configured sync mode."""
        devices = await api.get_devices()
        return _filter_devices_for_entry(entry, devices)

    coordinator = SmartDataUpdateCoordinator(
        hass,
        _LOGGER,
        name="behome_devices",
        update_method=_async_get_filtered_devices,
        update_interval=SCAN_INTERVAL,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "area_map": area_map,  # Store the map for platforms to use
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _schedule_remove_unselected_manual_devices(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _filter_devices_for_entry(
    entry: ConfigEntry, devices: list[dict]
) -> list[dict]:
    """Filter BeHome devices according to the configured sync mode."""
    if entry.options.get(CONF_SYNC_MODE) != SYNC_MODE_MANUAL:
        return devices

    selected_devices = entry.options.get(CONF_SELECTED_DEVICES, [])
    if not isinstance(selected_devices, list):
        return []

    selected_device_ids = {str(device_id) for device_id in selected_devices}
    return [
        device
        for device in devices
        if str(device.get("deviceID", "")) in selected_device_ids
    ]


def _remove_unselected_manual_devices(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove BeHome registry entries that are not selected in manual mode."""
    if entry.options.get(CONF_SYNC_MODE) != SYNC_MODE_MANUAL:
        return

    selected_devices = entry.options.get(CONF_SELECTED_DEVICES, [])
    if not isinstance(selected_devices, list):
        selected_devices = []
    selected_device_ids = {str(device_id) for device_id in selected_devices}

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    stale_device_entry_ids = set()
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        behome_device_id = _behome_device_id_from_device_entry(device_entry)
        if behome_device_id is None or behome_device_id in selected_device_ids:
            continue
        stale_device_entry_ids.add(device_entry.id)

    stale_entity_ids = [
        entity_entry.entity_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if (
            entity_entry.platform == DOMAIN
            and entity_entry.device_id in stale_device_entry_ids
        )
    ]
    for entity_id in stale_entity_ids:
        entity_registry.async_remove(entity_id)

    for device_entry_id in stale_device_entry_ids:
        device_registry.async_remove_device(device_entry_id)

    if stale_entity_ids or stale_device_entry_ids:
        _LOGGER.info(
            "Removed %d unselected BeHome entities and %d devices from registry",
            len(stale_entity_ids),
            len(stale_device_entry_ids),
        )


def _behome_device_id_from_device_entry(device_entry: dr.DeviceEntry) -> str | None:
    """Return the BeHome cloud device ID from a device registry entry."""
    for identifier_domain, identifier_value in device_entry.identifiers:
        if identifier_domain == DOMAIN:
            return str(identifier_value)
    return None


def _schedule_remove_unselected_manual_devices(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove unselected devices after HA startup registry writes are stable."""
    if entry.options.get(CONF_SYNC_MODE) != SYNC_MODE_MANUAL:
        return

    if hass.is_running:
        _remove_unselected_manual_devices(hass, entry)
        return

    def _async_remove_after_start(_event: Event) -> None:
        _remove_unselected_manual_devices(hass, entry)

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _async_remove_after_start
        )
    )


def _private_key_from_entry(entry: ConfigEntry) -> str | None:
    """Extract the private key from a current or legacy config entry."""
    private_key = entry.data.get(CONF_PRIVATE_KEY)
    if isinstance(private_key, str) and private_key:
        return private_key

    token = entry.data.get("token")
    access_token = token.get("access_token") if isinstance(token, dict) else None
    if isinstance(access_token, str) and len(access_token) > 8:
        return access_token[4:-4]

    return None


def _unique_id_from_private_key(private_key: str) -> str:
    """Return a stable, non-secret unique ID for a private key."""
    return hashlib.sha256(private_key.encode("utf-8")).hexdigest()


def _entry_title_from_private_key(private_key: str) -> str:
    """Return the config entry title for a BeHome account."""
    return f"BeHome ({private_key[-6:]})"
