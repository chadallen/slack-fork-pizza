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
