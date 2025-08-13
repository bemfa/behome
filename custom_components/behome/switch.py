"""Platform for switch integration."""
import logging
from typing import Any, Dict
import unicodedata

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_SOCKET, DEVICE_TYPE_SWITCH
from .api import BemfaAPI

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome switches from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

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
        new_sockets = [
            BeHomeSocket(coordinator, api, device) for device in socket_devices
        ]
        if new_sockets:
            new_entities.extend(new_sockets)

        # Create generic switch entities
        new_switches = [
            BeHomeSwitch(coordinator, api, device) for device in switch_devices
        ]
        if new_switches:
            new_entities.extend(new_switches)
        
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
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
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
        if await self._api.control_device(self._topic, "on", self._device["type"]):
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        if await self._api.control_device(self._topic, "off", self._device["type"]):
            await self.coordinator.async_request_refresh()

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
            _LOGGER.debug(
                f"Device '{self.name}' original room: '{room_name}', "
                f"suggesting area: '{normalized_room_name}'"
            )
            
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
