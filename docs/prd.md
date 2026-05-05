# PRD: Claude Code → Slack Session Notifications

## Problem

When running multiple Claude Code sessions across projects, the user has no way to know when a session needs attention without watching every terminal. Sessions run silently and only matter when they stop or ask a question.

## Goal

Slack becomes the attention layer. Terminals run headlessly. User only looks at Slack when needed.

## User Stories

- As a user with 3 projects running, I want to see a Slack message when any session stops or asks a question, so I don't have to watch terminals.
- As a user who just got pinged, I want to know which project it's from and what it needs, so I can decide whether to engage.
- As a user who ran `/clear` in a terminal, I want subsequent messages to appear in the same Slack thread as before, so the project's conversation history stays together.
- As a user who wants more detail, I want to be able to go to the terminal and pick up there.

## Functional Requirements

### Notifications
- On `Stop`: post "Agent finished — ready for next prompt" to the project's thread
- On `Notification` (AskUserQuestion etc.): post the message content to the project's thread
- Messages are brief — no verbose output, no tool call traces

### Thread model
- One thread per project directory (`cwd`)
- Thread persists across `/clear`, restarts, and new invocations in the same project
- Thread is created on first event for a project; reused for all subsequent events
- Thread header (first message) identifies the project by name

### Session persistence
- Mapping of `project_path → slack_thread_ts` stored in `~/.claude/slack-sessions.json`
- File is created automatically on first use

## Out of Scope (v1)
- Replying from Slack back to the CLI
- Multiple concurrent Claude sessions in the same project directory
- Slack channel creation (uses one pre-existing channel)
- Rich formatting / Block Kit buttons
- Mobile push or other notification targets

## Technical Approach

**What changes from current setup:**
1. Swap incoming webhook → Slack Bot token + `chat.postMessage` (needed to get back the `thread_ts` on first post)
2. Upgrade `slack-notify.py` to manage project→thread mapping
3. Add `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` to `settings.json` env

**User does (Slack app config, ~5 min):**
- Add `chat:write` OAuth scope to the app
- Install app to workspace → copy Bot User OAuth Token
- Invite the bot to your target channel
- Provide token + channel ID

**Developer does:**
- Write `slack-notify.py` (~80 lines, stdlib only — no pip install required)
- Document env vars and hook configuration

## Slack UX

```
#claude-sessions channel

┌─ [browser-agent] New session ───────────────┐
│  ✅ Agent stopped — ready for next prompt   │
│  🔔 Should I delete these files? (y/n)      │
│  ✅ Agent stopped — ready for next prompt   │
└──────────────────────────────────────────────┘

┌─ [fork-pizza] New session ──────────────────┐
│  ✅ Agent stopped — ready for next prompt   │
└──────────────────────────────────────────────┘
```

## Open Questions
- Repo name and distribution strategy (standalone repo vs. plugin)
- v2 round-trip: Slack reply → CLI (requires persistent listener process)
