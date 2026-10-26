"""WeChat flow tests using real HA interfaces; run inside the HA container.

Run from a checkout with HA installed: python -m unittest discover -s tests/ha -v
"""

import asyncio
import base64
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from homeassistant.core import HomeAssistant
from custom_components.behome.config_flow import BeHomeConfigFlow
from custom_components.behome.const import WECHAT_LOGIN_POLL_URL, WECHAT_SESSION_URL


UID = "0123456789abcdef" * 2
ENCODED_UID = base64.b64encode(UID.encode()).decode()


def response(data, status=200):
    result = Mock(status=status)
    result.json = AsyncMock(return_value=data)
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=result)
    context.__aexit__ = AsyncMock(return_value=False)
    return context


def session_response(**overrides):
    return response({"code": 0, "data": {
        "qr_code_url": "https://example.com/qr",
        "session_id": "test-session",
        "exchange_token": "test-exchange-token",
        "expires_at": time.time() + 120,
        **overrides,
    }})


class WechatFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = tempfile.TemporaryDirectory()
        self.addCleanup(self.config.cleanup)
        self.flow = BeHomeConfigFlow()
        self.flow.hass = HomeAssistant(self.config.name)
        self.session = Mock()
        self.patch = patch(
            "custom_components.behome.config_flow.async_get_clientsession",
            return_value=self.session,
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    async def asyncTearDown(self):
        if task := self.flow._wechat_login_task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_session_then_pending_then_completed_creates_entry(self):
        self.session.post.side_effect = [
            session_response(),
            response({"code": 0, "data": {"code": 0, "status": "pending"}}),
            response({"code": 0, "data": {
                "code": 0, "status": "completed", "uid": ENCODED_UID,
            }}),
        ]
        with patch("custom_components.behome.config_flow.WECHAT_LOGIN_POLL_INTERVAL", 0):
            result = await self.flow.async_step_wechat_scan()
            self.assertEqual(result["type"], "progress")
            self.assertEqual(result["description_placeholders"]["qr_image"], "https://example.com/qr")
            await self.flow._wechat_login_task
        result = await self.flow.async_step_wechat_scan()
        self.assertEqual(result["type"], "progress_done")
        self.assertEqual(result["step_id"], "wechat_done")
        with (
            patch.object(self.flow, "async_set_unique_id", new_callable=AsyncMock),
            patch.object(self.flow, "_abort_if_unique_id_configured"),
        ):
            result = await self.flow.async_step_wechat_done()
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"], {"private_key": UID})
        self.session.post.assert_any_call(WECHAT_SESSION_URL, timeout=30)
        self.session.post.assert_any_call(
            WECHAT_LOGIN_POLL_URL,
            json={"session_id": "test-session", "exchange_token": "test-exchange-token"},
            timeout=30,
        )

    async def test_pending_with_code_zero_does_not_complete_login(self):
        self.flow._wechat_session_id = "session"
        self.flow._wechat_exchange_token = "secret"
        self.session.post.return_value = response({
            "code": 0, "data": {"code": 0, "status": "pending"},
        })
        self.assertIsNone(await self.flow._async_poll_wechat_login())

    async def test_expired_exchange_reaches_timeout_step(self):
        self.session.post.side_effect = [
            session_response(),
            response({"code": 0, "data": {"code": 0, "status": "pending"}}),
            response({"code": 0, "data": {"status": "expired"}}),
        ]
        with patch("custom_components.behome.config_flow.WECHAT_LOGIN_POLL_INTERVAL", 0):
            await self.flow.async_step_wechat_scan()
            await asyncio.gather(self.flow._wechat_login_task, return_exceptions=True)
        result = await self.flow.async_step_wechat_scan()
        self.assertEqual(result["step_id"], "wechat_done")
        result = await self.flow.async_step_wechat_done()
        self.assertEqual(result["reason"], "wechat_not_scanned")

    async def test_invalid_session_cannot_start_polling(self):
        for override in ({"exchange_token": ""}, {"expires_at": time.time() - 1}):
            self.session.post.return_value = session_response(**override)
            result = await self.flow.async_step_wechat_scan()
            self.assertEqual(result["type"], "abort")
            self.assertEqual(result["reason"], "wechat_qr_failed")
            self.assertIsNone(self.flow._wechat_login_task)

    async def test_remove_cancels_pending_polling(self):
        self.flow._wechat_login_task = asyncio.create_task(asyncio.Event().wait())
        self.flow.async_remove()
        await asyncio.gather(self.flow._wechat_login_task, return_exceptions=True)
        self.assertTrue(self.flow._wechat_login_task.cancelled())

    async def test_session_expiry_bounds_polling_wait(self):
        self.flow._wechat_session_id = "session"
        self.flow._wechat_exchange_token = "secret"
        self.flow._wechat_expires_at = time.time() + 0.01
        self.flow._async_poll_wechat_login = AsyncMock(return_value=None)
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.flow._async_wait_for_wechat_private_key(), 1)
        self.flow._async_poll_wechat_login.assert_awaited_once()

    async def test_new_uid_and_legacy_openid_formats(self):
        extract = self.flow._private_key_from_wechat_payload
        self.assertEqual(extract({"uid": ENCODED_UID}), UID)
        self.assertEqual(extract({"uid": ENCODED_UID.rstrip("=")}), UID)
        self.assertEqual(extract({"uid": UID}), UID)
        self.assertEqual(extract({"openID": "ab" + ENCODED_UID + "cdef"}), UID)
        for value in (None, "", "not a key", "%%%", "a" * 100):
            self.assertIsNone(extract({"uid": value}))

    async def test_api_rejection_fails_without_leaking_exchange_token(self):
        self.flow._wechat_session_id = "session"
        self.flow._wechat_exchange_token = "secret"
        self.session.post.return_value = response({"code": -1, "data": "secret"})
        with self.assertRaises(ValueError) as error:
            await self.flow._async_poll_wechat_login()
        self.assertNotIn("secret", str(error.exception))


if __name__ == "__main__":
    unittest.main()
