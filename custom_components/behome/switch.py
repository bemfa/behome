"""Platform for switch integration."""
import asyncio
from typing import Any, Dict
import unicodedata

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_SOCKET, DEVICE_TYPE_SWITCH
from .api import BemfaAPI



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome switches from a config entry."""
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

        # Separate devices into sockets and switches
        socket_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_SOCKET
        ]
        switch_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_SWITCH
        ]

        new_entities = []

        # Create socket entities
        for device in socket_devices:
            if device["deviceID"] not in added_device_ids:
                new_entities.append(BeHomeSocket(coordinator, api, device))
                added_device_ids.add(device["deviceID"])

        # Create generic switch entities
        for device in switch_devices:
            if device["deviceID"] not in added_device_ids:
                new_entities.append(BeHomeSwitch(coordinator, api, device))
                added_device_ids.add(device["deviceID"])

        if new_entities:
            async_add_entities(new_entities)

    # Run the discovery function whenever the coordinator has new data.
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    # And run it once now
    _async_discover_entities()


class BeHomeSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a BeHome Switch."""
    _attr_icon = "mdi:toggle-switch"

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the switch."""
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
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return False
        
        msg = device.get("msg")
        if isinstance(msg, dict):
            return msg.get("on") is True
        
        # Fallback for older or unexpected string-based states
        return msg == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        # Update local state immediately
        self.coordinator.update_device_state_immediately(self._device_id, {
            "msg": {"on": True}
        })
        
        await self._api.control_device(self._topic, "on", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        # Update local state immediately
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
            "model": "Smart Switch",
        }
        
        room_name = self._device.get("room")
        if room_name:
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
            
        return device_info


class BeHomeSocket(BeHomeSwitch):
    """Representation of a BeHome Socket, a specific type of switch."""
    _attr_device_class = SwitchDeviceClass.OUTLET
    
    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the socket."""
        super().__init__(coordinator, api, device)
        self._attr_icon = "mdi:power-socket-eu" # Or other appropriate socket icon
        
    @property
    def device_info(self):
        """Return device information for the socket."""
        info = super().device_info
        info["model"] = "Smart Socket"
        return info
