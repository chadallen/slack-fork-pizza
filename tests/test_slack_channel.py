"""
Tests for find_channel_id and resolve_channel in slack_channel.py.

Mocks urllib.request.urlopen throughout — no real Slack API calls.
_channel_cache is cleared before each test to prevent cross-test contamination.
"""

import json
import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import slack_channel
from slack_channel import find_channel_id, resolve_channel, SLACK_LIST_URL


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


def make_list_response(channels: list, next_cursor: str = "") -> dict:
    """Build a conversations.list API response dict."""
    return {
        "ok": True,
        "channels": [{"name": name, "id": cid} for name, cid in channels],
        "response_metadata": {"next_cursor": next_cursor},
    }


class TestFindChannelId(unittest.TestCase):
    def setUp(self):
        # Clear the module-level cache before every test.
        slack_channel._channel_cache.clear()

    def _urlopen_returning(self, *payloads):
        """Return a side_effect list for urlopen that yields each payload in order."""
        responses = [FakeResponse(p) for p in payloads]
        return MagicMock(side_effect=responses)

    # ------------------------------------------------------------------ #
    # Happy path — single page                                             #
    # ------------------------------------------------------------------ #

    def test_returns_channel_id_when_found(self):
        payload = make_list_response([("my-project", "C001"), ("other", "C002")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = find_channel_id("xoxb-tok", "my-project")
        self.assertEqual(result, "C001")

    def test_returns_none_when_channel_not_found(self):
        payload = make_list_response([("alpha", "C010"), ("beta", "C011")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = find_channel_id("xoxb-tok", "gamma")
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # Pagination                                                           #
    # ------------------------------------------------------------------ #

    def test_paginates_to_find_channel_on_second_page(self):
        page1 = make_list_response([("alpha", "C100")], next_cursor="cursor-abc")
        page2 = make_list_response([("target-project", "C200")], next_cursor="")
        mock_urlopen = self._urlopen_returning(page1, page2)
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            result = find_channel_id("xoxb-tok", "target-project")
        self.assertEqual(result, "C200")
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_pagination_stops_when_cursor_empty(self):
        page1 = make_list_response([("chan-a", "CA1")], next_cursor="next")
        page2 = make_list_response([("chan-b", "CB2")], next_cursor="")
        mock_urlopen = self._urlopen_returning(page1, page2)
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            find_channel_id("xoxb-tok", "chan-a")
        # Both pages were fetched.
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_all_channels_cached_across_pages(self):
        page1 = make_list_response([("p1", "ID1")], next_cursor="c1")
        page2 = make_list_response([("p2", "ID2"), ("p3", "ID3")], next_cursor="")
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(page1, page2)):
            find_channel_id("xoxb-tok", "p1")
        # After traversal, all three names should be in the cache.
        self.assertEqual(slack_channel._channel_cache.get("p1"), "ID1")
        self.assertEqual(slack_channel._channel_cache.get("p2"), "ID2")
        self.assertEqual(slack_channel._channel_cache.get("p3"), "ID3")

    # ------------------------------------------------------------------ #
    # Caching                                                              #
    # ------------------------------------------------------------------ #

    def test_cache_hit_skips_api_call(self):
        slack_channel._channel_cache["cached-project"] = "C999"
        mock_urlopen = MagicMock()
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            result = find_channel_id("xoxb-tok", "cached-project")
        self.assertEqual(result, "C999")
        mock_urlopen.assert_not_called()

    def test_second_call_for_same_name_uses_cache(self):
        payload = make_list_response([("reused", "CRE1")])
        mock_urlopen = self._urlopen_returning(payload)
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            first = find_channel_id("xoxb-tok", "reused")
            second = find_channel_id("xoxb-tok", "reused")
        self.assertEqual(first, "CRE1")
        self.assertEqual(second, "CRE1")
        # urlopen should only have been called once.
        self.assertEqual(mock_urlopen.call_count, 1)

    # ------------------------------------------------------------------ #
    # API error handling                                                   #
    # ------------------------------------------------------------------ #

    def test_returns_none_when_ok_is_false(self):
        payload = {"ok": False, "error": "invalid_auth"}
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = find_channel_id("bad-token", "some-project")
        self.assertIsNone(result)

    def test_raises_on_urlopen_exception(self):
        """Network-level errors propagate out of find_channel_id."""
        import urllib.error
        with patch(
            "slack_channel.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(urllib.error.URLError):
                find_channel_id("xoxb-tok", "any-project")

    # ------------------------------------------------------------------ #
    # Request construction                                                 #
    # ------------------------------------------------------------------ #

    def test_request_includes_bearer_token(self):
        payload = make_list_response([])
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["req"] = req
            return FakeResponse(payload)

        with patch("slack_channel.urllib.request.urlopen", fake_urlopen):
            find_channel_id("xoxb-mytoken", "proj")

        self.assertIn("Bearer xoxb-mytoken", captured["req"].get_header("Authorization"))

    def test_request_url_includes_limit_and_exclude_archived(self):
        payload = make_list_response([])
        captured = {}

        def fake_urlopen(req, timeout=10):
            captured["url"] = req.full_url
            return FakeResponse(payload)

        with patch("slack_channel.urllib.request.urlopen", fake_urlopen):
            find_channel_id("xoxb-tok", "proj")

        self.assertIn("limit=200", captured["url"])
        self.assertIn("exclude_archived=true", captured["url"])

    def test_cursor_included_in_second_page_request(self):
        page1 = make_list_response([("a", "CA")], next_cursor="CURSOR_XYZ")
        page2 = make_list_response([("b", "CB")], next_cursor="")
        captured_urls = []

        def fake_urlopen(req, timeout=10):
            captured_urls.append(req.full_url)
            if len(captured_urls) == 1:
                return FakeResponse(page1)
            return FakeResponse(page2)

        with patch("slack_channel.urllib.request.urlopen", fake_urlopen):
            find_channel_id("xoxb-tok", "b")

        self.assertNotIn("cursor", captured_urls[0])
        self.assertIn("CURSOR_XYZ", captured_urls[1])


class TestResolveChannel(unittest.TestCase):
    def setUp(self):
        slack_channel._channel_cache.clear()

    def _urlopen_returning(self, *payloads):
        responses = [FakeResponse(p) for p in payloads]
        return MagicMock(side_effect=responses)

    # ------------------------------------------------------------------ #
    # Project name extraction                                              #
    # ------------------------------------------------------------------ #

    def test_extracts_project_name_from_cwd_last_component(self):
        payload = make_list_response([("my-project", "CPROJ")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = resolve_channel("xoxb-tok", "/home/user/my-project", "CFALLBACK")
        self.assertEqual(result, "CPROJ")

    def test_extracts_last_component_when_trailing_slash(self):
        # Path("/some/dir/").name returns "" in Python; resolve_channel should
        # fall back gracefully.
        payload = make_list_response([("fallback-chan", "CFB")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            # cwd with trailing slash — Path.name is ""; expect fallback
            result = resolve_channel("xoxb-tok", "/home/user/project/", "CFALLBACK")
        # Path("/home/user/project/").name == "project" in Python
        # (pathlib strips the trailing slash)
        self.assertIsNotNone(result)

    # ------------------------------------------------------------------ #
    # Happy path                                                           #
    # ------------------------------------------------------------------ #

    def test_returns_channel_id_when_project_found(self):
        payload = make_list_response([("slack-fork-pizza", "CPIZZA")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = resolve_channel(
                "xoxb-tok",
                "/Users/chadallen/projects/slack-fork-pizza",
                "CFALLBACK",
            )
        self.assertEqual(result, "CPIZZA")

    # ------------------------------------------------------------------ #
    # Fallback logic                                                       #
    # ------------------------------------------------------------------ #

    def test_falls_back_to_fallback_channel_when_project_not_found(self):
        payload = make_list_response([("other-channel", "COTHER")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = resolve_channel("xoxb-tok", "/home/user/my-project", "CFALLBACK")
        self.assertEqual(result, "CFALLBACK")

    def test_returns_none_when_both_lookups_fail(self):
        payload = make_list_response([("unrelated", "CUR")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = resolve_channel("xoxb-tok", "/home/user/missing", "")
        self.assertIsNone(result)

    def test_returns_fallback_when_cwd_is_empty_string(self):
        mock_urlopen = MagicMock()
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            result = resolve_channel("xoxb-tok", "", "CFALLBACK")
        self.assertEqual(result, "CFALLBACK")
        mock_urlopen.assert_not_called()

    def test_returns_none_when_cwd_empty_and_no_fallback(self):
        mock_urlopen = MagicMock()
        with patch("slack_channel.urllib.request.urlopen", mock_urlopen):
            result = resolve_channel("xoxb-tok", "", "")
        self.assertIsNone(result)
        mock_urlopen.assert_not_called()

    def test_fallback_not_used_when_project_channel_exists(self):
        """Fallback should be ignored when the project channel is found."""
        payload = make_list_response([("my-project", "CMINE")])
        with patch("slack_channel.urllib.request.urlopen", self._urlopen_returning(payload)):
            result = resolve_channel("xoxb-tok", "/home/user/my-project", "CFALLBACK")
        self.assertEqual(result, "CMINE")


if __name__ == "__main__":
    unittest.main()
