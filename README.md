# slack-fork-pizza

Get pinged in Slack when Claude Code needs your attention — one channel per project, automatically routed by project directory name.

## Quick install

Add the following to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "slack-notify": {
      "source": {
        "source": "github",
        "repo": "chadallen/slack-fork-pizza"
      }
    }
  },
  "enabledPlugins": {
    "slack-notify@slack-notify": true
  },
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here"
  }
}
```

That's it. The plugin registers its own hooks — no additional settings.json editing required.

## How it works

When Claude Code fires a `Notification` or `Stop` event, the plugin posts a message to the Slack channel whose name matches your project directory. For example, a project at `~/projects/my-app` posts to `#my-app`. If no matching channel exists, messages fall back to the channel specified by `SLACK_CHANNEL_ID`. An MCP server exposes an `ask_human` tool for interactive prompts from within an agent session.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-…`) |
| `SLACK_CHANNEL_ID` | No | Fallback channel ID when no project channel matches |

Both variables go in the `env` block of `~/.claude/settings.json`.

## Slack app setup

Run `/slack:setup` inside Claude Code for a guided walkthrough. Or do it manually:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Under **OAuth & Permissions**, add bot scopes: `chat:write`, `channels:read`.
3. Install to your workspace and copy the **Bot User OAuth Token**.
4. Create a Slack channel for each project (name must match the project directory).
5. Invite the bot to each channel: `/invite @YourAppName`.

## Channel naming

The plugin routes messages based on the **directory name on disk** — specifically the last component of the working directory Claude Code is running in. For example:

| Project directory | Slack channel |
|---|---|
| `~/projects/my-app` | `#my-app` |
| `~/projects/slack-fork-pizza` | `#slack-fork-pizza` |
| `~/work/client-dashboard` | `#client-dashboard` |

This is the actual folder name, not the sanitized path under `~/.claude/projects/`. Create matching channels in Slack and invite the bot.

## Compatibility

Works standalone or alongside the fork-pizza plugin. If both are enabled, they compose without conflict — each handles its own hooks.
