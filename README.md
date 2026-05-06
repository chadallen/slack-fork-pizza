# slack-fork-pizza

Slack notifications for Claude Code CLI. Get pinged in Slack when your agent needs attention — one channel per project, automatically routed by project directory name.

## How it works

`notify.py` is a Claude Code hook script that reads hook event JSON from stdin and posts messages to Slack. Each event is posted as a standalone message to the Slack channel whose name matches the current project directory (e.g. a project at `~/projects/my-app` posts to `#my-app`). If no matching channel is found, messages fall back to a default channel. Two events are handled:

- **Notification** — posted when Claude needs your input
- **Stop** — posted when the agent finishes and is ready for the next prompt

The script uses stdlib only — no pip install required.

---

## Setup

### 1. Create a Slack app and get a bot token

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**.
2. Give it a name (e.g. "Claude Code") and select your workspace.
3. In the left sidebar go to **OAuth & Permissions**.
4. Under **Bot Token Scopes**, add the following scopes:
   - `chat:write` — to post messages
   - `channels:read` — to look up channels by name
5. Scroll up and click **Install to Workspace**, then **Allow**.
6. Copy the **Bot User OAuth Token** — it starts with `xoxb-`. You'll need this shortly.

### 2. Create a channel for each project

Create a Slack channel whose name matches your project directory name. For example, if your project lives at `/Users/you/projects/my-app`, create a channel named `my-app`.

Invite the bot to each channel you create:

```
/invite @YourAppName
```

### 3. Get a fallback channel ID

If no channel matches the current project name, the script falls back to a default channel. Open Slack and navigate to the channel you want to use as the fallback. Click the channel name at the top to open channel details. Scroll to the bottom of the details pane — the channel ID is shown there (e.g. `C0B287AN1`). Copy it, and invite the bot to that channel as well.

### 4. Add env vars to `~/.claude/settings.json`

Add `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` (fallback) to the `env` object in `~/.claude/settings.json`:

```json
{
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here",
    "SLACK_CHANNEL_ID": "C0B287AN1"
  }
}
```

Replace the values with your actual bot token and fallback channel ID.

### 5. Add hooks to `~/.claude/settings.json`

Add the following `hooks` object to `~/.claude/settings.json`, replacing `/path/to/notify.py` with the absolute path to `notify.py` in this repo (e.g. `/Users/yourname/projects/slack-fork-pizza/notify.py`):

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/notify.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/notify.py"
          }
        ]
      }
    ]
  }
}
```

If you already have an `env` section, merge everything into the same top-level object. A complete `~/.claude/settings.json` with both sections looks like:

```json
{
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here",
    "SLACK_CHANNEL_ID": "C0B287AN1"
  },
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/notify.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/notify.py"
          }
        ]
      }
    ]
  }
}
```

---

## Verification

Start a Claude Code session in any project that has a matching Slack channel. When the agent finishes or sends a notification, you should see a message appear in that project's channel.

If messages are not appearing, check that:

- The bot token is set correctly in `settings.json`
- The bot has the `chat:write` and `channels:read` scopes
- The bot has been invited to the target channel
- The channel name exactly matches the project directory name
- The path to `notify.py` in the hooks config is an absolute path
