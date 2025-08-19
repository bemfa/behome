"""Platform for cover integration."""
import asyncio
import unicodedata
from typing import Any, Dict

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    CoverDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEVICE_TYPE_COVER
from .api import BemfaAPI



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome covers from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return
        
        devices = coordinator.data
        cover_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_COVER
        ]

        new_covers = [
            BeHomeCover(coordinator, api, device) for device in cover_devices
        ]
        
        if new_covers:
            async_add_entities(new_covers)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeCover(CoordinatorEntity, CoverEntity):
    """Representation of a BeHome Cover."""
    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the cover."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        if not device:
            return False
        return device.get("num", False)

    @property
    def _current_device_state(self) -> str:
        """Get the latest state for this specific device from the coordinator."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        return device.get("state", "closed") if device else "closed"

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self._current_device_state == "off"

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        return self._current_device_state == "opening"

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        return self._current_device_state == "closing"

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to open."""
        await self._api.control_device(self._topic, "on", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to close."""
        await self._api.control_device(self._topic, "off", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Instruct the cover to stop."""
        await self._api.control_device(self._topic, "stop", self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Curtain",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
