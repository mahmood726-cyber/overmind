# Candidate Tools — Weekend Repos

Ten open-source repos Mahmood shared (2026-07-04, URLs truncated → **each resolved by web search to its
real repo**, not guessed). For each: real URL · what-it-is · license · stars · relevance to the
cluster-harness / agent-orchestration / evidence-synthesis work · security note. **All of these run code
in/around the agent — audit before adopting.**

> **⚠ Star-count honesty:** star numbers are as reported by search/GitHub-page fetch on 2026-07-04.
> Two look **implausibly high** (Hermes "209k", Paperclip "71k") — flagged inline as *unverified / possible
> star inflation*. Treat all counts as approximate.

## Ranked shortlist (worth a real look this weekend)
| # | Repo | Relevance | Why |
|---|---|---|---|
| **1** | **ComposioHQ/agent-orchestrator** | **HIGH** | Closest thing to our cluster-harness: parallel coding-agent fleet, worktree-per-agent, autonomous CI-fix/review, 23+ agents incl. Claude Code + Codex. |
| **2** | **Yeachan-Heo/oh-my-claudecode** | **HIGH** | Claude-Code-native multi-agent orchestration (modes/skills/lanes) — direct pattern source for our lanes; large community. |
| **3** | **NousResearch/hermes-agent** | **MED-HIGH** | Self-improving skill loop + searches its own past trajectories — literally the [[src-automem]] / harness-evolution thesis in a shipped agent. |
| 4 | Gitlawb/openclaude | MED-HIGH | Multi-backend coding-agent harness (Codex/Gemini/Ollama/OpenAI-compat) — cross-vendor substrate study. |
| 5 | paperclipai/paperclip | MED | Agent-team governance (org charts / delegation / audit) — governance ideas, but "run a company" oriented. |

**Study the PATTERNS, don't wholesale-adopt** — each is a full alternate harness / surface; borrowing a
mechanism (worktree isolation, mode routing, self-eval loop) is lower-risk than swapping our substrate.

## 🚫 AVOID
- **elder-plinius/ST3GG** — see below. Jailbreak/adversarial-adjacent tooling; **do not adopt into a
  truth-first research harness.**

---

## Full catalog

### 1. Clawless — `open-gitagent/clawless`
- **URL:** https://github.com/open-gitagent/clawless
- **What:** serverless **browser-based runtime** for "Claw AI Agents" via WebContainers (a full Node.js
  runtime in-browser, WASM); built-in editor, terminal, **policy engine, and audit logging**; state in
  `localStorage`.
- **License:** not confirmed in this pass (verify on repo). **Stars:** not verified.
- **Relevance: LOW–MED.** It's a sandboxed *browser* runtime, not a fleet orchestrator. The **policy engine
  + audit logging** are the only ideas that touch our truth-first/audit theme; the WASM-in-browser
  substrate is not ours.
- **Security:** runs arbitrary npm (3.4M packages) in a browser sandbox; `localStorage` persistence. Audit
  the policy-engine + what the sandbox can reach before trusting it.

### 2. Paperclip — `paperclipai/paperclip`
- **URL:** https://github.com/paperclipai/paperclip
- **What:** open-source app to **manage a team of AI agents** (org charts, ticketing, delegation,
  governance); Node + React, embedded Postgres.
- **License:** MIT (search-reported). **Stars:** *"~71k" reported — implausibly high, treat as unverified /
  possible inflation.*
- **Relevance: MED.** Governance/delegation layer over an agent team maps loosely to our orchestration, but
  it's oriented at "run a company," not evidence-synthesis. Governance/audit patterns are the takeaway.
- **Security:** web app + embedded DB; standard surface. Audit auth + what agents are permitted to do.

### 3. TimesFM — `google-research/timesfm`
- **URL:** https://github.com/google-research/timesfm
- **What:** pretrained **decoder-only time-series foundation model** (Google Research, ICML 2024);
  zero-shot forecasting with uncertainty.
- **License:** Apache-2.0 (typical for google-research; not re-verified this pass). **Stars:** large, not
  verified.
- **Relevance: LOW / mostly None.** Only relevant **if we do time-series forecasting** — **tangential to
  meta-analysis / evidence synthesis** (our estimands are pooled effects, not forecasts). Might matter for a
  future clinic-monitoring time-series lane, not the methods work.
- **Security:** model weights + Python from a reputable org; low risk.

### 4. Lark CLI — `larksuite/cli`
- **URL:** https://github.com/larksuite/cli
- **What:** official **Lark/Feishu CLI** (Messenger/Docs/Base/Sheets/Calendar/Mail/Tasks), 200+ commands,
  20+ AI-Agent skills; built for humans and agents. (Token-efficient alt: `yjwong/lark-cli`.)
- **License:** not confirmed this pass. **Stars:** not verified.
- **Relevance: LOW / None** unless we use Lark/Feishu as a workspace. A connectors/act-not-suggest example,
  but not our stack.
- **Security:** official vendor CLI; it authenticates to a Lark tenant — audit scopes before granting.

### 5. ST3GG — `elder-plinius/ST3GG`  🚫 **AVOID**
- **URL:** https://github.com/elder-plinius/ST3GG
- **What:** "all-in-one **steganography** suite" — 100+ data-smuggling/encoding techniques across
  images/audio/text/docs/packets, plus detection functions; ships an **MCP server for AI agents.**
- **License:** AGPL-3.0. **Author:** **elder-plinius (Pliny)** — well known for **LLM jailbreak / red-team**
  tooling (same account: `CL4R1T4S` leaked system prompts, `OBLITERATUS`, Parseltongue).
- **Relevance: NONE (adversarial).** Data-smuggling / obfuscation is the **opposite** of a truth-first,
  auditable research harness.
- **Security:** 🚫 **Explicitly flagged AVOID.** Likely **jailbreak/adversarial tooling**; an MCP server
  from this author would run inside the agent. Do **not** install into the harness. Catalogued here only so
  it's clearly marked as off-limits.

### 6. OpenClaude — `Gitlawb/openclaude`
- **URL:** https://github.com/Gitlawb/openclaude
- **What:** open-source **coding-agent CLI harness** — "runs anywhere, uses anything": OpenAI-compatible /
  Gemini / GitHub Models / Codex-OAuth / Ollama backends; one terminal workflow (prompts, tools, agents,
  MCP, slash commands, streaming). VS Code extension. **Not affiliated with Anthropic.**
- **License:** MIT. **Stars:** ~29.8k. **Language:** TypeScript (99%).
- **Relevance: MED-HIGH.** A **multi-vendor coding-agent substrate** — direct study for our cross-vendor /
  harness-substrate work ([[Cross-Vendor-Witness-SOP]], [[src-claude-code-docs]] analog). Pattern source,
  not a substrate swap.
- **Security:** community project (not Anthropic) that runs code + wires many model backends; audit backend
  auth handling and tool permissions before use.

### 7. Agent Orchestrator — `ComposioHQ/agent-orchestrator`  ⭐ top pick
- **URL:** https://github.com/ComposioHQ/agent-orchestrator
- **What:** **agentic orchestrator for parallel coding agents** — a long-running **Go daemon** that plans
  tasks, spawns agents (each own git **worktree/branch/PR**), and autonomously handles **CI fixes, merge
  conflicts, code reviews**; works with **23+ CLI agents** (Claude Code, Codex, Cursor, Aider, …).
- **License:** Apache-2.0. **Stars:** ~8k. **Language:** Go (68%).
- **Relevance: HIGH.** The **closest external analog to our cluster-harness** + maker/checker: capability
  routing, worktree isolation (our `isolation:'worktree'` pattern), autonomous review loop. Maps to
  [[Gated-Additive-Deploy-SOP]] / cluster dispatch. *(Note: a fork `AgentWrapper/agent-orchestrator` also
  exists — canonical is ComposioHQ.)*
- **Security:** a daemon that spawns agents which **push branches / open PRs** — real write surface. Audit
  its git-auth + the truth-gate equivalent (does it block force-push / `--no-verify`?) before pointing it
  at real repos.

### 8. MiroFish — `666ghj/MiroFish`
- **URL:** https://github.com/666ghj/MiroFish
- **What:** **multi-agent "swarm-intelligence" prediction engine** — builds a simulated digital world of
  thousands of persona-agents to "predict anything" (news/policy/financial); topped GitHub Trending Mar
  2026.
- **License:** not confirmed this pass. **Stars:** high (trending), not verified.
- **Relevance: LOW.** Prediction/simulation via agent swarms — **tangential** to code-orchestration and to
  evidence-synthesis (it *generates* scenarios; we *verify* facts). Interesting multi-agent design, not a
  fit for a truth-first methods harness.
- **Security:** runs many autonomous agents; audit what data it ingests / emits before any use.

### 9. Hermes Agent — `NousResearch/hermes-agent`  ⭐ on-theme
- **URL:** https://github.com/NousResearch/hermes-agent
- **What:** **autonomous agent with a built-in learning loop** — creates skills from experience, improves
  them in use, **searches its own past conversations** for context, builds a user model across sessions;
  multi-platform messaging gateway. Sibling: `hermes-agent-self-evolution` (DSPy + GEPA).
- **License:** MIT. **Stars:** *"209k" reported — implausible, treat as unverified / possible inflation.*
  **Language:** Python (82%).
- **Relevance: MED-HIGH.** The **self-improving skill loop + own-trajectory recall** is a shipped instance
  of the [[src-automem]] / [[src-evolve-the-harness|harness-evolution]] thesis — a concrete study for our
  memory + evolve-the-harness themes.
- **Security:** MIT, runs code + connects messaging gateways (Telegram/Discord/Slack/…). `curl | bash`
  install is a red flag — read the installer; audit skill-creation (it writes + runs its own skills).

### 10. Oh-my-claudecode — `Yeachan-Heo/oh-my-claudecode`  ⭐ top pick
- **URL:** https://github.com/Yeachan-Heo/oh-my-claudecode
- **What:** **teams-first multi-agent orchestration for Claude Code** — ~19–32 specialized agents + ~31–39
  skills, 5 execution modes (Autopilot / Ultrapilot / Swarm / Pipeline / Ecomode). Plugin-marketplace
  install.
- **License:** MIT. **Stars:** ~37.4k. **Language:** TypeScript (58%). *(npm package name differs:
  `oh-my-claude-sisyphus` — mild supply-chain smell, verify before install.)*
- **Relevance: HIGH.** Directly a **Claude-Code orchestration layer** — pattern source for our lanes
  (swarm/pipeline modes ≈ our parallel/pipeline dispatch), skills library to mine ([[src-mattpocock-skills]]
  / [[src-sanyuan-skills]] neighbours).
- **Security:** **third-party CC plugin — runs instructions inside the agent.** Audit every SKILL.md/agent
  before install (same rule as mattpocock/sanyuan); the package-name mismatch means double-check you're
  installing the real thing.

---

## Cross-cutting security rule
Every repo here **executes in or around the agent** (CLIs, MCP servers, CC plugins, daemons that push
code). **Audit contents before adopting** — read installers, skill files, and permission scopes; prefer
borrowing a *mechanism* over installing a whole alternate harness. Hard AVOID: **ST3GG**.

## Ties to
[[tool-ragas]] · [[reference-library]] · [[Gated-Additive-Deploy-SOP]] (worktree isolation / truth-gate) ·
[[src-mattpocock-skills]] · [[src-sanyuan-skills]] (audit-before-install) · [[Home]].
