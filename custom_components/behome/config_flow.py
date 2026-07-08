"""Config flow for BeHome integration."""
import asyncio
import base64
import binascii
import hashlib
import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_PRIVATE_KEY,
    WECHAT_LOGIN_POLL_URL,
    WECHAT_QR_IMAGE_URL,
    WECHAT_QR_URL,
)

WECHAT_LOGIN_TIMEOUT = 120
WECHAT_LOGIN_POLL_INTERVAL = 3
_UID_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[A-Za-z0-9_-]{45}$")
_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class BeHomeConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """The main config flow. It starts by showing a menu."""

    DOMAIN = DOMAIN
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._wechat_sid: str | None = None
        self._wechat_qr_image_url: str | None = None
        self._wechat_login_task: asyncio.Task[str | None] | None = None

    @property
    def logger(self):
        """Return the logger used by the OAuth flow."""
        return _LOGGER

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow after successful authorization."""
        private_key = self._private_key_from_oauth_data(data)
        if not private_key:
            return self.async_abort(reason="invalid_token")

        return await self._async_create_private_key_entry(private_key, "BeHome")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["wechat_scan", "manual", "oauth"],
        )

    async def async_step_wechat_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle WeChat QR code login."""
        if self._wechat_login_task and self._wechat_login_task.done():
            return self.async_show_progress_done(next_step_id="wechat_done")

        if not self._wechat_login_task:
            if not await self._async_prepare_wechat_qr():
                return self.async_abort(reason="wechat_qr_failed")

            self._wechat_login_task = self.hass.async_create_task(
                self._async_wait_for_wechat_private_key()
            )

        return self.async_show_progress(
            step_id="wechat_scan",
            progress_action="wechat_scan",
            description_placeholders={"qr_image": self._wechat_qr_image_url or ""},
            progress_task=self._wechat_login_task,
        )

    async def async_step_wechat_done(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create an entry after WeChat QR login succeeds."""
        if not self._wechat_login_task or not self._wechat_login_task.done():
            return await self.async_step_wechat_scan(user_input)

        try:
            private_key = self._wechat_login_task.result()
        except Exception:
            return self.async_abort(reason="wechat_login_failed")

        if not private_key:
            return self.async_abort(reason="wechat_not_scanned")

        return await self._async_create_private_key_entry(
            private_key, "BeHome (WeChat)"
        )

    async def async_step_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the OAuth2 flow."""
        # For single OAuth implementation, use the inherited OAuth flow
        return await super().async_step_user(user_input)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the manual private key entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            private_key = str(user_input.get(CONF_PRIVATE_KEY, "")).strip()
            if private_key:
                return await self._async_create_private_key_entry(
                    private_key, "BeHome (Manual)"
                )
            errors["base"] = "empty_key"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_PRIVATE_KEY): str}),
            errors=errors,
        )

    async def _async_prepare_wechat_qr(self) -> bool:
        """Fetch a WeChat QR ticket and prepare the image URL."""
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(WECHAT_QR_URL, timeout=30) as response:
                if response.status >= 400:
                    return False
                data = await response.json(content_type=None)
        except Exception:
            return False

        if not isinstance(data, dict):
            return False

        payload = data.get("data") if isinstance(data.get("data"), dict) else {}
        ticket = str(payload.get("url") or "")
        sid = str(payload.get("sid") or "")
        if not ticket or not sid:
            return False

        self._wechat_sid = sid
        self._wechat_qr_image_url = WECHAT_QR_IMAGE_URL.format(ticket=ticket)
        return True

    async def _async_wait_for_wechat_private_key(self) -> str | None:
        """Poll WeChat login result until success or timeout."""
        if not self._wechat_sid:
            return None

        deadline = self.hass.loop.time() + WECHAT_LOGIN_TIMEOUT
        while self.hass.loop.time() < deadline:
            payload = await self._async_poll_wechat_login()
            if payload:
                return self._private_key_from_wechat_payload(payload)
            await asyncio.sleep(WECHAT_LOGIN_POLL_INTERVAL)

        return None

    async def _async_poll_wechat_login(self) -> dict[str, Any] | None:
        """Poll the backend for a WeChat login result."""
        session = async_get_clientsession(self.hass)

        try:
            async with session.post(
                WECHAT_LOGIN_POLL_URL,
                json={"eventKey": self._wechat_sid},
                timeout=30,
            ) as response:
                if response.status >= 400:
                    return None
                data = await response.json(content_type=None)
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        if data.get("code") != 0:
            return None

        payload = data.get("data") if isinstance(data.get("data"), dict) else None
        if not payload or payload.get("code") != 0:
            return None

        return payload

    def _private_key_from_wechat_payload(self, data: dict[str, Any]) -> str | None:
        """Extract the Bemfa private key from the WeChat login payload."""
        open_id = str(data.get("openID") or "")
        if len(open_id) <= 6:
            return None

        encoded_uid = open_id[1:-2][1:-2]
        padding = "=" * ((4 - len(encoded_uid) % 4) % 4)
        try:
            private_key = base64.b64decode(encoded_uid + padding).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None

        if not _UID_RE.match(private_key):
            return None

        return private_key

    @staticmethod
    def _private_key_from_oauth_data(data: dict[str, Any]) -> str | None:
        """Extract the Bemfa private key from an OAuth token response."""
        token = data.get("token")
        access_token = token.get("access_token") if isinstance(token, dict) else None
        if not isinstance(access_token, str) or len(access_token) <= 8:
            return None

        private_key = access_token[4:-4]
        return private_key if _UID_RE.match(private_key) else None

    async def _async_create_private_key_entry(
        self, private_key: str, title: str
    ) -> dict[str, Any]:
        """Create a config entry for a Bemfa private key."""
        unique_id = hashlib.sha256(private_key.encode("utf-8")).hexdigest()
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=title,
            data={CONF_PRIVATE_KEY: private_key},
        )
