"""Platform for light integration."""
import asyncio
from typing import Any, Dict
import unicodedata

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    LightEntity,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_LIGHT
from .api import BemfaAPI



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome lights from a config entry."""
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
        light_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_LIGHT
        ]

        # Create entities for all discovered devices.
        # Home Assistant will handle matching them to existing entities.
        new_lights = [
            BeHomeLight(coordinator, api, device)
            for device in light_devices
            if device["deviceID"] not in added_device_ids
        ]

        if new_lights:
            # Track the new device IDs
            for entity in new_lights:
                added_device_ids.add(entity._device_id)
            async_add_entities(new_lights)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeLight(CoordinatorEntity, LightEntity):
    """Representation of a BeHome Light."""
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the light."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._device_id = device["deviceID"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"

    def _supports_brightness(self) -> bool:
        """Check if device supports brightness adjustment."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return False
        return device.get("attr1") is True

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return supported color modes."""
        if self._supports_brightness():
            return {ColorMode.BRIGHTNESS}
        return {ColorMode.ONOFF}

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS if self._supports_brightness() else ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return False
        
        msg = device.get("msg")
        if isinstance(msg, dict):
            return msg.get("on") is True
        
        # Fallback for older string-based states
        return isinstance(msg, str) and msg.startswith("on")

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
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        if not self._supports_brightness():
            return None
            
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return None

        msg = device.get("msg")
        
        if isinstance(msg, dict):
            # Check if device is on
            if not msg.get("on"):
                return 0
                
            # If device has bri field, use it
            if "bri" in msg:
                try:
                    bri_val = int(msg["bri"])
                    return int(bri_val / 100 * 255)
                except (ValueError, TypeError):
                    pass
            
            # If device is on but no bri field, return 100%
            return 255
        elif isinstance(msg, str):
            if msg == "off":
                return 0
            elif msg.startswith("on,"):
                # Old string format: "on,80"
                try:
                    bri_val = int(msg.split(",")[1])
                    return int(bri_val / 100 * 255)
                except (ValueError, IndexError):
                    return 255
            elif msg == "on":
                return 255
            
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        
        if self._supports_brightness() and brightness is not None:
            # Device supports brightness and brightness was specified
            bri_val = int(brightness / 255 * 100)
            msg = f"set,{bri_val}"
            
            # Update local state immediately
            self.coordinator.update_device_state_immediately(self._device_id, {
                "msg": {"on": True, "bri": bri_val}
            })
        else:
            # Simple on command
            msg = "on"
            
            # Update local state immediately
            if self._supports_brightness():
                # If supports brightness but no brightness specified, set to 100%
                self.coordinator.update_device_state_immediately(self._device_id, {
                    "msg": {"on": True}
                })
            else:
                self.coordinator.update_device_state_immediately(self._device_id, {
                    "msg": {"on": True}
                })
        
        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        # Update local state immediately
        if self._supports_brightness():
            self.coordinator.update_device_state_immediately(self._device_id, {
                "msg": {"on": False, "bri": 0}
            })
        else:
            self.coordinator.update_device_state_immediately(self._device_id, {
                "msg": {"on": False}
            })
        
        await self._api.control_device(self._topic, "off", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Light",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
