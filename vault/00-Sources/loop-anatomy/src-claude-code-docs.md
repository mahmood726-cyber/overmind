# Claude Code docs — the real build substrate

**URL:** https://code.claude.com/docs
**What:** the actual toolbox every mechanism in the plan is built from. All facts below VERIFIED by
fetching the pages 2026-07-04.

## Subagents (`.claude/agents/*.md`) — https://code.claude.com/docs/en/sub-agents
Frontmatter: `name, description, tools, disallowedTools, model, effort, permissionMode, mcpServers,
hooks, maxTurns, skills, isolation, color`. Per-subagent `model` for cost routing ("cheaper models like
Haiku"). → maker/checker split; the TRINITY cheap-router.

## Hooks — https://code.claude.com/docs/en/hooks
31 lifecycle events. Blocking: `PreToolUse`, `Stop`, `SubagentStop`, `PostToolBatch`, `UserPromptSubmit`.
Handler types: command / http / mcp_tool / prompt / agent. Docs give an exact `npm test` test-suite
blocker (`PostToolBatch`/`Stop`, `decision:"block"`). `SessionStart`/`UserPromptSubmit` inject
`additionalContext`. → objective gate (T12a), anti-drift reread (T12e), different-vendor check (T-CV).

## Headless — https://code.claude.com/docs/en/headless
`claude -p`; `--output-format json` returns **`total_cost_usd` + per-model cost breakdown** (= cost-per-
accepted, T12b); `--json-schema`, `--allowedTools`, `--permission-mode dontAsk/acceptEdits`, `--bare`,
`--continue/--resume`, `--model`, `--mcp-config`, `--agents`. Pipe: `git diff main | claude -p "..."`.

## Skills / commands — https://code.claude.com/docs/en/skills
`.claude/skills/<name>/SKILL.md` or `.claude/commands/<name>.md` → `/name`. Frontmatter `allowed-tools,
disallowed-tools, argument-hint, disable-model-invocation, context: fork, agent`.

## Commands — https://code.claude.com/docs/en/commands  (+ /goal: /en/goal)
Verified real: **`/loop [interval] [prompt]`** (self-paces if omitted; `.claude/loop.md`), **`/goal
[condition]`** (works until condition met), **`/schedule`** (cloud routines), **`/compact`**, **`/effort
[low|medium|high|xhigh|max]`**. *Flag:* "/goal runs a separate fast grader model" is practitioner framing,
not doc-confirmed.

## MCP — https://code.claude.com/docs/en/mcp
`.mcp.json` / `claude mcp add` (scopes local/project/user); read-AND-act connectors; `mcp__server__tool`
naming; callable from hooks (`type:"mcp_tool"`) and headless (`--mcp-config`). → MemClaw wiring.

## Ties to
[[src-memclaw]] · [[src-ai-edge-loop-guide]] · [[swipe-file]].
