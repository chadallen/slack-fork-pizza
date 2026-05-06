# Round-Trip Feasibility Research

**Task:** slack-fork-pizza-uc7.2  
**Goal:** Can a Slack reply inject a prompt into a running or resumable Claude Code session?

---

## 1. Claude CLI Flags (confirmed via `claude --help`)

Relevant flags:

| Flag | Behavior |
|---|---|
| `-p / --print` | Non-interactive: read stdin prompt, print response, exit |
| `-c / --continue` | Resume most recent session in cwd (interactive) |
| `-r / --resume [id]` | Resume session by ID or interactive picker |
| `--session-id <uuid>` | Force a specific session UUID |
| `--input-format stream-json` | Accept streaming JSON on stdin (works with `-p`) |
| `--output-format stream-json` | Emit streaming JSON on stdout |
| `--fork-session` | Create new session ID when resuming instead of reusing |

No man page exists. No dedicated "inject into running session" flag exists.

**Key limitation (Issue #3976):** `--resume` combined with `-p` (non-interactive) is confirmed broken as of early 2026. Resuming a non-interactive session spawns a new context rather than continuing the existing conversation. Workaround is direct JSONL manipulation — fragile and unsupported.

---

## 2. Session / IPC Mechanisms

What Claude Code actually exposes:

- **Session JSONL transcripts:** `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` — append-only conversation log. Writable but not monitored for live injection.
- **IDE lock files:** `~/.claude/ide/<pid>.lock` — JSON with `pid`, workspace folder, `transport: "ws"`, and an `authToken`. These describe a local WebSocket server Claude exposes for IDE integrations (VS Code extension).
- **Temp session dir:** `/tmp/claude-<uid>/<encoded-cwd>/<session-id>/tasks/` — symlinks to subagent output JSONL files. Read-only for external processes.
- **No Unix domain sockets** found that accept arbitrary prompt input.
- **Remote Control:** Registers the local session with Anthropic's relay API and polls for incoming messages. Requires the Desktop app on the receiving side; no documented programmatic API to send messages to a remote-control session from a script. Cannot be enabled programmatically at session start (Issue #39347 as of Feb 2026).

**Bottom line:** There is no stable, documented IPC mechanism for injecting a prompt into a running interactive session from an external process.

---

## 3. Hook-Based Injection

Hooks fire as subprocess calls and communicate with Claude via:

| Hook type | Receives (stdin) | Can return |
|---|---|---|
| `UserPromptSubmit` | JSON event with `prompt`, `session_id`, `cwd` | `additionalContext` string injected into context window (via `hookSpecificOutput.additionalContext` in stdout JSON, exit 0) |
| `Notification` / `Stop` | JSON event with session info, last message | Exit code only (0 = allow, non-zero = block) |
| `PreToolUse` / `PostToolUse` | JSON with tool name and input/output | `decision: block` or stdout context |

**`UserPromptSubmit` + `additionalContext`** is the one hook that can inject text into the conversation:

```json
{
  "hookSpecificOutput": {
    "additionalContext": "Slack reply from user: 'please also update the README'"
  }
}
```

Claude receives this as a system reminder inserted before it processes the user's turn.

**Caveats:**
- Hook fires *per prompt* — not on demand. Injection only works when the user is already submitting a new prompt.
- Issue #13912: stdout from `UserPromptSubmit` hooks sometimes causes errors despite docs saying it's added to context. Plain text stdout (not JSON) can work as a fallback.
- Issue #17804: Injecting JSON-structured content can trigger Claude's prompt-injection defenses and surface the text to the user instead of silently adding context.
- Context injection is capped at 10,000 characters.

**Verdict:** `UserPromptSubmit` + `additionalContext` is viable for *augmenting* a new user turn with pending Slack replies — not for injecting mid-session without user action.

---

## 4. OSS Survey

### Existing projects (confirmed on GitHub, May 2026)

| Project | Approach | What it does | Gap |
|---|---|---|---|
| **tomeraitz/claude-slack-bridge** | MCP server + Unix domain socket daemon | Claude pauses mid-task, asks human via Slack, resumes on reply | Requires MCP tool call from Claude side — Claude must initiate the ask |
| **jeremylongshore/claude-code-slack-channel** | Socket Mode + MCP stdio, TypeScript | Two-way Slack bridge; per-thread session isolation; prompt-injection defense; Block Kit permission relay | Complex, TypeScript/Bun/Docker, security-focused |
| **mpociot/claude-code-slack-bot** | Slack mention → new `claude -p` subprocess | Mention bot in Slack, spawns fresh Claude Code process per message | No session continuity — each message is a new session |
| **dbenn8/claude-slack** | Socket Mode + session tracking JSON | Bidirectional; multi-session support | Unclear if it resumes vs. spawns new |
| **retrodigio/claude-channel-slack** | Socket Mode plugin | Inherits full tool/skill/MCP context from parent session | Requires plugin install, not standalone |
| **JessyTsui/Claude-Code-Remote** | Email/Discord/Telegram → local Claude Code | Receives replies via messaging platform, feeds new `claude -p` turns | Not Slack; same spawn-new-process model |

### Key pattern across all OSS projects

None inject into a *running* interactive session. All bridge via one of:

1. **MCP tool** (Claude pauses and polls a socket — Claude must initiate)
2. **Spawn new `-p` process per reply** (no conversation continuity beyond what `-c`/`--resume` provides, and `--resume -p` is broken)
3. **Session file manipulation** (JSONL append + restart — fragile)

### Anthropic's own Slack integration (Dec 2025)

Claude Code in Slack (Teams/Enterprise) routes tasks to Claude Code on the *web*, not the local CLI. Not relevant for local-session injection.

---

## 5. Reusable Components

Regardless of approach, these are useful:

- **`slack_sdk` (Python, official):** Socket Mode client (`slack_sdk.socket_mode.SocketModeClient`) — handles WebSocket reconnect, event ACKs, no public URL needed.
- **`slack_bolt` (Python):** Higher-level framework over `slack_sdk`; handles OAuth, event routing, `app_mention` / `message` handlers cleanly.
- **File-based inbox pattern:** Write pending Slack replies to `~/.claude/slack-inbox/<session_id>.json`; hook script reads and returns them as `additionalContext`. Zero IPC complexity.
- **`asyncio` + `threading`:** Socket Mode client runs in a background thread; hook reads the inbox file synchronously — no async bridge needed.
- **Session ID tracking:** `~/.claude/slack-sessions.json` (already in use in this project) maps `cwd → thread_ts`. Extend to also map `session_id → thread_ts` for inbox routing.

---

## 6. Recommendation

**Feasible approach: file-based inbox + `UserPromptSubmit` hook**

1. Run a persistent **Slack Socket Mode daemon** (`notify-daemon.py` or similar) that:
   - Listens for thread replies on existing session threads
   - On reply: appends the message to `~/.claude/slack-inbox/<session_id>.txt`

2. Extend `UserPromptSubmit` hook to:
   - Read `~/.claude/slack-inbox/<session_id>.txt` if it exists
   - Return `additionalContext` with the pending reply
   - Delete the inbox file after reading

3. Claude sees the Slack reply as context at the start of its next turn.

**Limitations of this approach:**
- Requires the user to submit a new prompt to Claude — the Slack reply is prepended to that turn, not injected autonomously.
- If the user never prompts again after the Slack reply, the context is never consumed (though it persists for the next turn).
- `UserPromptSubmit` hook reliability issues (Issues #13912, #17804) require careful output formatting.

**Not feasible (currently):**
- Injecting into a *running* session mid-turn — no IPC mechanism exists.
- Resuming a session non-interactively and reliably — `--resume -p` is broken (Issue #3976).
- Remote Control programmatic API — no public endpoint; Desktop-app only.

**Alternative:** Use the MCP tool pattern (like `claude-slack-bridge`) where Claude explicitly calls an `AskHuman` tool that blocks on a Slack reply. This gives true round-trip control but requires Claude to initiate — not transparent to the user. Worth considering for uc7.3 if the hook approach proves too unreliable.
