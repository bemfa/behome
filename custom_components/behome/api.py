"""API client for interacting with the Bemfa Cloud."""
import logging
from typing import Any, Dict, List
import httpx
import base64
import json

from .const import API_DEVICE_LIST_URL, API_DEVICE_CONTROL_URL

_LOGGER = logging.getLogger(__name__)

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
            _LOGGER.debug("Bemfa API response: %s", data)
            if data.get("code") == 0:
                return data.get("data", {}).get("array", [])
            _LOGGER.error("Failed to get devices: %s", data.get("msg"))
            return []
        except httpx.RequestError as err:
            _LOGGER.error("Error requesting devices: %s", err)
            return []
        except Exception as err:
            _LOGGER.error("An unexpected error occurred while getting devices: %s", err)
            return []

    async def control_device(self, topic: str, message: str, device_type: int) -> bool:
        """Send a control command to a device using the new POST endpoint."""
        encoded_private_key = base64.b64encode(self._private_key.encode("utf-8")).decode("utf-8")

        # Per the new protocol, format the message based on device type
        if device_type >= 4:
            if message == "on":
                cmd_message = json.dumps({"on": True})
            elif message == "off":
                cmd_message = json.dumps({"on": False})
            else:
                cmd_message = message # Pass other commands through
        else:
            cmd_message = message

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
                _LOGGER.debug(
                    "Successfully controlled device %s with payload %s", topic, payload
                )
                return True
            else:
                _LOGGER.error(
                    "Failed to control device %s with payload %s: %s",
                    topic,
                    payload,
                    data.get("message"),
                )
                return False
        except httpx.RequestError as err:
            _LOGGER.error("Error controlling device %s: %s", topic, err)
            return False
        except Exception as err:
            _LOGGER.error(
                "An unexpected error occurred while controlling device %s: %s", topic, err
            )
            return False