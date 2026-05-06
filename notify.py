#!/usr/bin/env python3
"""
Claude Code hook script: posts Slack notifications to per-project channels.

Reads hook event JSON from stdin. Handles Notification and Stop events.
Uses conversations.list to find a channel matching the project directory name.
Falls back to SLACK_CHANNEL_ID if no matching channel is found.
Always exits 0 to avoid blocking Claude Code.
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
SLACK_LIST_URL = "https://slack.com/api/conversations.list"

# Module-level cache: channel name -> channel ID
_channel_cache: dict = {}


def find_channel_id(token: str, project_name: str) -> str | None:
    """Look up the Slack channel ID for project_name using conversations.list.

    Results are cached in _channel_cache to avoid repeated API calls.
    Returns the channel ID string, or None if not found.
    """
    if project_name in _channel_cache:
        return _channel_cache[project_name]

    cursor = None
    while True:
        params: dict = {"limit": 200, "exclude_archived": "true"}
        if cursor:
            params["cursor"] = cursor

        url = SLACK_LIST_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        if not data.get("ok"):
            break

        for channel in data.get("channels", []):
            name = channel.get("name", "")
            _channel_cache[name] = channel["id"]

        next_cursor = (
            data.get("response_metadata", {}).get("next_cursor") or ""
        )
        if not next_cursor:
            break
        cursor = next_cursor

    return _channel_cache.get(project_name)


def post_message(token: str, channel: str, text: str) -> dict:
    payload = {"channel": channel, "text": text}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_POST_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    fallback_channel = os.environ.get("SLACK_CHANNEL_ID")

    if not token:
        return

    raw = sys.stdin.read()
    event = json.loads(raw)

    hook_event = event.get("hook_event_name", "")
    cwd = event.get("cwd", "")

    if hook_event == "Notification":
        message_text = "\U0001f514 " + event.get("message", "")
    elif hook_event == "Stop":
        message_text = "\u2705 Agent stopped \u2014 ready for next prompt"
        last_msg = event.get("last_assistant_message", "")
        if last_msg:
            message_text += f"\n{last_msg.strip()}"
    else:
        return

    project_name = Path(cwd).name if cwd else ""

    channel = None
    if project_name:
        channel = find_channel_id(token, project_name)

    if not channel:
        channel = fallback_channel

    if not channel:
        return

    post_message(token, channel, message_text)


try:
    main()
except Exception:
    pass

sys.exit(0)
