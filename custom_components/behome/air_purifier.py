"""Platform for air_purifier integration."""
import asyncio
import unicodedata
from typing import Any

from homeassistant.components.air_purifier import (
    AirPurifierEntity,
    AirPurifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_AIR_PURIFIER
from .api import BemfaAPI

PRESET_MODES = ["auto", "sleep", "strong"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome air purifiers from a config entry."""
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
        ap_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_AIR_PURIFIER
        ]

        new_aps = [
            BeHomeAirPurifier(coordinator, api, device)
            for device in ap_devices
            if device["deviceID"] not in added_device_ids
        ]

        if new_aps:
            # Track the new device IDs
            for entity in new_aps:
                added_device_ids.add(entity._device_id)
            async_add_entities(new_aps)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeAirPurifier(CoordinatorEntity, AirPurifierEntity):
    """Representation of a BeHome Air Purifier."""
    _attr_icon = "mdi:air-purifier"
    _attr_supported_features = AirPurifierEntityFeature.PRESET_MODE
    _attr_preset_modes = PRESET_MODES

    def __init__(self, coordinator, api: BemfaAPI, device: dict[str, Any]):
        """Initialize the air purifier."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._device_id = device["deviceID"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"

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
    def _current_device_state_parts(self) -> list[str]:
        """Get the latest state for this device, split by comma."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        return device.get("state", "").split(",") if device else []

    @property
    def is_on(self) -> bool:
        """Return true if the device is on."""
        parts = self._current_device_state_parts
        return parts and parts[0] != "off"

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        parts = self._current_device_state_parts
        return parts[1] if self.is_on and len(parts) > 1 else None

    async def _send_command(self, msg: str):
        """Send a command to the device."""
        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._send_command("on")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._send_command("off")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Invalid preset mode: {preset_mode}")
        
        await self._send_command(f"set,{preset_mode}")

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Air Purifier",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
