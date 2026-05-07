"""
Tests for ping_user_mcp.py — MCP JSON-RPC server exposing the ping_user tool.

Covers:
  - handle_message: protocol routing for initialize, tools/list, tools/call,
    unknown method, and notifications (no id).
  - handle_ping_user: missing question, missing token, no channel found,
    successful post+reply round-trip, and poll timeout.
  - send_response: output goes to sys.stdout.

All Slack API calls are mocked — no real network traffic.
time.sleep and time.time are mocked to avoid real delays.
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import ping_user_mcp
from ping_user_mcp import handle_message, handle_ping_user, send_response

FAKE_TOKEN = "xoxb-test-token"
FAKE_CHANNEL = "C0TEST123"
FAKE_TS = "1620000000.000100"
FAKE_BOT_USER_ID = "UBOT001"


class FakeResponse:
    """Minimal file-like object returned by urlopen mock."""

    def __init__(self, payload: dict):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ---------------------------------------------------------------------------
# send_response
# ---------------------------------------------------------------------------


class TestSendResponse(unittest.TestCase):
    def test_writes_json_plus_newline_to_stdout(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            send_response({"jsonrpc": "2.0", "id": 1, "result": {}})
        output = buf.getvalue()
        self.assertTrue(output.endswith("\n"))
        parsed = json.loads(output.strip())
        self.assertEqual(parsed, {"jsonrpc": "2.0", "id": 1, "result": {}})


# ---------------------------------------------------------------------------
# handle_message — protocol routing
# ---------------------------------------------------------------------------


class TestHandleMessageInitialize(unittest.TestCase):
    def _call(self, msg: dict) -> dict:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message(msg)
        return json.loads(buf.getvalue().strip())

    def test_initialize_returns_correct_protocol_version(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["protocolVersion"], "2024-11-05")

    def test_initialize_includes_tools_capability(self):
        response = self._call({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})
        self.assertIn("tools", response["result"]["capabilities"])

    def test_initialize_includes_server_info(self):
        response = self._call({"jsonrpc": "2.0", "id": 3, "method": "initialize", "params": {}})
        info = response["result"]["serverInfo"]
        self.assertEqual(info["name"], "ping-user")

    def test_initialize_echoes_request_id(self):
        response = self._call({"jsonrpc": "2.0", "id": 99, "method": "initialize", "params": {}})
        self.assertEqual(response["id"], 99)

    def test_initialize_uses_jsonrpc_20(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["jsonrpc"], "2.0")


class TestHandleMessageToolsList(unittest.TestCase):
    def _call(self, msg: dict) -> dict:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message(msg)
        return json.loads(buf.getvalue().strip())

    def test_tools_list_contains_ping_user(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = response["result"]["tools"]
        names = [t["name"] for t in tools]
        self.assertIn("ping_user", names)

    def test_tools_list_ping_user_has_input_schema(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tool = next(t for t in response["result"]["tools"] if t["name"] == "ping_user")
        self.assertIn("inputSchema", tool)
        self.assertIn("question", tool["inputSchema"]["properties"])

    def test_tools_list_echoes_id(self):
        response = self._call({"jsonrpc": "2.0", "id": 42, "method": "tools/list"})
        self.assertEqual(response["id"], 42)

    def test_tools_list_uses_jsonrpc_20(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["jsonrpc"], "2.0")


class TestHandleMessageUnknownMethod(unittest.TestCase):
    def _call(self, msg: dict) -> dict:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message(msg)
        return json.loads(buf.getvalue().strip())

    def test_unknown_method_returns_error_code(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "nonexistent/method"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_unknown_method_error_message_mentions_method(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "foo/bar"})
        self.assertIn("foo/bar", response["error"]["message"])

    def test_unknown_method_echoes_id(self):
        response = self._call({"jsonrpc": "2.0", "id": 7, "method": "unknown"})
        self.assertEqual(response["id"], 7)

    def test_no_result_key_on_error(self):
        response = self._call({"jsonrpc": "2.0", "id": 1, "method": "bad"})
        self.assertNotIn("result", response)


class TestHandleMessageNotification(unittest.TestCase):
    """Notifications have no 'id' and must produce no output."""

    def test_notification_produces_no_output(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(buf.getvalue(), "")

    def test_notification_without_method_produces_no_output(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message({"jsonrpc": "2.0"})
        self.assertEqual(buf.getvalue(), "")


class TestHandleMessageToolsCall(unittest.TestCase):
    """Route tools/call to the correct handler."""

    def _call(self, msg: dict, mock_handle_ping_user=None) -> dict:
        buf = io.StringIO()
        result = {"content": [{"type": "text", "text": "mocked reply"}]}
        with patch("sys.stdout", buf), \
             patch("ping_user_mcp.handle_ping_user", return_value=result) as mock_h:
            handle_message(msg)
        return json.loads(buf.getvalue().strip()), mock_h

    def test_tools_call_ping_user_dispatches_to_handler(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ping_user", "arguments": {"question": "Ready?"}},
        }
        _, mock_h = self._call(msg)
        mock_h.assert_called_once_with({"question": "Ready?"})

    def test_tools_call_unknown_tool_returns_error(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "does_not_exist", "arguments": {}},
        }
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            handle_message(msg)
        response = json.loads(buf.getvalue().strip())
        self.assertTrue(response["result"]["isError"])
        self.assertIn("does_not_exist", response["result"]["content"][0]["text"])

    def test_tools_call_echoes_id(self):
        msg = {
            "jsonrpc": "2.0",
            "id": 88,
            "method": "tools/call",
            "params": {"name": "ping_user", "arguments": {"question": "?"}},
        }
        response, _ = self._call(msg)
        self.assertEqual(response["id"], 88)


# ---------------------------------------------------------------------------
# handle_ping_user — tool execution
# ---------------------------------------------------------------------------


class TestHandlePingUserMissingQuestion(unittest.TestCase):
    def test_empty_question_returns_error(self):
        result = handle_ping_user({"question": ""})
        self.assertTrue(result["isError"])
        self.assertIn("question", result["content"][0]["text"].lower())

    def test_missing_question_key_returns_error(self):
        result = handle_ping_user({})
        self.assertTrue(result["isError"])
        self.assertIn("question", result["content"][0]["text"].lower())


class TestHandlePingUserMissingToken(unittest.TestCase):
    def test_missing_token_returns_error(self):
        with patch.dict("os.environ", {}, clear=True):
            result = handle_ping_user({"question": "Are you ready?"})
        self.assertTrue(result["isError"])
        self.assertIn("SLACK_BOT_TOKEN", result["content"][0]["text"])

    def test_empty_token_returns_error(self):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": ""}, clear=True):
            result = handle_ping_user({"question": "Hello?"})
        self.assertTrue(result["isError"])


class TestHandlePingUserNoChannel(unittest.TestCase):
    def test_no_channel_found_returns_error(self):
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=None):
            result = handle_ping_user({"question": "Where are we?"})
        self.assertTrue(result["isError"])
        self.assertIn("channel", result["content"][0]["text"].lower())

    def test_fallback_channel_env_used_when_lookup_fails(self):
        """When find_channel_id returns None, SLACK_CHANNEL_ID is used as fallback."""
        env = {
            "SLACK_BOT_TOKEN": FAKE_TOKEN,
            "SLACK_CHANNEL_ID": FAKE_CHANNEL,
        }

        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        replies_response = FakeResponse({
            "ok": True,
            "messages": [
                # parent message (same ts as thread_ts — skipped by poll_for_reply)
                {"ts": FAKE_TS, "user": "UHUMAN", "text": "original question"},
                # human reply with a later ts
                {"ts": "1620000001.000200", "user": "UHUMAN", "text": "Sure!"},
            ],
        })

        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=None), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 1000]):
            mock_urlopen.side_effect = [auth_response, replies_response]
            result = handle_ping_user({"question": "Hello?"})
        self.assertFalse(result.get("isError", False))
        self.assertEqual(result["content"][0]["text"], "Sure!")


class TestHandlePingUserSuccessfulRoundTrip(unittest.TestCase):
    """Happy path: post to Slack, poll for reply, return reply text."""

    def _run(self, reply_text="Got it!") -> dict:
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}

        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        replies_response = FakeResponse({
            "ok": True,
            "messages": [
                # parent message — should be skipped
                {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "original question"},
                # human reply
                {"ts": "1620000001.000200", "user": "UHUMAN", "text": reply_text},
            ],
        })

        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 1000]):
            mock_urlopen.side_effect = [auth_response, replies_response]
            result = handle_ping_user({"question": "Ready to deploy?"})
        return result

    def test_returns_reply_text(self):
        result = self._run("Approved!")
        self.assertEqual(result["content"][0]["text"], "Approved!")

    def test_result_is_not_error(self):
        result = self._run()
        self.assertFalse(result.get("isError", False))

    def test_post_message_called_with_question(self):
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        replies_response = FakeResponse({
            "ok": True,
            "messages": [
                {"ts": "1620000001.000200", "user": "UHUMAN", "text": "yes"},
            ],
        })
        post_ret = {"ok": True, "ts": FAKE_TS}
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value=post_ret) as mock_post, \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 1000]):
            mock_urlopen.side_effect = [auth_response, replies_response]
            handle_ping_user({"question": "Should I proceed?"})
        _, call_channel, call_text = mock_post.call_args[0]
        self.assertEqual(call_channel, FAKE_CHANNEL)
        self.assertIn("Should I proceed?", call_text)

    def test_skips_bot_own_replies(self):
        """Messages from the bot's own user ID must not be returned as a reply."""
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        # First poll: only bot replies — should keep polling
        replies_poll1 = FakeResponse({
            "ok": True,
            "messages": [
                {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "bot's follow-up"},
            ],
        })
        # Second poll: human reply
        replies_poll2 = FakeResponse({
            "ok": True,
            "messages": [
                {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "bot message"},
                {"ts": "1620000002.000300", "user": "UHUMAN", "text": "human reply"},
            ],
        })
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 0, 0, 1000]):
            mock_urlopen.side_effect = [auth_response, replies_poll1, replies_poll2]
            result = handle_ping_user({"question": "Still waiting?"})
        self.assertEqual(result["content"][0]["text"], "human reply")

    def test_skips_messages_with_bot_id_field(self):
        """Messages with a bot_id field must be skipped."""
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        replies_response = FakeResponse({
            "ok": True,
            "messages": [
                # another bot (not our bot_user_id, but has bot_id)
                {"ts": "1620000001.000200", "user": "UOTHER", "bot_id": "BOTHER",
                 "text": "automated message"},
                # human reply
                {"ts": "1620000002.000300", "user": "UHUMAN", "text": "the real answer"},
            ],
        })
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 1000]):
            mock_urlopen.side_effect = [auth_response, replies_response]
            result = handle_ping_user({"question": "Any humans?"}),
        self.assertEqual(result[0]["content"][0]["text"], "the real answer")

    def test_post_fails_returns_error(self):
        """If post_message returns no ts, handle_ping_user returns an error."""
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": False}), \
             patch("ping_user_mcp.urllib.request.urlopen", return_value=auth_response):
            result = handle_ping_user({"question": "Will this work?"})
        self.assertTrue(result["isError"])
        self.assertIn("failed to post", result["content"][0]["text"].lower())


class TestHandlePingUserTimeout(unittest.TestCase):
    """poll_for_reply raises TimeoutError after 300 s with no human reply."""

    def test_timeout_returns_error_result(self):
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        # Replies with only the parent message — no human reply ever
        replies_response = FakeResponse({
            "ok": True,
            "messages": [
                {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "question"},
            ],
        })

        # Simulate deadline expiry: first call = start (0), second = past deadline (301)
        time_values = iter([0, 301])

        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=time_values):
            mock_urlopen.side_effect = [auth_response, replies_response]
            result = handle_ping_user({"question": "Still there?"})

        self.assertTrue(result["isError"])
        # The timeout message should mention duration
        self.assertIn("300", result["content"][0]["text"])

    def test_timeout_message_contains_seconds(self):
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN}
        auth_response = FakeResponse({"ok": True, "user_id": FAKE_BOT_USER_ID})
        replies_response = FakeResponse({
            "ok": True,
            "messages": [{"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "q"}],
        })
        time_values = iter([0, 301])
        with patch.dict("os.environ", env, clear=True), \
             patch("ping_user_mcp.find_channel_id", return_value=FAKE_CHANNEL), \
             patch("ping_user_mcp.post_message", return_value={"ok": True, "ts": FAKE_TS}), \
             patch("ping_user_mcp.urllib.request.urlopen") as mock_urlopen, \
             patch("time.sleep"), \
             patch("time.time", side_effect=time_values):
            mock_urlopen.side_effect = [auth_response, replies_response]
            result = handle_ping_user({"question": "?"})
        self.assertIn("s", result["content"][0]["text"])  # "300s" or "300 seconds"


class TestPollForReply(unittest.TestCase):
    """Unit tests for poll_for_reply directly."""

    def _make_replies_response(self, messages: list) -> FakeResponse:
        return FakeResponse({"ok": True, "messages": messages})

    def test_returns_first_human_reply(self):
        replies = self._make_replies_response([
            {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "original"},
            {"ts": "1620000001.000001", "user": "UHUMAN", "text": "reply text"},
        ])
        with patch("ping_user_mcp.urllib.request.urlopen", return_value=replies), \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 1000]):
            text = ping_user_mcp.poll_for_reply(FAKE_TOKEN, FAKE_CHANNEL, FAKE_TS, FAKE_BOT_USER_ID)
        self.assertEqual(text, "reply text")

    def test_raises_timeout_error_when_deadline_exceeded(self):
        replies = self._make_replies_response([
            {"ts": FAKE_TS, "user": FAKE_BOT_USER_ID, "text": "q"},
        ])
        # time.time returns 0 (deadline=300), then 301 to exceed it immediately
        with patch("ping_user_mcp.urllib.request.urlopen", return_value=replies), \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 301]):
            with self.assertRaises(TimeoutError):
                ping_user_mcp.poll_for_reply(FAKE_TOKEN, FAKE_CHANNEL, FAKE_TS, FAKE_BOT_USER_ID)

    def test_continues_on_urlopen_exception(self):
        """Network errors during polling are swallowed; next iteration proceeds."""
        import urllib.error
        replies = self._make_replies_response([
            {"ts": "9999", "user": "UHUMAN", "text": "ok"},
        ])
        side_effects = [
            urllib.error.URLError("timeout"),
            replies,
        ]
        with patch("ping_user_mcp.urllib.request.urlopen", side_effect=side_effects), \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 0, 1000]):
            text = ping_user_mcp.poll_for_reply(FAKE_TOKEN, FAKE_CHANNEL, FAKE_TS, FAKE_BOT_USER_ID)
        self.assertEqual(text, "ok")

    def test_skips_parent_message_by_ts(self):
        """Message with ts == thread_ts is skipped even if it's a human message."""
        replies = self._make_replies_response([
            # same ts as thread — skip it
            {"ts": FAKE_TS, "user": "UHUMAN", "text": "original"},
            # reply with different ts
            {"ts": "1620000002.000000", "user": "UHUMAN", "text": "actual reply"},
        ])
        with patch("ping_user_mcp.urllib.request.urlopen", return_value=replies), \
             patch("time.sleep"), \
             patch("time.time", side_effect=[0, 0, 1000]):
            text = ping_user_mcp.poll_for_reply(FAKE_TOKEN, FAKE_CHANNEL, FAKE_TS, FAKE_BOT_USER_ID)
        self.assertEqual(text, "actual reply")


class TestGetBotUserId(unittest.TestCase):
    def test_returns_user_id_on_ok_response(self):
        response = FakeResponse({"ok": True, "user_id": "UBOT999"})
        with patch("ping_user_mcp.urllib.request.urlopen", return_value=response):
            uid = ping_user_mcp.get_bot_user_id(FAKE_TOKEN)
        self.assertEqual(uid, "UBOT999")

    def test_returns_none_when_ok_is_false(self):
        response = FakeResponse({"ok": False, "error": "invalid_auth"})
        with patch("ping_user_mcp.urllib.request.urlopen", return_value=response):
            uid = ping_user_mcp.get_bot_user_id(FAKE_TOKEN)
        self.assertIsNone(uid)


if __name__ == "__main__":
    unittest.main()
