# Slack Fork Pizza — Conventions

These conventions are injected into every Claude session via the plugin's SessionStart hook.

## ping_user Tool

When you need human input, clarification, or approval during a task, use the `ping_user` MCP tool instead of stopping and waiting for the next prompt.

**Use ping_user when:**
- A task requirement is ambiguous and you cannot proceed without clarification
- You need approval before taking a potentially irreversible action
- You encounter a blocker that only the human can resolve

**Do not use ping_user for:**
- Routine status updates (those go to Slack via the Stop hook automatically)
- Reporting task completion (just finish the task)
- Confirming actions you are already authorized to take

**Keep questions concise and actionable** — one clear question per ping_user call. If you have multiple questions, prioritize the most blocking one.

**If ping_user times out:** Fall back to stopping and waiting for the next prompt. Do not retry in a loop.
