"""Platform for sensor integration."""
import unicodedata
from typing import Any, Dict

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfPressure,
)

from .const import DOMAIN, DEVICE_TYPE_SENSOR



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BeHome sensors from a config entry."""
    domain_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = domain_data["coordinator"]

    # Track already added entity unique IDs (not device IDs, since one device can have multiple sensor entities)
    added_unique_ids = set()

    @callback
    def _async_discover_entities():
        """Discover and add new entities."""
        if not coordinator.data:
            return

        devices = coordinator.data
        sensor_devices = [
            device for device in devices if device["id"] == DEVICE_TYPE_SENSOR
        ]

        new_sensors = []
        for device in sensor_devices:
            # Check if device has multi-sensor data
            if device.get("msg") and isinstance(device["msg"], dict):
                msg = device["msg"]
                # Create separate entities for each sensor type
                if "t" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_temperature"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "temperature"))
                        added_unique_ids.add(unique_id)
                if "h" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_humidity"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "humidity"))
                        added_unique_ids.add(unique_id)
                if "air" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_air_quality"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "air_quality"))
                        added_unique_ids.add(unique_id)
                if "pm25" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_pm25"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "pm25"))
                        added_unique_ids.add(unique_id)
                if "co2" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_co2"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "co2"))
                        added_unique_ids.add(unique_id)
                if "pa" in msg:
                    unique_id = f"{DOMAIN}_{device['deviceID']}_pressure"
                    if unique_id not in added_unique_ids:
                        new_sensors.append(BeHomeSensor(coordinator, device, "pressure"))
                        added_unique_ids.add(unique_id)
            else:
                # Single sensor entity for other types
                unique_id = f"{DOMAIN}_{device['deviceID']}"
                if unique_id not in added_unique_ids:
                    new_sensors.append(BeHomeSensor(coordinator, device))
                    added_unique_ids.add(unique_id)

        if new_sensors:
            async_add_entities(new_sensors)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_discover_entities)
    )
    _async_discover_entities()


class BeHomeSensor(CoordinatorEntity, SensorEntity):
    """Representation of a BeHome Sensor."""
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, device: Dict[str, Any], sensor_type: str = None):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device = device
        self._topic = device["topic"]
        self._device_id = device["deviceID"]
        self._sensor_type = sensor_type
        
        # Set name and unique ID based on sensor type
        base_name = device.get("name", self._topic)
        if sensor_type == "temperature":
            self._attr_name = f"{base_name} 温度"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_temperature"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        elif sensor_type == "humidity":
            self._attr_name = f"{base_name} 湿度"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_humidity"
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE
        elif sensor_type == "air_quality":
            self._attr_name = f"{base_name} 空气质量"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_air_quality"
            self._attr_device_class = SensorDeviceClass.AQI
            self._attr_native_unit_of_measurement = None
        elif sensor_type == "pm25":
            self._attr_name = f"{base_name} PM2.5"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_pm25"
            self._attr_device_class = SensorDeviceClass.PM25
            self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
        elif sensor_type == "co2":
            self._attr_name = f"{base_name} 二氧化碳"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_co2"
            self._attr_device_class = SensorDeviceClass.CO2
            self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
        elif sensor_type == "pressure":
            self._attr_name = f"{base_name} 气压"
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}_pressure"
            self._attr_device_class = SensorDeviceClass.ATMOSPHERIC_PRESSURE
            self._attr_native_unit_of_measurement = UnitOfPressure.HPA
        else:
            # Single sensor or other types - use original logic
            self._attr_name = base_name
            self._attr_unique_id = f"{DOMAIN}_{device['deviceID']}"
            
            # Set device class and unit based on sensor name
            name_lower = self._attr_name.lower()
            if "temperature" in name_lower or "温度" in name_lower:
                self._attr_device_class = SensorDeviceClass.TEMPERATURE
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            elif "humidity" in name_lower or "湿度" in name_lower:
                self._attr_device_class = SensorDeviceClass.HUMIDITY
                self._attr_native_unit_of_measurement = PERCENTAGE
            elif "pm2.5" in name_lower or "pm25" in name_lower:
                self._attr_device_class = SensorDeviceClass.PM25
                self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
            elif "co2" in name_lower or "二氧化碳" in name_lower:
                self._attr_device_class = SensorDeviceClass.CO2
                self._attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
            elif "voc" in name_lower:
                self._attr_device_class = SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
                self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
            elif "formaldehyde" in name_lower or "甲醛" in name_lower:
                self._attr_device_class = SensorDeviceClass.FORMALDEHYDE
                self._attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
            else:
                self._attr_icon = "mdi:eye"

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
    def native_value(self):
        """Return the state of the sensor."""
        device = next(
            (d for d in self.coordinator.data if d["deviceID"] == self._device_id), None
        )
        if not device:
            return None
            
        # Handle multi-sensor devices
        if self._sensor_type == "temperature":
            msg = device.get("msg", {})
            return msg.get("t") if isinstance(msg, dict) else None
        elif self._sensor_type == "humidity":
            msg = device.get("msg", {})
            return msg.get("h") if isinstance(msg, dict) else None
        elif self._sensor_type == "air_quality":
            msg = device.get("msg", {})
            return msg.get("air") if isinstance(msg, dict) else None
        elif self._sensor_type == "pm25":
            msg = device.get("msg", {})
            return msg.get("pm25") if isinstance(msg, dict) else None
        elif self._sensor_type == "co2":
            msg = device.get("msg", {})
            return msg.get("co2") if isinstance(msg, dict) else None
        elif self._sensor_type == "pressure":
            msg = device.get("msg", {})
            return msg.get("pa") if isinstance(msg, dict) else None
        else:
            # Single sensor - use original logic
            return device.get("state")

    @property
    def device_info(self):
        """Return device information."""
        device_info = {
            "identifiers": {(DOMAIN, self._device['deviceID'])},
            "name": self.name,
            "manufacturer": "BeHome (Bemfa)",
            "model": "Smart Sensor",
        }
        
        room_name = self._device.get("room")
        if room_name:
            # Normalize the string to 'NFKC' form to clean up potential issues
            normalized_room_name = unicodedata.normalize("NFKC", room_name).strip()
            device_info["suggested_area"] = normalized_room_name
            pass
        
        return device_info
