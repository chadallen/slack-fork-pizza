# slack-fork-pizza

Get pinged in Slack when Claude Code needs your attention — and reply from Slack when it asks for help. One channel per project, automatically routed by directory name.

## Install

```
/plugin marketplace add chadallen/slack-fork-pizza
/plugin install slack-notify@slack-notify
```

Then add your Slack bot token to `~/.claude/settings.json`:

```json
{
  "env": {
    "SLACK_BOT_TOKEN": "xoxb-your-token-here"
  }
}
```

The plugin registers its own hooks and MCP server — no other configuration needed.

## What you get

**Outbound notifications (automatic):** When Claude stops or needs attention, a message appears in your project's Slack channel. No configuration beyond install — this just works.

**Inbound replies (ping_user):** When Claude calls the `ping_user` tool, it posts a question to Slack and waits up to 5 minutes for you to reply **in the thread**. Your reply goes back to Claude and it continues working. This is how you answer Claude from your phone/desktop without going back to the terminal.

## Slack app setup

Run `/slack:setup` inside Claude Code for a guided walkthrough. Or do it manually:

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**.
2. Name it something like "Claude Code" and pick your workspace.
3. Go to **OAuth & Permissions** → **Bot Token Scopes** and add:
   - `chat:write` — post messages
   - `channels:read` — look up channels by name
4. Click **Install to Workspace** → **Allow**.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-`).
6. For each project, create a Slack channel matching the directory name (see [Channel naming](#channel-naming)).
7. Invite the bot to each channel: `/invite @Claude Code`

## Channel naming

The plugin routes messages based on the **directory name on disk** — the last component of the working directory Claude Code is running in:

| Project directory | Slack channel |
|---|---|
| `~/projects/my-app` | `#my-app` |
| `~/projects/slack-fork-pizza` | `#slack-fork-pizza` |
| `~/work/client-dashboard` | `#client-dashboard` |

This is the actual folder name, not the sanitized path under `~/.claude/projects/`.

## Configuration

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-…`) |
| `SLACK_CHANNEL_ID` | No | Fallback channel ID when no project channel matches |

Both go in the `env` block of `~/.claude/settings.json`.

## Telling Claude when to use ping_user

The plugin injects default instructions at session start, but you can reinforce or customize the behavior in your project's `CLAUDE.md`:

```markdown
## Slack

When you need human input, use the ping_user tool to ask via Slack.
I may be away from the terminal but monitoring Slack on my phone.
```

More specific examples:

```markdown
## Slack

- Use ping_user before deleting files, dropping tables, or force-pushing.
- Use ping_user when a task requirement is ambiguous and you can't proceed.
- Don't use ping_user for routine status updates — I'll see the Stop notification.
- If ping_user times out, stop and wait for my next prompt.
```

For autonomous sessions where Claude runs for a while unattended:

```markdown
## Slack

This is a long-running autonomous session. Use ping_user liberally:
- Before any irreversible action
- When you hit a fork in the road and either path is reasonable
- When you finish a major milestone and want approval before continuing
- If you encounter an error you can't resolve after 2 attempts
```

## Hook trust model

The plugin runs scripts automatically each session — `notify.py` on Stop/Notification events, `inject-conventions.sh` on SessionStart, and `ping_user_mcp.py` as a persistent MCP server. These scripts are controlled by the plugin author and run with your full user permissions.

Pin to a tag (e.g., `@v0.1.0`) so you control when you take updates, and review the diff before upgrading.

## Compatibility

Works standalone or alongside the fork-pizza plugin. If both are enabled, they compose without conflict.
