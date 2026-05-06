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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from slack_channel import resolve_channel

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"


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

    channel = resolve_channel(token, cwd, fallback_channel or "")

    if not channel:
        return

    post_message(token, channel, message_text)


try:
    main()
except Exception:
    pass

sys.exit(0)
