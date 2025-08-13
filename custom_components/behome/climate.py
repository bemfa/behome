"""Platform for climate integration."""
import logging
import unicodedata
from typing import Any, Dict, List

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN, DEVICE_TYPE_CLIMATE, DEVICE_TYPE_THERMOSTAT
from .api import BemfaAPI

_LOGGER = logging.getLogger(__name__)

HA_STATE_TO_BEMFA = {
    HVACMode.OFF: "off",
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.FAN_ONLY: "fan",
}
BEMFA_TO_HA_STATE = {v: k for k, v in HA_STATE_TO_BEMFA.items()}

HA_FAN_MODE_TO_BEMFA = {
    FAN_AUTO: "auto",
    FAN_LOW: "low",
    FAN_MEDIUM: "medium",
    FAN_HIGH: "high",
}
BEMFA_FAN_MODE_TO_HA = {v: k for k, v in HA_FAN_MODE_TO_BEMFA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome climate devices from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    api: BemfaAPI = domain_data["api"]
    coordinator = domain_data["coordinator"]

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return
        
        devices = coordinator.data
        climate_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_CLIMATE
        ]

        new_climates = [
            BeHomeClimate(coordinator, api, device) for device in climate_devices
        ]
        
        if new_climates:
            async_add_entities(new_climates)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a BeHome Climate device."""

    def __init__(self, coordinator, api: BemfaAPI, device: Dict[str, Any]):
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._api = api
        self._device = device
        self._topic = device["topic"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
        self._attr_icon = "mdi:thermostat"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.FAN_ONLY]
        self._attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        )
        self._attr_target_temperature_step = 1

    @property
    def _current_device_state_parts(self) -> List[str]:
        """Get the latest state for this device, split by comma."""
        device = next(
            (d for d in self.coordinator.data if d["topic"] == self._topic), None
        )
        return device.get("state", "").split(",") if device else []

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current hvac mode."""
        parts = self._current_device_state_parts
        if not parts or parts[0] == "off":
            return HVACMode.OFF
        
        return BEMFA_TO_HA_STATE.get(parts[2]) if len(parts) > 2 else HVACMode.FAN_ONLY

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.target_temperature

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

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        parts = self._current_device_state_parts
        return BEMFA_FAN_MODE_TO_HA.get(parts[3]) if len(parts) > 3 else None

    async def _send_command(self, msg: str):
        """Send a command to the climate device."""
        if await self._api.control_device(self._topic, msg, self._device["type"]):
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send_command("off")
        else:
            temp = self.target_temperature or 25
            fan = self.fan_mode or FAN_AUTO
            mode_bemfa = HA_STATE_TO_BEMFA.get(hvac_mode, "cool")
            fan_bemfa = HA_FAN_MODE_TO_BEMFA.get(fan, "auto")
            await self._send_command(f"set,{int(temp)},{mode_bemfa},{fan_bemfa}")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return
        
        mode = self.hvac_mode if self.hvac_mode != HVACMode.OFF else HVACMode.COOL
        mode_bemfa = HA_STATE_TO_BEMFA.get(mode, "cool")
        fan_bemfa = HA_FAN_MODE_TO_BEMFA.get(self.fan_mode or FAN_AUTO, "auto")
        await self._send_command(f"set,{int(temp)},{mode_bemfa},{fan_bemfa}")

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if self.hvac_mode == HVACMode.OFF:
            return

        temp = self.target_temperature or 25
        mode_bemfa = HA_STATE_TO_BEMFA.get(self.hvac_mode, "cool")
        fan_bemfa = HA_FAN_MODE_TO_BEMFA.get(fan_mode, "auto")
        await self._send_command(f"set,{int(temp)},{mode_bemfa},{fan_bemfa}")

    @property
    def device_info(self):
        """Return device information."""
        model = "Smart Air Conditioner" if self._topic.endswith(DEVICE_TYPE_CLIMATE) else "Smart Thermostat"
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": model,
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
