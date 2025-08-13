"""Platform for fan integration."""
import logging
import math
import unicodedata
from typing import Any, Dict

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)

from .const import DOMAIN, DEVICE_TYPE_FAN
from .api import BemfaAPI

_LOGGER = logging.getLogger(__name__)
SPEED_RANGE = (1, 3)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome fans from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return
        
        devices = coordinator.data
        fan_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_FAN
        ]

        new_fans = [
            BeHomeFan(coordinator, api, device) for device in fan_devices
        ]
        
        if new_fans:
            async_add_entities(new_fans)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeFan(CoordinatorEntity, FanEntity):
    """Representation of a BeHome Fan."""
    _attr_icon = "mdi:fan"
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the fan."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
        self._attr_speed_count = len(range(*SPEED_RANGE)) + 1

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        if not device:
            return False
        
        msg = device.get("msg")
        if isinstance(msg, dict):
            return msg.get("on") is True
        
        # Fallback for older string-based states
        return isinstance(msg, str) and msg != "off"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        if not device or not self.is_on:
            return 0

        msg = device.get("msg")
        speed_val = None

        if isinstance(msg, dict):
            # New JSON format: {"on": true, "speed": 2}
            if "speed" in msg:
                try:
                    speed_val = int(msg["speed"])
                except (ValueError, TypeError):
                    pass
        elif isinstance(msg, str) and msg.startswith("speed,"):
            # Old string format: "speed,2"
            try:
                speed_val = int(msg.split(",")[1])
            except (ValueError, IndexError):
                pass
        
        if speed_val is not None:
            return ranged_value_to_percentage(SPEED_RANGE, speed_val)

        # If it's on but no specific speed is found, assume a default.
        return 66 if self.is_on else 0

    async def async_turn_on(
        self, percentage: int | None = None, **kwargs: Any
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            await self.async_set_percentage(66)  # Default to medium speed
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        if await self._api.control_device(self._topic, "off", self._device["type"]):
            await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed_level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        msg = f"speed,{speed_level}"
        
        if await self._api.control_device(self._topic, msg, self._device["type"]):
            await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Fan",
        }
        
        room_name = self._device.get("room")
        if room_name:
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            _LOGGER.debug(
                f"Device '{self.name}' original room: '{room_name}', "
                f"suggesting area: '{normalized_room_name}'"
            )
            
        return device_info
