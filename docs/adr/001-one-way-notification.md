# ADR-001: One-way Slack notification as the primary interaction pattern

**Status:** Accepted
**Date:** 2026-05-07

## Context

Running multiple Claude Code sessions across projects means watching multiple terminals.
We needed a way to know when a session finishes a turn and what it did — without switching
to the right terminal at the right time.

Three approaches were evaluated over the course of the project:

1. **Shared channel with threading (v1):** One Slack channel, one thread per project
   directory. Required a `slack-sessions.json` state file mapping `cwd → thread_ts`.
2. **Full round-trip (Slack → CLI):** A persistent daemon listens for Slack messages and
   injects them into the running Claude Code session. Research
   (`docs/round-trip-research.md`) found no stable IPC mechanism for this — the
   `UserPromptSubmit` + `additionalContext` hook approach requires a daemon and has
   reliability issues.
3. **One-way notification to per-project channels:** The `Stop` hook posts the agent's last
   assistant message to a Slack channel matching the project directory name. No threading,
   no state file, no daemon.

## Decision

Use one-way notification (option 3) as the primary pattern.

- The `Stop` hook fires `notify.py`, which posts the last assistant message to `#<project-name>`.
- Channel lookup via `conversations.list`, falling back to `SLACK_CHANNEL_ID`.
- An optional `ping_user` MCP tool exists for Claude-initiated round-trips (post a question,
  poll for a threaded reply). This is secondary — it works but requires Claude to explicitly
  call it, and the polling model has a 5-minute timeout.

## Consequences

**Benefits:**
- Zero state. No session file, no daemon, no background process.
- Each project's messages are naturally scoped to its own channel.
- Works with any number of concurrent sessions across projects.
- Stdlib only — no dependencies beyond Python 3.

**Trade-offs:**
- The user cannot reply to Claude from Slack (unless Claude calls `ping_user` first).
- If a session needs input, the user must switch to the terminal to provide it.
- Slack channels must be created manually and match directory names.

**Supersedes:**
- v1 threading model (`slack-sessions.json`, single shared channel)
- Full round-trip daemon approach (researched, not built)
