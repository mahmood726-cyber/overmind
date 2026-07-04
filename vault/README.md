# Overmind Vault — knowledge base

An **Obsidian-compatible markdown vault**: the human-readable knowledge layer that consolidates the
**2026-07-04** session output. Plain local `.md` files with `[[wiki-links]]` — no database, no infra. It
complements **MemClaw** (the governed *machine* memory, [[src-memclaw]]) and **Wiki-Ingest** (auto-compile,
[[src-sanyuan-skills]]); this is the layer humans curate.

## How to open it
- **Obsidian:** *Open folder as vault* → select `F:\overmind\vault\`. `[[wiki-links]]` and the graph view
  work out of the box. (Links resolve by note **basename**, so the folder layout is free to change.)
- **Any markdown reader / editor:** every file is plain CommonMark; open `Home.md` and follow the links.
- **Terminal / grep / git:** it is diff-able, greppable, offline, and git-versioned — the same properties
  that make our `PROGRESS.md` convention work.

## Start here
- **[[Home]]** — the top map of content (four pillars + the through-line). **Read this first.**
- [[_Sources-MOC]] · [[_Verification-MOC]] · [[_SOPs-MOC]] · [[Decisions-Log-2026-07-04]] — the four
  section indexes.
- [[reference-library]] — every cited URL · [[swipe-file]] — reusable `/loop` specs + templates ·
  [[_index]] — the sources through-line.

## Structure
```
vault/
├─ Home.md                     ← top MOC (start here)
├─ README.md                   ← this file
├─ _index.md                   ← sources through-line (sub-index)
├─ reference-library.md        ← all cited URLs
├─ swipe-file.md               ← reusable /loop specs, loss template
├─ 00-Sources/                 ← external material reviewed today (by theme)
│  ├─ harness-evolution/  loop-anatomy/  benchmarking/  skills/  memory/
│  └─ _Sources-MOC.md
├─ 01-Verification/            ← cross-vendor QA summaries (→ F:\ubcma\verification\)
│  └─ _Verification-MOC.md
├─ 02-SOPs/                    ← reusable, versioned workflows
│  └─ _SOPs-MOC.md
└─ 03-Decisions/              ← key decisions (with truth-first provenance tags)
   └─ Decisions-Log-2026-07-04.md
```

## Conventions
- **Truth-first:** each note separates **VERIFIED** (path cited) from **REPORTED / UNVERIFIED** (flagged).
  Uncertain items stay marked — see the [[Decisions-Log-2026-07-04|decisions log]] for a worked example
  (clinic items flagged not-found-on-disk).
- **Versioned SOPs:** each SOP carries a `Version:` header so we can audit what worked (vault workflow #2).
- **Keep local paths out of anything pushed** beyond these internal notes; the vault is a local artifact,
  not a public deliverable.

Seeded 2026-07-04 from the workflow-upgrade session; expanded into the four-pillar structure the same day.
Git-tracked on branch `vault/knowledge-base-2026-07-04`.
