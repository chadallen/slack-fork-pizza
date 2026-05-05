# Build Handoff: slack-fork-pizza

## What You're Building

A Claude Code CLI → Slack notification bridge. When a Claude Code session stops or asks a question, it posts a message to a Slack thread for that project. The user monitors Slack instead of watching terminals.

This is a real project at `~/projects/slack-fork-pizza` with a GitHub repo at `https://github.com/chadallen/slack-fork-pizza`. Build there.

Read `docs/prd.md` before writing any code.

---

## Current State

A partial v0 already exists. The user's `~/.claude/settings.json` already has:
- `Notification` and `Stop` hooks configured, both pointing to `~/.claude/scripts/slack-notify.py`
- `SLACK_WEBHOOK_URL` in the `env` block (a working incoming webhook)
- The existing `slack-notify.py` sends flat messages to Slack with no threading

The existing script works but has no threading — every project posts to the same channel as flat messages. You are replacing it with the threaded version described in the PRD.

---

## What Needs to Be Built

### 1. `notify.py` — the main script
Location: `~/projects/slack-fork-pizza/notify.py`

Behavior:
- Reads hook event JSON from stdin (Claude Code pipes it in)
- On `Notification` event: posts the message content to the project's Slack thread
- On `Stop` event: posts "Agent stopped — ready for next prompt" to the project's Slack thread
- Ignores all other events
- Thread key is `cwd` (project directory path) — one thread per project, survives `/clear`
- On first event for a project: calls `chat.postMessage` to create a new message in the channel, saves the returned `ts` as the thread anchor
- On subsequent events for a project: calls `chat.postMessage` with `thread_ts` set to the saved `ts`
- Thread state persisted in `~/.claude/slack-sessions.json` (a JSON dict of `{cwd: thread_ts}`)
- `slack-sessions.json` must NOT be committed (already in `.gitignore`)
- Uses only Python stdlib — no pip install, no third-party packages
- Exits 0 always — a non-zero exit would block Claude Code

Environment variables (set in `~/.claude/settings.json`):
- `SLACK_BOT_TOKEN` — Bot User OAuth Token (starts with `xoxb-`)
- `SLACK_CHANNEL_ID` — the channel ID to post to (not the name, the ID like `C0B287AN1`)

### 2. Update `~/.claude/settings.json`
- Add `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` to the `env` block
- Remove `SLACK_WEBHOOK_URL` from the `env` block
- Update both hook commands to point to `~/projects/slack-fork-pizza/notify.py` instead of `~/.claude/scripts/slack-notify.py`

### 3. Update `README.md`
Write clear setup instructions covering:
- How to create the Slack app and get a bot token (add `chat:write` scope, install to workspace)
- How to get the channel ID
- Which env vars to add to `settings.json`
- Which hooks to add to `settings.json` (include the exact JSON snippet)
- How to invite the bot to the channel

---

## What NOT to Build in v1
- Round-trip replies (Slack → CLI) — explicitly out of scope
- Multiple concurrent Claude sessions per project
- Block Kit / rich formatting
- Slack channel creation
- Any new dependencies

---

## Before You Start Coding

The user needs to complete a Slack app config step first — adding the `chat:write` scope and getting a bot token. The Slack app already exists (App ID: `A0B2PKDCEBA`, workspace: `fork-pizza`).

**Ask the user for `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` before writing any code.** Once they provide those, you can build and test end-to-end.

---

## Testing

Once built, test by running:
```bash
echo '{"hook_event_name":"Stop","cwd":"/Users/chadallen/projects/slack-fork-pizza"}' | \
  SLACK_BOT_TOKEN=<token> SLACK_CHANNEL_ID=<channel> python3 ~/projects/slack-fork-pizza/notify.py
```

Run it twice — first run should create a thread, second run should reply in the same thread.

Then run with a different `cwd` to confirm a separate thread is created.

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
