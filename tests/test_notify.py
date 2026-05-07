"""
Tests for notify.py hook script.

Covers Notification event handling, Stop event handling (with/without SLACK_RECAP),
mute marker check, missing token early return, and edge cases.

notify.py has module-level side effects (sys.path hack + try: main() + sys.exit).
We import `main` by patching sys.exit before import and using importlib.
"""

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure the project root is on sys.path so notify.py's own sys.path.insert succeeds
# and so we can find slack_channel for mocking.
PROJECT_ROOT = str(Path(__file__).parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _import_main():
    """Import the main() function from notify.py, suppressing module-level side effects."""
    # Patch sys.exit so the module-level `sys.exit(0)` doesn't abort the test process.
    # Also provide minimal env and stdin so the module-level `main()` call returns early.
    with patch("sys.exit"), \
         patch.dict("os.environ", {}, clear=False), \
         patch("sys.stdin", io.StringIO("")):
        # Remove cached module so we can reload cleanly if needed
        if "notify" in sys.modules:
            del sys.modules["notify"]
        # Also pre-stub slack_channel so the import inside notify.py doesn't fail
        if "slack_channel" not in sys.modules:
            import slack_channel  # noqa: F401 — ensure it's importable
        import notify  # noqa: F401
    return notify.main


# Import once at module level; individual tests will call main() with appropriate mocks.
# We suppress the module-level invocation by ensuring SLACK_BOT_TOKEN is absent.
with patch("sys.exit"), \
     patch("sys.stdin", io.StringIO("")):
    if "notify" in sys.modules:
        del sys.modules["notify"]
    import notify

_main = notify.main


def _make_stdin(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


FAKE_TOKEN = "xoxb-test-token"
FAKE_CHANNEL = "C0TEST123"
FAKE_CWD = "/Users/test/projects/my-project"


class TestMuteMarker(unittest.TestCase):
    """Early return when .slack-notify-disabled exists."""

    def test_mute_marker_prevents_any_post(self):
        event = {
            "hook_event_name": "Notification",
            "message": "hello",
        }
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN, "CLAUDE_PLUGIN_ROOT": "/fake/root"}
        with patch.dict("os.environ", env), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("notify.post_message") as mock_post, \
             patch("notify.resolve_channel") as mock_resolve:
            _main()
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    def test_no_mute_marker_continues(self):
        """When marker is absent, execution proceeds normally."""
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "hello",
        }
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN, "CLAUDE_PLUGIN_ROOT": "/fake/root"}
        with patch.dict("os.environ", env), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=FAKE_CHANNEL), \
             patch("notify.post_message") as mock_post:
            _main()
        mock_post.assert_called_once()


class TestMissingToken(unittest.TestCase):
    """Early return when SLACK_BOT_TOKEN is not set."""

    def test_missing_token_no_post(self):
        event = {"hook_event_name": "Notification", "message": "hi"}
        env = {"CLAUDE_PLUGIN_ROOT": "/fake/root"}
        # Remove SLACK_BOT_TOKEN if present
        with patch.dict("os.environ", env, clear=True), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.post_message") as mock_post, \
             patch("notify.resolve_channel") as mock_resolve:
            _main()
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    def test_present_token_allows_post(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "hi",
        }
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=FAKE_CHANNEL), \
             patch("notify.post_message") as mock_post:
            _main()
        mock_post.assert_called_once()


class TestNotificationEvent(unittest.TestCase):
    """Notification hook_event_name prepends bell emoji."""

    def _run(self, event: dict, resolve_return=FAKE_CHANNEL):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=resolve_return) as mock_resolve, \
             patch("notify.post_message") as mock_post:
            _main()
        return mock_resolve, mock_post

    def test_bell_emoji_prepended(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "Build finished",
        }
        _, mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("\U0001f514", message_text)
        self.assertIn("Build finished", message_text)
        self.assertTrue(message_text.startswith("\U0001f514"))

    def test_empty_message(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "",
        }
        _, mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        # Should still prepend bell, resulting in just the bell
        self.assertEqual(message_text, "\U0001f514 ")

    def test_resolve_channel_called_with_token_and_cwd(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "hello",
        }
        # Use explicit env with no SLACK_CHANNEL_ID so fallback is empty string
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=True), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=FAKE_CHANNEL) as mock_resolve, \
             patch("notify.post_message"):
            _main()
        mock_resolve.assert_called_once_with(FAKE_TOKEN, FAKE_CWD, "")

    def test_no_post_when_channel_not_found(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "hello",
        }
        _, mock_post = self._run(event, resolve_return=None)
        mock_post.assert_not_called()

    def test_post_called_with_correct_channel(self):
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "deployed",
        }
        _, mock_post = self._run(event)
        args = mock_post.call_args[0]
        self.assertEqual(args[1], FAKE_CHANNEL)

    def test_fallback_channel_from_env(self):
        """SLACK_CHANNEL_ID fallback is passed to resolve_channel."""
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "hi",
        }
        env = {"SLACK_BOT_TOKEN": FAKE_TOKEN, "SLACK_CHANNEL_ID": "CFALLBACK"}
        with patch.dict("os.environ", env, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=FAKE_CHANNEL) as mock_resolve, \
             patch("notify.post_message"):
            _main()
        mock_resolve.assert_called_once_with(FAKE_TOKEN, FAKE_CWD, "CFALLBACK")


class TestStopEventWithRecap(unittest.TestCase):
    """Stop event with [SLACK_RECAP]...[/SLACK_RECAP] block."""

    def _run(self, event: dict, resolve_return=FAKE_CHANNEL):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=resolve_return), \
             patch("notify.post_message") as mock_post:
            _main()
        return mock_post

    def test_recap_block_extracted(self):
        recap_text = "Completed task A.\nFixed bug B."
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": (
                f"Some preamble\n[SLACK_RECAP]\n{recap_text}\n"
                "[/SLACK_RECAP]\nTrailing stuff"
            ),
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn(recap_text, message_text)
        # Preamble and trailing content should not appear
        self.assertNotIn("Some preamble", message_text)
        self.assertNotIn("Trailing stuff", message_text)

    def test_recap_includes_project_name(self):
        event = {
            "hook_event_name": "Stop",
            "cwd": "/home/user/projects/my-project",
            "last_assistant_message": "[SLACK_RECAP]\nDone!\n[/SLACK_RECAP]",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("my-project", message_text)

    def test_recap_block_with_checkmark_emoji(self):
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": "[SLACK_RECAP]\nrecap here\n[/SLACK_RECAP]",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("\u2705", message_text)

    def test_recap_on_same_line(self):
        """Markers on the same line with content between them."""
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": "[SLACK_RECAP]inline recap[/SLACK_RECAP]",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("inline recap", message_text)


class TestStopEventWithoutRecap(unittest.TestCase):
    """Stop event without SLACK_RECAP block falls back to truncated last message."""

    def _run(self, event: dict, resolve_return=FAKE_CHANNEL):
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", return_value=resolve_return), \
             patch("notify.post_message") as mock_post:
            _main()
        return mock_post

    def test_short_message_used_as_body(self):
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": "Short message.",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("Short message.", message_text)

    def test_long_message_truncated_to_500_chars(self):
        long_msg = "A" * 600
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": long_msg,
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        # Message body is last 500 chars with "..." prefix
        self.assertIn("..." + "A" * 500, message_text)
        # Total length of body portion is 503 (3 dots + 500 A's)
        # But message_text also includes project name header
        self.assertIn("...", message_text)
        # Should not contain more than 500 A's in the body
        body_part = message_text.split("\n", 1)[1] if "\n" in message_text else message_text
        self.assertLessEqual(body_part.count("A"), 500)

    def test_message_exactly_500_chars_not_truncated(self):
        exact_msg = "B" * 500
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": exact_msg,
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("B" * 500, message_text)
        self.assertNotIn("...", message_text)

    def test_empty_last_assistant_message_no_body(self):
        """Empty last_assistant_message: only project header posted."""
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
            "last_assistant_message": "",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        # Just the checkmark + project name, no newline body
        project_name = Path(FAKE_CWD).name
        self.assertEqual(message_text, f"\u2705 {project_name}")

    def test_missing_last_assistant_message_key(self):
        """last_assistant_message key absent: only project header posted."""
        event = {
            "hook_event_name": "Stop",
            "cwd": FAKE_CWD,
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        project_name = Path(FAKE_CWD).name
        self.assertEqual(message_text, f"\u2705 {project_name}")

    def test_empty_cwd_uses_unknown(self):
        event = {
            "hook_event_name": "Stop",
            "cwd": "",
            "last_assistant_message": "",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("unknown", message_text)

    def test_missing_cwd_uses_unknown(self):
        event = {
            "hook_event_name": "Stop",
            "last_assistant_message": "",
        }
        mock_post = self._run(event)
        args = mock_post.call_args[0]
        message_text = args[2]
        self.assertIn("unknown", message_text)


class TestUnknownEvent(unittest.TestCase):
    """Unknown hook_event_name results in no post."""

    def test_unknown_event_no_post(self):
        event = {
            "hook_event_name": "SessionStart",
            "cwd": FAKE_CWD,
            "message": "starting up",
        }
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel") as mock_resolve, \
             patch("notify.post_message") as mock_post:
            _main()
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    def test_empty_event_name_no_post(self):
        event = {
            "hook_event_name": "",
            "cwd": FAKE_CWD,
        }
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel") as mock_resolve, \
             patch("notify.post_message") as mock_post:
            _main()
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()

    def test_missing_event_name_no_post(self):
        event = {"cwd": FAKE_CWD}
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel") as mock_resolve, \
             patch("notify.post_message") as mock_post:
            _main()
        mock_post.assert_not_called()
        mock_resolve.assert_not_called()


class TestExceptionHandling(unittest.TestCase):
    """The module-level try/except ensures exceptions in main() don't propagate."""

    def test_exception_in_main_does_not_raise(self):
        """Even if resolve_channel raises, the try/except at module level catches it.
        We test main() itself here; the wrapping is at module level."""
        event = {
            "hook_event_name": "Notification",
            "cwd": FAKE_CWD,
            "message": "boom",
        }
        with patch.dict("os.environ", {"SLACK_BOT_TOKEN": FAKE_TOKEN}, clear=False), \
             patch("sys.stdin", _make_stdin(event)), \
             patch("pathlib.Path.exists", return_value=False), \
             patch("notify.resolve_channel", side_effect=RuntimeError("network error")):
            # main() itself will raise; the try/except is at module level.
            # Here we verify that calling main() does raise (since we're calling
            # it directly, not via the module-level wrapper).
            with self.assertRaises(RuntimeError):
                _main()


if __name__ == "__main__":
    unittest.main()
