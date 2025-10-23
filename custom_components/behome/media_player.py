"""Platform for media_player integration."""
import asyncio
import unicodedata
from typing import Any, Dict

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_MEDIA_PLAYER
from .api import BemfaAPI



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome media players from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

    # Track already added device IDs
    added_device_ids = set()

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return
        
        devices = coordinator.data
        mp_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_MEDIA_PLAYER
        ]

        new_mps = [
            BeHomeMediaPlayer(coordinator, api, device)
            for device in mp_devices
            if device["deviceID"] not in added_device_ids
        ]

        if new_mps:
            # Track the new device IDs
            for entity in new_mps:
                added_device_ids.add(entity._device_id)
            async_add_entities(new_mps)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Representation of a BeHome Media Player."""

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the media player."""
        super().__init__(coordinator)
        self._api = api
        self._topic = device["topic"]
        self._device_id = device["deviceID"]
        self._device = device # Store device object
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
        self._attr_icon = "mdi:television"
        self._attr_supported_features = (
            MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return False
        return device.get("num", False)

    @property
    def _current_device_state(self) -> str:
        """Get the latest state for this specific device from the coordinator."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        return device.get("state", "off") if device else "off"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        return MediaPlayerState.ON if self._current_device_state != "off" else MediaPlayerState.OFF

    async def _send_command(self, msg: str):
        """Send a command to the device."""
        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._send_command("on")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._send_command("off")

    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        await self._send_command("volup")

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._send_command("voldown")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._send_command("chup")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._send_command("chdown")

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart TV",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
