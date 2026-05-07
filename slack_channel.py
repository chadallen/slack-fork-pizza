"""
Shared Slack channel lookup utilities.

Provides find_channel_id for paginated conversations.list lookup with caching,
resolve_channel as a convenience wrapper that derives the project name from
a cwd path and falls back to a provided channel ID, and post_message for
posting to a Slack channel.

Stdlib only — no pip dependencies.
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path

SLACK_LIST_URL = "https://slack.com/api/conversations.list"
SLACK_POST_URL = "https://slack.com/api/chat.postMessage"

# Module-level cache: channel name -> channel ID
_channel_cache: dict = {}


def find_channel_id(token: str, project_name: str) -> str | None:
    """Look up the Slack channel ID for project_name using conversations.list.

    Iterates through all pages of conversations.list, caching every channel
    name seen. Returns the channel ID string, or None if not found.
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
    """Post a message to a Slack channel.

    Returns the parsed JSON response dict. Callers can check response['ok']
    and retrieve fields like response['ts'].
    """
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


def resolve_channel(token: str, cwd: str, fallback_channel: str) -> str | None:
    """Resolve the Slack channel for a given working directory.

    Extracts the project name from the last component of cwd, then calls
    find_channel_id. Falls back to fallback_channel if no matching channel
    is found. Returns None only if both lookups fail.
    """
    project_name = Path(cwd).name if cwd else ""
    channel = None
    if project_name:
        channel = find_channel_id(token, project_name)
    if not channel:
        channel = fallback_channel or None
    return channel
