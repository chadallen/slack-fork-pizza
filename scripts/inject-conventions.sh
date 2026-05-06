#!/usr/bin/env bash
# Slack Fork Pizza — SessionStart hook
# Injects plugin conventions into Claude context each session.
# Always exits 0 to avoid blocking the session.

CONVENTIONS="${CLAUDE_PLUGIN_ROOT}/docs/conventions.md"

if [ -f "$CONVENTIONS" ]; then
  cat "$CONVENTIONS"
fi

exit 0
