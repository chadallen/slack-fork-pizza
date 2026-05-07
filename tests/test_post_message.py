"""
Tests for the shared post_message function in slack_channel.py.
"""

import json
import sys
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from slack_channel import post_message, SLACK_POST_URL


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


class TestPostMessage(unittest.TestCase):
    def _make_mock_urlopen(self, payload: dict):
        return MagicMock(return_value=FakeResponse(payload))

    def test_returns_full_response_dict(self):
        payload = {"ok": True, "ts": "1234567890.123456", "channel": "C123"}
        with patch("slack_channel.urllib.request.urlopen", self._make_mock_urlopen(payload)):
            result = post_message("xoxb-token", "C123", "hello")
        self.assertEqual(result, payload)

    def test_ok_field_accessible(self):
        payload = {"ok": True, "ts": "1234567890.000000"}
        with patch("slack_channel.urllib.request.urlopen", self._make_mock_urlopen(payload)):
            result = post_message("xoxb-token", "C123", "hello")
        self.assertTrue(result.get("ok"))

    def test_ts_field_accessible(self):
        payload = {"ok": True, "ts": "9999999999.000001"}
        with patch("slack_channel.urllib.request.urlopen", self._make_mock_urlopen(payload)):
            result = post_message("xoxb-token", "C123", "question?")
        self.assertEqual(result.get("ts"), "9999999999.000001")

    def test_failed_post_returns_ok_false(self):
        payload = {"ok": False, "error": "channel_not_found"}
        with patch("slack_channel.urllib.request.urlopen", self._make_mock_urlopen(payload)):
            result = post_message("xoxb-token", "CBAD", "hello")
        self.assertFalse(result.get("ok"))
        self.assertEqual(result.get("error"), "channel_not_found")

    def test_request_built_with_correct_url_and_headers(self):
        payload = {"ok": True, "ts": "1111"}
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["req"] = req
            return FakeResponse(payload)

        with patch("slack_channel.urllib.request.urlopen", fake_urlopen):
            post_message("xoxb-mytoken", "CMYCHAN", "test text")

        req = captured["req"]
        self.assertEqual(req.full_url, SLACK_POST_URL)
        self.assertIn("Bearer xoxb-mytoken", req.get_header("Authorization"))
        self.assertIn("application/json", req.get_header("Content-type"))

    def test_request_body_contains_channel_and_text(self):
        payload = {"ok": True, "ts": "2222"}
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["body"] = json.loads(req.data)
            return FakeResponse(payload)

        with patch("slack_channel.urllib.request.urlopen", fake_urlopen):
            post_message("xoxb-tok", "CCHAN", "my message")

        self.assertEqual(captured["body"]["channel"], "CCHAN")
        self.assertEqual(captured["body"]["text"], "my message")


if __name__ == "__main__":
    unittest.main()
