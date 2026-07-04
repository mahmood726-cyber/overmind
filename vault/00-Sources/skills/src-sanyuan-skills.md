# sanyuan0704/sanyuan-skills — production skills + meta-tooling

**URL:** https://github.com/sanyuan0704/sanyuan-skills  (MIT, ~3.7k★)
**What:** 6 production-grade Claude Code skills, incl. the meta-tooling to author + audit our own skills.

## VERIFIED (fetched repo) — skill → our use
- **Code Review Expert** (SOLID / security / perf / error-handling) → another impl of the different-vendor
  / checker gate.
- **Skill Forge** (meta-skill, "12 battle-tested techniques") → **AUTHOR** our lane skills well (write-once).
- **Skill Review** (audit structure / description / token-efficiency / anti-patterns) → **AUDIT** those
  skills (token-efficiency matters — skills kept SHORT, bloat paid every beat).
- **Wiki Ingest** (compile notes → cross-referenced wiki KB) → auto-compile methods + RapidMeta knowledge
  into the vault.
- **Sigma / Book Study** (learning) → not lane-relevant.

## Security caveat
Third-party skills run instructions in the agent — **audit contents before install**, don't trust-on-faith
(matches Sentinel plugin-loader / arbitrary-code-at-push warning). Skill Review helps, but human read first.

## Ties to
Step 4.6 vault (Wiki Ingest) · [[src-mattpocock-skills]] · [[src-memclaw]].
