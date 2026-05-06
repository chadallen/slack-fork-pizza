#!/usr/bin/env python3
"""
Claude Code hook script: posts Slack notifications with per-project threading.

Reads hook event JSON from stdin. Handles Notification and Stop events.
Thread state persisted in ~/.claude/slack-sessions.json.
Always exits 0 to avoid blocking Claude Code.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

SESSIONS_FILE = Path.home() / ".claude" / "slack-sessions.json"
SLACK_API_URL = "https://slack.com/api/chat.postMessage"


def load_sessions():
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_sessions(sessions):
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


def post_message(token, channel, text, thread_ts=None):
    payload = {"channel": channel, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_API_URL,
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
    channel = os.environ.get("SLACK_CHANNEL_ID")

    if not token or not channel:
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

    sessions = load_sessions()
    thread_ts = sessions.get(cwd)

    if not thread_ts:
        project_name = Path(cwd).name if cwd else "unknown"
        anchor_text = f"[{project_name}] New session"
        result = post_message(token, channel, anchor_text)
        if result.get("ok"):
            thread_ts = result["ts"]
            sessions[cwd] = thread_ts
            save_sessions(sessions)

    if thread_ts:
        post_message(token, channel, message_text, thread_ts=thread_ts)


try:
    main()
except Exception:
    pass

sys.exit(0)
