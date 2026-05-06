#!/usr/bin/env python3
"""
MCP server exposing an ask_human tool.

Posts a question to the project's Slack channel, polls for a thread reply,
and returns the reply text to Claude. Stdlib only.

Register in ~/.claude/settings.json:
  "mcpServers": {
    "ask-human": {
      "command": "python3",
      "args": ["/Users/chadallen/projects/slack-fork-pizza/ask_human_mcp.py"],
      "env": {"SLACK_BOT_TOKEN": "xoxb-...", "SLACK_CHANNEL_ID": "C0..."}
    }
  }
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from slack_channel import find_channel_id

SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
SLACK_REPLIES_URL = "https://slack.com/api/conversations.replies"
SLACK_AUTH_URL = "https://slack.com/api/auth.test"

POLL_INTERVAL = 3  # seconds between polling
TIMEOUT = 300  # 5 minutes


def get_bot_user_id(token: str) -> str | None:
    """Get the bot's own user ID to filter out its messages."""
    req = urllib.request.Request(
        SLACK_AUTH_URL, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    if data.get("ok"):
        return data.get("user_id")
    return None


def post_message(token: str, channel: str, text: str) -> str | None:
    """Post a message to Slack. Returns the thread timestamp (ts) or None."""
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
        result = json.loads(resp.read())
    if result.get("ok"):
        return result.get("ts")
    return None


def poll_for_reply(token: str, channel: str, thread_ts: str, bot_user_id: str) -> str:
    """Poll conversations.replies until a non-bot reply appears or timeout."""
    deadline = time.time() + TIMEOUT

    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)

        params = urllib.parse.urlencode({
            "channel": channel,
            "ts": thread_ts,
            "limit": 10,
        })
        url = SLACK_REPLIES_URL + "?" + params
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:
            continue

        if not data.get("ok"):
            continue

        for msg in data.get("messages", []):
            # Skip the original question (parent message)
            if msg.get("ts") == thread_ts:
                continue
            # Skip bot's own messages
            if msg.get("user") == bot_user_id:
                continue
            if msg.get("bot_id"):
                continue
            # Found a human reply
            return msg.get("text", "")

    raise TimeoutError(f"No reply received within {TIMEOUT}s")


def handle_ask_human(arguments: dict) -> dict:
    """Execute the ask_human tool."""
    question = arguments.get("question", "")
    if not question:
        return {"content": [{"type": "text", "text": "Error: question is required"}], "isError": True}

    token = os.environ.get("SLACK_BOT_TOKEN", "")
    fallback_channel = os.environ.get("SLACK_CHANNEL_ID", "")

    if not token:
        return {"content": [{"type": "text", "text": "Error: SLACK_BOT_TOKEN not set"}], "isError": True}

    # Determine project channel from cwd
    project_name = Path.cwd().name
    channel = find_channel_id(token, project_name) or fallback_channel

    if not channel:
        return {"content": [{"type": "text", "text": "Error: no Slack channel found"}], "isError": True}

    # Get bot's user ID to filter replies
    bot_user_id = get_bot_user_id(token) or ""

    # Post question
    thread_ts = post_message(token, channel, f"\u2753 *Claude needs input:*\n{question}")
    if not thread_ts:
        return {"content": [{"type": "text", "text": "Error: failed to post to Slack"}], "isError": True}

    # Poll for reply
    try:
        reply = poll_for_reply(token, channel, thread_ts, bot_user_id)
    except TimeoutError as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}

    return {"content": [{"type": "text", "text": reply}]}


# --- MCP JSON-RPC protocol ---

def send_response(response: dict):
    """Write a JSON-RPC response to stdout."""
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def handle_message(msg: dict):
    """Route a JSON-RPC request to the appropriate handler."""
    method = msg.get("method", "")
    msg_id = msg.get("id")

    # Notifications (no id) — acknowledge silently
    if msg_id is None:
        return

    if method == "initialize":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "ask-human", "version": "1.0.0"},
            },
        })

    elif method == "tools/list":
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "ask_human",
                        "description": (
                            "Ask the human a question via Slack. Posts to the project's "
                            "Slack channel and waits up to 5 minutes for a reply. Use this "
                            "when you need clarification, approval, or input from the user."
                        ),
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "question": {
                                    "type": "string",
                                    "description": "The question to ask the human",
                                }
                            },
                            "required": ["question"],
                        },
                    }
                ]
            },
        })

    elif method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name == "ask_human":
            result = handle_ask_human(arguments)
        else:
            result = {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

        send_response({"jsonrpc": "2.0", "id": msg_id, "result": result})

    else:
        send_response({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })


def main():
    """Read JSON-RPC messages from stdin, dispatch, respond on stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle_message(msg)


if __name__ == "__main__":
    main()
