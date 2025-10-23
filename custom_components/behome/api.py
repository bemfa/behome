"""API client for interacting with the Bemfa Cloud."""
from typing import Any, Dict, List
import httpx
import base64
import json

from .const import API_DEVICE_LIST_URL, API_DEVICE_CONTROL_URL


class BemfaAPI:
    """A client for the Bemfa API."""

    def __init__(self, private_key: str, session: httpx.AsyncClient):
        """Initialize the API client."""
        self._private_key = private_key
        self._session = session

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Fetch all devices (topics) from the Bemfa cloud."""
        encoded_private_key = base64.b64encode(self._private_key.encode("utf-8")).decode("utf-8")
        params = {"openID": encoded_private_key}
        try:
            response = await self._session.get(API_DEVICE_LIST_URL, params=params)
            response.raise_for_status()
            data = await response.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("array", [])
            return []
        except httpx.RequestError:
            return []
        except Exception:
            return []

    async def control_device(self, topic: str, message: str, device_type: int) -> bool:
        """Send a control command to a device using the new POST endpoint."""
        encoded_private_key = base64.b64encode(self._private_key.encode("utf-8")).decode("utf-8")

        # Parse message to JSON format - unified approach for all device types
        if message == "on":
            cmd_message = {"on": True}
        elif message == "off":
            cmd_message = {"on": False}
        elif message.startswith("set,"):
            # Handle brightness/temperature/speed settings
            parts = message.split(",")
            value = int(parts[1])

            if len(parts) == 2:
                # Simple brightness for light: "set,80" -> {"on":true,"bri":80}
                cmd_message = {"on": True, "bri": value}
            elif len(parts) == 4:
                # Climate control: "set,25,cool,auto" -> {"on":true,"t":25,"mode":2}
                temperature = value
                mode_str = parts[2]
                # Convert mode string to int according to documentation
                mode_map = {
                    "auto": 1, "cool": 2, "heat": 3, "fan": 4,
                    "dry": 5, "sleep": 6, "eco": 7
                }
                mode = mode_map.get(mode_str, 1)  # Default to auto
                cmd_message = {"on": True, "t": temperature, "mode": mode}
            else:
                # Fallback for other set commands
                cmd_message = {"on": True, "v": value}
                
        elif message.startswith("speed,"):
            # Fan speed: "speed,2" -> {"on":true,"v":2}
            speed = int(message.split(",")[1])
            cmd_message = {"on": True, "v": speed}
            
        else:
            # Other commands (stop, volup, voldown, chup, chdown, etc.)
            try:
                # Try to parse as JSON first
                cmd_message = json.loads(message)
            except:
                # Handle special commands for media player and covers
                if message == "stop":
                    cmd_message = {"pause": True}  # Use pause for cover stop
                elif message in ["volup", "voldown", "chup", "chdown"]:
                    cmd_message = {"command": message}
                else:
                    # Fallback: create a simple command object
                    cmd_message = {"on": True}

        payload = {
            "openID": encoded_private_key,
            "topicID": topic,
            "type": device_type,
            "message": cmd_message,
        }
        
        try:
            response = await self._session.post(API_DEVICE_CONTROL_URL, json=payload)
            response.raise_for_status()
            data = await response.json()
            if data.get("code") == 0:
                return True
            else:
                return False
        except httpx.RequestError:
            return False
        except Exception:
            return False