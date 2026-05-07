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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from slack_channel import resolve_channel, post_message


def main():
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent))
    if Path(plugin_root, ".slack-notify-disabled").exists():
        return

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
        project_name = Path(cwd).name if cwd else "unknown"
        last_msg = event.get("last_assistant_message", "")
        recap = None
        if last_msg:
            start_marker = "[SLACK_RECAP]"
            end_marker = "[/SLACK_RECAP]"
            start_idx = last_msg.find(start_marker)
            end_idx = last_msg.find(end_marker)
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                recap = last_msg[start_idx + len(start_marker):end_idx].strip()
        if recap:
            body = recap
        elif last_msg:
            stripped = last_msg.strip()
            if len(stripped) > 500:
                body = "..." + stripped[-500:]
            else:
                body = stripped
        else:
            body = None
        message_text = f"\u2705 {project_name}"
        if body:
            message_text += f"\n{body}"
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
