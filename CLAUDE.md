# Project Instructions for AI Agents

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

Enable the plugin via directory marketplace source in `extraKnownMarketplaces` pointing to
`.claude-plugin/marketplace.json`, then install from the Claude Code marketplace UI.

```bash
# Manual end-to-end test (posts to channel matching cwd name, falls back to SLACK_CHANNEL_ID)
echo '{"hook_event_name":"Stop","cwd":"/Users/chadallen/projects/slack-fork-pizza"}' | \
  SLACK_BOT_TOKEN=<token> python3 notify.py
```

## Architecture Overview

Claude Code plugin that auto-registers hooks (`Notification`, `Stop`, `SessionStart`) and an
MCP server (`ask-human`) on install. Key files:

- `notify.py` — `Notification`/`Stop` handler; posts to Slack
- `slack_channel.py` — shared channel lookup (name → ID via `conversations.list`)
- `scripts/inject-conventions.sh` — `SessionStart` hook; injects `docs/conventions.md`
- `commands/setup.md` — `/slack:setup` slash command

Each project routes to a Slack channel matching its directory name; falls back to
`SLACK_CHANNEL_ID`.

## Conventions & Patterns

- Always exit 0 — a non-zero exit blocks Claude Code
- Wrap all logic in try/except in `main()` to guarantee exit 0
- Stdlib only — no third-party packages
- Channel lookup lives in `slack_channel.py` — import it, don't duplicate
