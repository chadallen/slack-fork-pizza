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

## Slack Recap (Stop Hook)

When you finish a turn, your last message is automatically posted to Slack via the Stop hook. To keep the notification useful and concise, end every turn with a short recap block using this exact format:

```
[SLACK_RECAP]
<1-3 line recap: what you did, outcome, whether user needs to act>
[/SLACK_RECAP]
```

**The recap should answer:**
- What did I do?
- Did it succeed?
- Does the user need to act?

**Guidelines:**
- Keep it to 1-3 lines, no markdown formatting (Slack receives plain text)
- If the turn is just a quick answer or clarification, one line is fine
- Do not include code blocks, bullet points, or headers inside the recap block
- Write in past tense, first person (e.g., "Implemented X. Tests pass. No action needed.")

**Example:**
```
[SLACK_RECAP]
Refactored the channel lookup logic and added error handling. All tests pass. No action needed.
[/SLACK_RECAP]
```

If you omit the block, the Stop hook will fall back to truncating your last message — which may be noisy or lack context.
