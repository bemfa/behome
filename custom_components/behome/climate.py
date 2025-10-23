"""Platform for climate integration."""
import asyncio
import unicodedata
from typing import Any, Dict, List

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    PRESET_SLEEP,
    PRESET_ECO,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import UnitOfTemperature

from .const import DOMAIN, DEVICE_TYPE_CLIMATE, DEVICE_TYPE_THERMOSTAT
from .api import BemfaAPI

# Map Bemfa mode numbers to Home Assistant HVAC modes
MODE_TO_HVAC = {
    1: HVACMode.AUTO,      # 自动
    2: HVACMode.COOL,      # 制冷
    3: HVACMode.HEAT,      # 制热
    4: HVACMode.FAN_ONLY,  # 送风
    5: HVACMode.DRY,       # 除湿
}

HVAC_TO_MODE = {v: k for k, v in MODE_TO_HVAC.items()}

# Presets for sleep and eco modes
PRESET_TO_MODE = {
    PRESET_SLEEP: 6,  # 睡眠
    PRESET_ECO: 7,    # 节能
}

MODE_TO_PRESET = {v: k for k, v in PRESET_TO_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome climate devices from a config entry."""
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
        climate_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_CLIMATE
        ]

        new_climates = [
            BeHomeClimate(coordinator, api, device)
            for device in climate_devices
            if device["deviceID"] not in added_device_ids
        ]

        if new_climates:
            # Track the new device IDs
            for entity in new_climates:
                added_device_ids.add(entity._device_id)
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
        self._device_id = device["deviceID"]
        self._attr_name = device.get("name", self._topic)
        self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
        self._attr_icon = "mdi:thermostat"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY,
            HVACMode.DRY,
        ]
        self._attr_preset_modes = [PRESET_SLEEP, PRESET_ECO]
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.PRESET_MODE
        )
        self._attr_target_temperature_step = 1

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
    def _current_device_msg(self) -> dict:
        """Get the latest msg for this device from the coordinator."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        msg = device.get("msg") if device else {}
        return msg if isinstance(msg, dict) else {}

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current hvac mode."""
        msg = self._current_device_msg

        # Check if device is on
        if not msg.get("on"):
            return HVACMode.OFF

        # Get mode number from msg
        mode_num = msg.get("mode")
        if mode_num is None:
            return HVACMode.AUTO  # Default

        # Check if it's a preset mode (sleep or eco)
        if mode_num in MODE_TO_PRESET:
            # Return the base hvac mode (auto) when in preset mode
            return HVACMode.AUTO

        # Map mode number to HVAC mode
        return MODE_TO_HVAC.get(mode_num, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self.target_temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        msg = self._current_device_msg
        if msg.get("on") and "t" in msg:
            try:
                return float(msg["t"])
            except (ValueError, TypeError):
                pass
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        msg = self._current_device_msg
        mode_num = msg.get("mode")
        return MODE_TO_PRESET.get(mode_num)

    async def _send_command(self, msg: str):
        """Send a command to the climate device."""
        await self._api.control_device(self._topic, msg, self._device["type"])
        asyncio.create_task(self.coordinator.async_request_refresh_after_delay(3.0))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            # Update local state immediately
            self.coordinator.update_device_state_immediately(self._device_id, {
                "msg": {"on": False}
            })
            await self._send_command("off")
        else:
            temp = self.target_temperature or 25
            mode_num = HVAC_TO_MODE.get(hvac_mode, 1)  # Default to auto

            # Update local state immediately
            self.coordinator.update_device_state_immediately(self._device_id, {
                "msg": {"on": True, "t": int(temp), "mode": mode_num}
            })

            await self._send_command(f"set,{int(temp)},{['auto','cool','heat','fan','dry'][mode_num-1] if mode_num <= 5 else 'auto'},auto")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get("temperature")
        if temp is None:
            return

        # Get current mode or default to cool
        current_mode = self.hvac_mode if self.hvac_mode != HVACMode.OFF else HVACMode.COOL
        mode_num = HVAC_TO_MODE.get(current_mode, 2)  # Default to cool

        # Update local state immediately
        self.coordinator.update_device_state_immediately(self._device_id, {
            "msg": {"on": True, "t": int(temp), "mode": mode_num}
        })

        mode_str = ['auto','cool','heat','fan','dry'][mode_num-1] if mode_num <= 5 else 'auto'
        await self._send_command(f"set,{int(temp)},{mode_str},auto")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode (sleep or eco)."""
        mode_num = PRESET_TO_MODE.get(preset_mode)
        if mode_num is None:
            return

        temp = self.target_temperature or 25

        # Update local state immediately
        self.coordinator.update_device_state_immediately(self._device_id, {
            "msg": {"on": True, "t": int(temp), "mode": mode_num}
        })

        # For sleep and eco modes, send with mode number
        mode_str = ['auto','cool','heat','fan','dry','sleep','eco'][mode_num-1]
        await self._send_command(f"set,{int(temp)},{mode_str},auto")

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
            pass
        
        return device_info
