# PRD: slack-notify — Claude Code Slack Plugin

## Problem

When running multiple Claude Code sessions across projects, there's no way to know when a session needs attention without watching every terminal. Sessions run silently and only surface when they stop or ask a question.

## Goal

Slack becomes the attention layer. Terminals run headlessly. The user only looks at Slack when needed — and can reply to Claude from Slack when input is required.

---

## What Was Built

### Plugin architecture

`slack-notify` is a Claude Code plugin installed via the marketplace UI. On install, it auto-registers:
- **Hooks:** `Notification`, `Stop`, `SessionStart`
- **MCP server:** `ping-user`
- **Slash command:** `/slack:setup`

Plugin manifest lives at `.claude-plugin/plugin.json`. Install by adding the repo as a directory marketplace source pointing to `.claude-plugin/marketplace.json`.

### Channel-per-project routing

Each project maps to a Slack channel by name: directory `~/projects/foo` routes to `#foo`. Channel lookup uses `conversations.list` (paginated, cached in memory). Falls back to `SLACK_CHANNEL_ID` env var if no matching channel exists.

Implementation: `slack_channel.py` — shared module imported by both `notify.py` and `ping_user_mcp.py`.

### Outbound notifications (`notify.py`)

Handles `Notification` and `Stop` hook events:
- `Notification`: posts `🔔 <message>` to the project channel
- `Stop`: posts `✅ Agent stopped — ready for next prompt` with the last assistant message appended

No threading. No state files. Each event is a flat message in the project's channel.

### Round-trip: Claude asks, user replies (`ping_user_mcp.py`)

MCP stdio server exposing one tool: `ping_user(question: str) → str`.

When Claude calls `ping_user`:
1. Posts `❓ *Claude needs input:* <question>` to the project channel
2. Polls `conversations.replies` every 3 seconds
3. Returns the first non-bot reply text to Claude
4. Times out after 5 minutes

Claude-initiated — Claude must decide to call `ping_user`. This is intentional: it avoids the need for a persistent daemon and works within Claude Code's current IPC constraints (no mechanism exists to inject a prompt into a running interactive session from outside).

### SessionStart convention injection (`scripts/inject-conventions.sh`)

On every session start, injects `docs/conventions.md` as context. Teaches Claude:
- What `ping_user` is and when to use it
- Channel-per-project routing behavior

### Setup slash command (`commands/setup.md`)

`/slack:setup` guides through:
1. Validating or creating a Slack bot token
2. Configuring `SLACK_BOT_TOKEN` (required) and `SLACK_CHANNEL_ID` (optional fallback)
3. Creating per-project channels and inviting the bot

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_CHANNEL_ID` | No | Fallback channel ID if no project channel exists |

Scopes required on the Slack app: `chat:write`, `channels:read`.

---

## Key Design Decisions

**Channel-per-project over threading.** The original plan used one shared channel with threads keyed by `cwd`. Replaced with dedicated channels per project — simpler Slack UX, no state file needed, each project's messages are naturally scoped.

**MCP round-trip over daemon + hook injection.** Research (`docs/round-trip-research.md`) confirmed there's no stable IPC mechanism for injecting into a running session. The `UserPromptSubmit` + `additionalContext` hook approach requires a persistent daemon and has documented reliability issues. The MCP tool pattern — where Claude explicitly calls `ping_user` — is simpler, more reliable, and ships without a background process.

**Stdlib only.** No pip dependencies. The plugin installs and runs with whatever Python 3 is on the system.

**Always exit 0.** All hook scripts wrap logic in `try/except` and exit 0 unconditionally. A non-zero exit blocks Claude Code.

---

## File Map

```
notify.py              — Notification/Stop hook handler
ping_user_mcp.py       — MCP server (ping_user tool)
slack_channel.py       — Channel lookup shared module
.claude-plugin/
  plugin.json          — Plugin manifest
  marketplace.json     — Local marketplace source
hooks/
  hooks.json           — Hook registrations (Notification, Stop, SessionStart)
scripts/
  inject-conventions.sh — SessionStart hook; injects docs/conventions.md
commands/
  setup.md             — /slack:setup slash command
docs/
  conventions.md       — ping_user conventions injected at session start
  round-trip-research.md — Research on round-trip feasibility (May 2026)
  prd.md               — This document
```

---

## Out of Scope

- Slack → CLI injection without Claude initiating (requires unsupported IPC — see `docs/round-trip-research.md`)
- Multiple concurrent Claude sessions per project directory
- Block Kit / rich formatting
- Slack channel creation (user creates channels manually)
- Mobile push or other notification targets

---

## Integration Points for fork-pizza

The plugin surfaces these integration points for fork-pizza tooling:

- **`ping_user` MCP tool** — available in any session with the plugin installed. Call `ping_user(question)` to block on a Slack reply. Documented in `docs/conventions.md`.
- **`slack_channel.py`** — `find_channel_id(token, project_name)` and `resolve_channel(token, cwd, fallback)` are importable from any script running in the plugin root.
- **Channel naming convention** — project directory name = Slack channel name. fork-pizza can rely on this to route messages predictably.
- **`SLACK_BOT_TOKEN` env var** — available in all hook and MCP contexts once the plugin is installed and configured.
