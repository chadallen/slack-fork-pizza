# PRD: slack-notify — Claude Code Slack Plugin

## Problem

When running multiple Claude Code sessions across projects, there's no way to know when a
session needs attention without watching every terminal. Sessions run silently and only
surface when you switch to the right terminal at the right time.

## Goal

Slack becomes the attention layer. Terminals run headlessly. When an agent finishes a turn,
the relevant Slack channel gets the agent's last message — so you know what happened and
whether it needs your attention.

---

## Core Feature: One-Way Notification

### How it works

The `Stop` hook fires `notify.py` every time Claude finishes a turn. It posts the agent's
last assistant message to a Slack channel matching the project directory name.

- Directory `~/projects/foo` routes to `#foo`
- Message format: `✅ Agent stopped — ready for next prompt` followed by the last message
- Falls back to `SLACK_CHANNEL_ID` env var if no matching channel exists
- The `Notification` hook also fires `notify.py` for explicit `🔔` notifications

No threading. No state files. Each event is a flat message in the project's channel.

### Channel-per-project routing

Channel lookup uses Slack `conversations.list` (paginated, cached in memory).
Implementation: `slack_channel.py` — shared module imported by `notify.py` and
`ping_user_mcp.py`.

### Plugin architecture

`slack-notify` is a Claude Code plugin installed via the marketplace UI. On install, it
auto-registers:
- **Hooks:** `Notification`, `Stop`, `SessionStart`
- **MCP server:** `ping-user` (optional — see below)
- **Slash command:** `/slack:setup`

Plugin manifest lives at `.claude-plugin/plugin.json`. Install by adding the repo as a
directory marketplace source pointing to `.claude-plugin/marketplace.json`.

---

## Optional: ping_user MCP Round-Trip

An experimental add-on. `ping_user_mcp.py` exposes a `ping_user(question)` MCP tool that
posts a question to the project channel and polls for a threaded reply (3s interval, 5min
timeout). Claude must explicitly call it — there's no way to inject into a running session
from outside.

This works but is secondary to the core one-way notification. The `SessionStart` hook
injects `docs/conventions.md` to teach Claude when to use it.

See `docs/round-trip-research.md` for feasibility research on alternative approaches.

---

## Setup

`/slack:setup` guides through:
1. Validating or creating a Slack bot token
2. Configuring `SLACK_BOT_TOKEN` (required) and `SLACK_CHANNEL_ID` (optional fallback)
3. Creating per-project channels and inviting the bot

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (`xoxb-...`) |
| `SLACK_CHANNEL_ID` | No | Fallback channel ID if no project channel exists |

Scopes required on the Slack app: `chat:write`, `channels:read`.

---

## Key Design Decisions

See also: `docs/adr/001-one-way-notification.md`

**One-way notification as the primary pattern.** The Stop hook posting the last assistant
message to a per-project channel covers the main use case: knowing what an agent did without
watching the terminal. Full round-trip (Slack replies reaching the CLI) is possible via the
`ping_user` MCP tool but is optional.

**Channel-per-project over threading.** v1 used one shared channel with threads keyed by
`cwd`. Replaced with dedicated channels per project — simpler Slack UX, no state file, each
project's messages naturally scoped.

**Stdlib only.** No pip dependencies. Runs with whatever Python 3 is on the system.

**Always exit 0.** All hook scripts wrap logic in `try/except` and exit 0 unconditionally.
A non-zero exit blocks Claude Code.

---

## File Map

```
notify.py              — Notification/Stop hook handler (core)
slack_channel.py       — Channel lookup shared module
ping_user_mcp.py       — MCP server for round-trip (optional)
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
  round-trip-research.md — Research on round-trip feasibility
  prd.md               — This document
  adr/                 — Architecture Decision Records
```

---

## Out of Scope

- Slack → CLI injection without Claude initiating (see `docs/round-trip-research.md`)
- Multiple concurrent Claude sessions per project directory
- Block Kit / rich formatting
- Slack channel creation (user creates channels manually)
- Mobile push or other notification targets

---

## Integration Points for fork-pizza

- **`slack_channel.py`** — `find_channel_id(token, project_name)` and `resolve_channel(token, cwd, fallback)` are importable from any script running in the plugin root.
- **Channel naming convention** — project directory name = Slack channel name. fork-pizza can rely on this to route messages predictably.
- **`SLACK_BOT_TOKEN` env var** — available in all hook and MCP contexts once the plugin is installed and configured.
- **`ping_user` MCP tool** (optional) — call `ping_user(question)` to block on a Slack reply. Documented in `docs/conventions.md`.
