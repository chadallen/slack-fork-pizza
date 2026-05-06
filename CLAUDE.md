# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Build & Test

```bash
# Manual end-to-end test
echo '{"hook_event_name":"Stop","cwd":"/Users/chadallen/projects/slack-fork-pizza"}' | \
  SLACK_BOT_TOKEN=<token> SLACK_CHANNEL_ID=<channel> python3 notify.py

# Events post to the channel matching the project directory name (e.g. #slack-fork-pizza)
# Falls back to SLACK_CHANNEL_ID if no matching channel exists
```

## Architecture Overview

Single-file Python script (`notify.py`) invoked by Claude Code hooks. On `Stop` events, posts "Agent stopped" + last assistant message to Slack. On `Notification` events, posts the notification message. Each event is a standalone message posted to the Slack channel whose name matches `Path(cwd).name`. Falls back to `SLACK_CHANNEL_ID` if no matching channel is found. Channel name→ID lookup is cached in a module-level dict. Stdlib only — no pip dependencies.

Hooks configured in `~/.claude/settings.json`:
- `Notification` and `Stop` → `python3 /Users/chadallen/projects/slack-fork-pizza/notify.py`
- Env vars: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`
- Required Slack scopes: `chat:write`, `channels:read`

## Conventions & Patterns

- Always exit 0 — a non-zero exit blocks Claude Code
- Wrap all logic in try/except in `main()` to guarantee exit 0
- Stdlib only — no third-party packages
