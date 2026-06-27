"""API client for interacting with the Bemfa Cloud."""
from __future__ import annotations

import base64
import json
import logging
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_DEVICE_CONTROL_URL, API_DEVICE_LIST_URL

_LOGGER = logging.getLogger(__name__)


class BemfaAPI:
    """A client for the Bemfa API."""

    def __init__(self, private_key: str, session: ClientSession) -> None:
        """Initialize the API client."""
        self._private_key = private_key
        self._session = session

    @property
    def _encoded_private_key(self) -> str:
        """Return the encoded private key expected by the BeHome API."""
        return base64.b64encode(self._private_key.encode("utf-8")).decode("utf-8")

    async def get_devices(self) -> list[dict[str, Any]]:
        """Fetch all devices from the Bemfa cloud."""
        data = await self._request_json(
            "get",
            API_DEVICE_LIST_URL,
            params={"openID": self._encoded_private_key},
        )
        if not data:
            return []

        if data.get("code") != 0:
            _LOGGER.warning("BeHome device list request failed: %s", data.get("msg"))
            return []

        payload = data.get("data")
        if not isinstance(payload, dict):
            _LOGGER.warning("BeHome device list response data is not an object")
            return []

        devices = payload.get("array")
        if not isinstance(devices, list):
            _LOGGER.warning("BeHome device list response array is not a list")
            return []

        return [device for device in devices if isinstance(device, dict)]

    async def control_device(self, topic: str, message: str, device_type: int) -> bool:
        """Send a control command to a device."""
        try:
            command_message = self._build_command_message(message)
        except (TypeError, ValueError, json.JSONDecodeError) as err:
            _LOGGER.warning("Invalid BeHome command for topic %s: %s", topic, err)
            return False

        data = await self._request_json(
            "post",
            API_DEVICE_CONTROL_URL,
            json={
                "openID": self._encoded_private_key,
                "topicID": topic,
                "type": device_type,
                "message": command_message,
            },
        )
        if not data:
            return False

        if data.get("code") != 0:
            _LOGGER.warning(
                "BeHome control request failed for topic %s: %s",
                topic,
                data.get("msg"),
            )
            return False

        return True

    async def _request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Request JSON from the BeHome API."""
        try:
            async with self._session.request(method, url, **kwargs) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except ClientError as err:
            _LOGGER.warning("BeHome API request failed: %s", err)
            return None
        except (TimeoutError, ValueError) as err:
            _LOGGER.warning("BeHome API response could not be parsed: %s", err)
            return None

        if not isinstance(data, dict):
            _LOGGER.warning("BeHome API response is not an object")
            return None

        return data

    @staticmethod
    def _build_command_message(message: str) -> dict[str, Any]:
        """Build the command payload expected by the BeHome API."""
        if message == "on":
            return {"on": True}
        if message == "off":
            return {"on": False}

        if message.startswith("set,"):
            parts = message.split(",")
            value = int(parts[1])

            if len(parts) == 2:
                return {"on": True, "bri": value}

            if len(parts) == 4:
                mode_map = {
                    "auto": 1,
                    "cool": 2,
                    "heat": 3,
                    "fan": 4,
                    "dry": 5,
                    "sleep": 6,
                    "eco": 7,
                }
                return {
                    "on": True,
                    "t": value,
                    "mode": mode_map.get(parts[2], 1),
                }

            return {"on": True, "v": value}

        if message.startswith("speed,"):
            return {"on": True, "v": int(message.split(",", 1)[1])}

        try:
            parsed = json.loads(message)
        except json.JSONDecodeError:
            if message == "stop":
                return {"pause": True}
            if message in {"volup", "voldown", "chup", "chdown"}:
                return {"command": message}
            return {"on": True}

        if not isinstance(parsed, dict):
            raise ValueError("JSON command must be an object")

        return parsed
