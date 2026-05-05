# slack-fork-pizza

Slack notifications for Claude Code CLI. Get pinged in Slack when your agent needs attention — one thread per project, silence while it's working.

## How it works

`notify.py` is a Claude Code hook script that reads hook event JSON from stdin and posts threaded messages to Slack. Each project working directory gets its own thread. Two events are handled:

- **Notification** — posted as a reply in the project thread (e.g. when Claude needs your input)
- **Stop** — posted as a reply when the agent finishes and is ready for the next prompt

Thread state is persisted in `~/.claude/slack-sessions.json`. The script uses stdlib only — no pip install required.

---

## Setup

### 1. Create a Slack app and get a bot token

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**.
2. Give it a name (e.g. "Claude Code") and select your workspace.
3. In the left sidebar go to **OAuth & Permissions**.
4. Under **Bot Token Scopes**, add the scope: `chat:write`
5. Scroll up and click **Install to Workspace**, then **Allow**.
6. Copy the **Bot User OAuth Token** — it starts with `xoxb-`. You'll need this shortly.

### 2. Get the channel ID

Open Slack and navigate to the channel where you want notifications posted. Click the channel name at the top to open channel details. Scroll to the bottom of the details pane — the channel ID is shown there (e.g. `C0B287AN1`). Copy it.

### 3. Invite the bot to the channel

In Slack, open the channel and type:

```
/invite @YourAppName
```

Replace `YourAppName` with the name you gave your Slack app. The bot must be a member of the channel to post messages.

### 4. Add env vars to `~/.claude/settings.json`

Add `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` to the `env` object in `~/.claude/settings.json`:

```json
{
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here",
    "SLACK_CHANNEL_ID": "C0B287AN1"
  }
}
```

Replace the values with your actual bot token and channel ID.

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

Start a Claude Code session in any project. When the agent finishes or sends a notification, you should see a message appear in your Slack channel. The first event in a given project directory creates a new thread; subsequent events in the same session reply to that thread.

If messages are not appearing, check that:

- The bot token and channel ID are set correctly in `settings.json`
- The bot has been invited to the channel
- The path to `notify.py` in the hooks config is an absolute path and the file is executable
