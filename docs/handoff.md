# Design History

## v1 (May 2025) — Threading model

Original design used a single Slack channel with per-project threads:
- One channel (`SLACK_CHANNEL_ID`) for all projects
- Thread state in `~/.claude/slack-sessions.json` (`{cwd: thread_ts}`)
- Incoming webhook → swapped to Bot token to get back `thread_ts` on first post
- Round-trip replies explicitly out of scope

## v2 (May 2026) — Channel-per-project + plugin architecture

Replaced threading with dedicated channels per project. Converted to installable plugin.

**What changed:**
- `slack-sessions.json` removed — no state file needed
- Channel routing via `conversations.list`: directory name → Slack channel name
- `SLACK_CHANNEL_ID` demoted to optional fallback (not required)
- Plugin manifest (`.claude-plugin/`) + `hooks.json` replace manual `settings.json` edits
- `ping_user` MCP server added: Claude-initiated round-trip (post question → poll for reply)
- `SessionStart` hook injects `docs/conventions.md` to teach Claude about `ping_user`
- `/slack:setup` slash command guides token and channel configuration

**Why channel-per-project over threading:** Simpler Slack UX — each project's messages stay in its own channel rather than as threads in a shared channel. Also eliminates the state file.

**Why MCP tool over daemon + hook injection:** Research (`docs/round-trip-research.md`) found no stable IPC for injecting into a running session. The `UserPromptSubmit` + `additionalContext` hook approach works but requires a persistent daemon and has documented reliability issues. The MCP pattern (Claude explicitly calls `ping_user`) is simpler, stateless, and ships without a background process.

See `docs/prd.md` for the current architecture.
