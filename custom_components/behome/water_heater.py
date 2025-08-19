"""Platform for water_heater integration."""
import asyncio
import unicodedata
from typing import Any, Dict

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ECO,
    STATE_PERFORMANCE,
    STATE_OFF,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from .const import DOMAIN, DEVICE_TYPE_WATER_HEATER
from .api import BemfaAPI


HA_OP_MODE_TO_BEMFA = {
    STATE_ECO: "eco",
    STATE_PERFORMANCE: "perf",
    STATE_OFF: "off",
}
BEMFA_OP_MODE_TO_HA = {v: k for k, v in HA_OP_MODE_TO_BEMFA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome water heaters from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return
        
        devices = coordinator.data
        wh_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_WATER_HEATER
        ]

        new_whs = [
            BeHomeWaterHeater(coordinator, api, device) for device in wh_devices
        ]
        
        if new_whs:
            async_add_entities(new_whs)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Representation of a BeHome Water Heater."""
    _attr_icon = "mdi:water-heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_operation_list = [STATE_ECO, STATE_PERFORMANCE, STATE_OFF]
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the water heater."""
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
    def _current_device_state_parts(self) -> list[str]:
        """Get the latest state for this device, split by comma."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        return device.get("state", "").split(",") if device else []

    @property
    def current_operation(self) -> str | None:
        """Return current operation."""
        parts = self._current_device_state_parts
        if not parts or parts[0] == "off":
            return STATE_OFF
        
        return BEMFA_OP_MODE_TO_HA.get(parts[2]) if len(parts) > 2 else STATE_PERFORMANCE

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        parts = self._current_device_state_parts
        if len(parts) > 1 and parts[0] != "off":
            try:
                return float(parts[1])
            except (ValueError, IndexError):
                pass
        return None

    async def _send_command(self, msg: str):
        """Send a command to the device."""
        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        
        mode = self.current_operation if self.current_operation != STATE_OFF else STATE_PERFORMANCE
        mode_bemfa = HA_OP_MODE_TO_BEMFA.get(mode, "perf")
        await self._send_command(f"set,{int(temp)},{mode_bemfa}")

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        if operation_mode == STATE_OFF:
            await self._send_command("off")
        else:
            temp = self.target_temperature or 55
            mode_bemfa = HA_OP_MODE_TO_BEMFA.get(operation_mode, "perf")
            await self._send_command(f"set,{int(temp)},{mode_bemfa}")

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Water Heater",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
