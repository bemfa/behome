"""Platform for light integration."""
import logging
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

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome lights from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

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
            BeHomeLight(coordinator, api, device) for device in light_devices
        ]
        
        if new_lights:
            async_add_entities(new_lights)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeLight(CoordinatorEntity, LightEntity):
    """Representation of a BeHome Light."""
    _attr_icon = "mdi:lightbulb"
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the light."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        if not device:
            return False
        
        msg = device.get("msg")
        if isinstance(msg, dict):
            return msg.get("on") is True
        
        # Fallback for older string-based states
        return isinstance(msg, str) and msg.startswith("on")

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        if not device:
            return None

        msg = device.get("msg")
        brightness_val = None

        if isinstance(msg, dict):
            # New JSON format: {"on": true, "brightness": 80}
            if msg.get("on") and "brightness" in msg:
                try:
                    brightness_val = int(msg["brightness"])
                except (ValueError, TypeError):
                    pass
        elif isinstance(msg, str) and msg.startswith("on,"):
            # Old string format: "on,80"
            try:
                brightness_val = int(msg.split(",")[1])
            except (ValueError, IndexError):
                pass
        
        if brightness_val is not None:
            return int(brightness_val / 100 * 255)
            
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        msg = f"set,{int(brightness / 255 * 100)}" if brightness is not None else "on"
        
        if await self._api.control_device(self._topic, msg, self._device["type"]):
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        if await self._api.control_device(self._topic, "off", self._device["type"]):
            await self.coordinator.async_request_refresh()

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
            _LOGGER.debug(
                f"Device '{self.name}' original room: '{room_name}', "
                f"suggesting area: '{normalized_room_name}'"
            )
        
        return device_info
