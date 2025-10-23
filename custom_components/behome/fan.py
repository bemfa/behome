"""Platform for fan integration."""
import asyncio
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

    # Track already added device IDs
    added_device_ids = set()

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return

        devices = coordinator.data
        fan_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_FAN
        ]

        # Only create entities for new devices
        new_fans = [
            BeHomeFan(coordinator, api, device)
            for device in fan_devices
            if device["deviceID"] not in added_device_ids
        ]

        if new_fans:
            # Track the new device IDs
            for fan in new_fans:
                added_device_ids.add(fan._device_id)
            async_add_entities(new_fans)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeFan(CoordinatorEntity, FanEntity):
    """Representation of a BeHome Fan."""
    _attr_icon = "mdi:fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED |
        FanEntityFeature.TURN_ON |
        FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the fan."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._device_id = device["deviceID"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
        self._attr_speed_count = len(range(*SPEED_RANGE)) + 1

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
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
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
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
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
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            await self.async_set_percentage(66)  # Default to medium speed
        else:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        # Update local state immediately
        self.coordinator.update_device_state_immediately(self._device_id, {
            "msg": {"on": False}
        })

        await self._api.control_device(self._topic, "off", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        speed_level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        msg = f"speed,{speed_level}"

        # Update local state immediately
        self.coordinator.update_device_state_immediately(self._device_id, {
            "msg": {"on": True, "speed": speed_level}
        })

        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

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
            pass
            
        return device_info
