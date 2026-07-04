# Caura MemClaw — governed shared memory (machine layer)

**URL:** https://github.com/caura-ai/caura-memclaw · https://memclaw.net/  (Apache-2.0)
**What:** MCP-native governed shared memory for agent fleets — the concrete tool for our missing
shared-signal store. The **machine-readable** memory layer (this vault is the human layer).

## VERIFIED (fetched repo README)
- MCP-native (`/mcp`); visibility scopes (`scope_agent` private / `scope_team` fleet-wide, stamped at
  write); 4 trust tiers; keystone policies; **full audit log** (every write/delete/transition); tenant
  isolation (row-level); **contradiction detection** (auto-supersede); auto knowledge graph (entity
  resolution); self-improving retrieval. Deploy: Docker Compose or Python+PostgreSQL.

## VERIFIED-AS-CLAIM (README states; not independently measured by me)
- eToro (NASDAQ: ETOR): 300+ agents, 26,500+ memories, 1,372 shared skills, 23 ms p50 search.

## Adoption (no-regression) — shadow-first, file state = FLOOR
1. Mirror `STUCK_FAILURES.jsonl` / `.progress_<date>.json` / `circuit_states.json` INTO MemClaw
   additively — files stay source of truth.
2. Evaluate recall + contradiction-detection vs mirrored ground truth (read-only consumers).
3. Promote a signal class to source-of-truth only if it earns it; keep file mirror as audit floor.

## Risks (truth-first)
New service to run (note **pc2 socket-buffer fragility** — validate large-payload reads); governance/config
overhead; added dependency. Contradiction-detection ties to [[src-lfd]] (surface correlated-loop conflicts).

## Ties to
Step 4.6 vault (human mirror) · Wiki-Ingest in [[src-sanyuan-skills]] · [[src-claude-code-docs]] (MCP wiring).
