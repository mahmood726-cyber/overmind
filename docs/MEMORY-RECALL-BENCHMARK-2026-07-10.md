# Memory-Recall Benchmark — 2026-07-10

**Closes GAP #2** of [`F:\overmind\docs\PEER-BENCHMARK-2026-07-10.md`](file:///F:/overmind/docs/PEER-BENCHMARK-2026-07-10.md)
("Mem0 / Letta / Zep publish LoCoMo/LongMemEval recall; **we've never benchmarked memory**").
Measurement only. No memory/harness behaviour changed. Adapter + eval live on branch
`mem-recall-benchmark-2026-07-10` (frozen repos untouched). Metric is honest, `n` is honest,
no hand-tuning.

---

## Headline

Our shipped memory retriever (`MemoryStore`), measured as **retrieval recall@k** on the two
public sets the peers use, with its **semantic (dense-embedding) path enabled**:

| Set | Unit | n | **R@1** | **R@5** | **R@10** |
|---|---|---:|---:|---:|---:|
| **LongMemEval_s** | session | 500 (full) | 74.6% | **91.4%** | **96.4%** |
| **LoCoMo** | turn | 1982 (full) | 15.7% | 36.5% | **45.8%** |

**As shipped on a box with no embedding backend installed** (FTS5 keyword only — the state this
machine was actually in before this exercise), recall collapses:

| Set | Unit | n | R@1 | R@5 | R@10 |
|---|---|---:|---:|---:|---:|
| LongMemEval_s | session | 500 | 8.8% | 8.8% | 8.8% |
| LoCoMo | turn | 1982 | 0.15% | 0.15% | 0.15% |

**One-line honest read:** *On session-level retrieval (LongMemEval) our plain MiniLM dense path
reaches 96.4% R@10 — competitive at the retrieval layer. On the harder turn-level task (LoCoMo)
it reaches 45.8% R@10 — about half of the best published LoCoMo retriever (MemPalace 88.9% R@10),
because we retrieve raw conversation turns with an off-the-shelf 384-dim embedder and no
LLM-based memory extraction, reranking, or graph. And the keyword-only path we actually shipped
by default is effectively non-functional for natural-language questions (~0–9%).*

---

## 1. Where the code is (Finding: real retrieval exists — it is not just static markdown)

The agent-memory system has **two layers**, and the retrieval layer is real code, not a pile of
markdown files:

| Component | Path | Retrieval given a query? |
|---|---|---|
| `MemoryStore.search` / `hybrid_search` / `recall_*` | `overmind/memory/store.py` | Yes — FTS5 + semantic + temporal filter |
| `StateDatabase.search_memories` (FTS5 `MATCH`) | `overmind/storage/db.py:308` | Yes — keyword, AND-of-tokens |
| `StateDatabase.semantic_search_memories` (cosine) | `overmind/storage/db.py:335` | Yes — vector similarity |
| `embeddings.embed` (all-MiniLM-L6-v2, 384-dim) | `overmind/memory/embeddings.py` | backend for semantic |
| `MemoryExtractor.extract` (populates `embedding=` on save) | `overmind/memory/extractor.py:137` | write side |
| BM25 markdown recall (`bm25_recall`/`cmd_recall`) | `overmind/memory/file_index.py` | Yes — over `~/.claude/memory` facts |

The SQLite layer (`overmind.db`, table `memories` + FTS5 `memories_fts`) is the primary agent
memory. The markdown file-memory is a **second, separate** BM25 index over the human-authored
`~/.claude/memory/*.md` facts. The peer doc's "two layers, unbridged" observation is accurate:
they are independent retrieval paths with no shared index.

**Two facts that shape every number below:**
1. **The semantic layer was wired but dormant.** `MemoryExtractor` *does* populate embeddings on
   save (production is correct), but the backend (`sentence-transformers` + `torch`) was **not
   installed** on this machine, so `embeddings.embed()` returned `None` and every semantic search
   returned `[]`. I installed the declared optional dependency to measure the designed path — that
   enables shipped code, it does not change behaviour. The FTS-only rows above are what the box
   did *before* that install.
2. **The prior internal eval was a saturated fixture.** `evals/memory_recall.py` reports 100%
   recall — on **n=4** hand-authored supersession probes. That measures the temporal-validity
   filter, not retrieval quality, and is exactly the "100% on a saturated fixture" the peer doc
   flags. This benchmark replaces it with public data at real `n`.

---

## 2. Method

**Datasets (public, pulled fresh 2026-07-10):**
- **LoCoMo** — `snap-research/locomo`, `data/locomo10.json` (CC-BY-NC). 10 multi-session
  conversations; 1986 QA items with `evidence` = the dialog-turn ids (`D<session>:<turn>`) that
  contain the answer. Retrieval unit = **one turn**. 4 items have no evidence (adversarial) and
  are excluded from recall (reported as `excluded_no_gold`).
- **LongMemEval_s** — `xiaowu0162/longmemeval` (HuggingFace), file `longmemeval_s` (266 MB, the
  full-haystack retrieval set, ~50 sessions/question incl. distractors). 500 questions;
  `answer_session_ids` = the gold evidence sessions. Retrieval unit = **one session**.

**Metric — retrieval recall@k**, the definition LongMemEval's retrieval eval and MemPalace's
LoCoMo R@k use:

> recall@k = fraction of questions for which **≥1 gold evidence unit is in the top-k retrieved**.

(We also log gold *coverage@k* = mean fraction of gold units retrieved; see the JSON.)

**Harness (read-only, no hand-tuning):** one fresh SQLite-backed `MemoryStore` per
conversation/question (the natural "one memory per user" scope). Each retrieval unit is saved as
a real `MemoryRecord`; each question's **raw text** is the query — we never strip stopwords,
expand, or rewrite it, because the peers feed the raw question to their retriever too and the
point is to measure *ours*. Three shipped retrieval paths are exercised:

| config | calls | note |
|---|---|---|
| `fts` | `store.search()` | FTS5 keyword, AND-of-tokens — as-shipped default with no backend |
| `semantic` | `db.semantic_search_memories()` | pure MiniLM cosine; embeddings populated on ingest exactly as `extractor.py:137` |
| `hybrid` | `store.hybrid_search()` | FTS5 first, semantic fallback when FTS < 3 hits |

Adapter: `evals/public_memory_bench/adapter.py`; runner: `…/run_bench.py`; tests:
`tests/unit/test_public_memory_bench.py` (5 tests, green). Raw result JSON:
`evals/public_memory_bench/results/*.json`.

---

## 3. Full results

**LoCoMo — turn-level, n=1982:**

| config | R@1 | R@3 | R@5 | R@10 |
|---|---:|---:|---:|---:|
| fts (as-shipped, keyword) | 0.15% | 0.15% | 0.15% | 0.15% |
| semantic (MiniLM) | 15.7% | 28.7% | 36.5% | **45.8%** |
| hybrid | 15.8% | 28.8% | 36.6% | 45.8% |

**LongMemEval_s — session-level, n=500:**

| config | R@1 | R@3 | R@5 | R@10 |
|---|---:|---:|---:|---:|
| fts (as-shipped, keyword) | 8.8% | 8.8% | 8.8% | 8.8% |
| semantic (MiniLM) | 74.6% | 87.4% | 91.4% | **96.4%** |
| hybrid (shipped default) | 76.4% | 88.0% | **91.8%** | **96.4%** |

`hybrid` is the store's shipped-default retrieval method and is the best config: it prepends the
(few) exact FTS keyword hits ahead of the dense candidates, nudging a handful of gold sessions
into top-1/3 (R@1 76.4% vs 74.6% semantic) while matching semantic at R@10.

Two structural facts jump out of the raw numbers:
- **FTS recall is flat across k.** `search_memories` quotes every query token and FTS5 **ANDs**
  them, so a natural-language question (`"When did Caroline go to the LGBTQ support group?"`)
  requires *every* token — including stopwords — to co-occur in one short unit. It almost always
  returns **< 1** result, so raising k does nothing. (The same query as keywords, `"LGBTQ support
  group"`, correctly returns the gold turn — the failure is the AND-of-all-tokens query builder,
  not the index.) This is a real, un-tuned property of the shipped keyword path.
- **Semantic recall grows normally with k** and does the real work; `hybrid ≈ semantic` because
  FTS contributes almost nothing on NL queries, so hybrid falls through to the vector path.

**By category (semantic):**

| LoCoMo (turn) | R@5 | R@10 | | LongMemEval (session) | R@5 | R@10 |
|---|---:|---:|---|---|---:|---:|
| temporal | 47.7% | 54.5% | | knowledge-update | 96.2% | 100% |
| single-hop | 42.6% | 52.4% | | multi-session | 94.7% | 99.2% |
| multi-hop | 37.2% | 50.0% | | single-session-assistant | 98.2% | 98.2% |
| open-domain | 30.4% | 39.1% | | temporal-reasoning | 91.7% | 95.5% |
| adversarial | 17.9% | 25.6% | | single-session-preference | 83.3% | 96.7% |
| | | | | single-session-user | 77.1% | 87.1% |

---

## 4. Peer comparison — with the metric caveat stated loudly

**The metrics are not all the same, and conflating them would be the exact overclaim to avoid.**

| System | Set | Number | **Metric** |
|---|---|---:|---|
| **Ours (semantic)** | LongMemEval_s | **96.4% R@10 / 91.4% R@5** | **retrieval recall@k (session)** |
| **Ours (semantic)** | LoCoMo | **45.8% R@10** | **retrieval recall@k (turn)** |
| **MemPalace** | LoCoMo | 88.9% R@10 | **retrieval recall@10** ← *apples-to-apples* |
| Mem0 | LoCoMo | 92.5% | LLM-judged **QA answer accuracy** (not retrieval) |
| Mem0 | LongMemEval | 94.4% | LLM-judged **QA answer accuracy** |
| Zep/Graphiti | LongMemEval | 63.8% | **QA answer accuracy** |
| Mem0 (independent repro) | LoCoMo | 58–66% | QA accuracy (self-report 91.6%→independent 58–66%) |

- **The only true apples-to-apples comparison is MemPalace's 88.9% R@10 on LoCoMo vs our
  45.8%.** Both are turn-level retrieval recall@10. We are at roughly **half** of the best
  published LoCoMo retriever. That is the honest headline gap.
- **On LongMemEval, our 96.4% R@10 is session-level retrieval recall** — competitive at the
  *retrieval layer*. It must **not** be read as beating Zep (63.8%) or matching Mem0 (94.4%):
  those are **end-to-end QA answer accuracy**, a harder downstream metric that also requires
  generating and judging an answer. Retrieval recall is an *upstream component* of those numbers,
  not the same quantity. We did not run an answer-generation/judge stage, so we have **no
  QA-accuracy number** to place next to 94.4 / 63.8 — only a retrieval-recall number.
- **Peer numbers are self-reported upper bounds.** The peer doc already records Mem0's LoCoMo
  self-report (91.6%) collapsing to 58–66% on independent reproduction. Ours is a first-party
  measurement too — treat it with the same skepticism and reproduce it (§6).

---

## 5. Why the LoCoMo gap, honestly

Our retriever is a **no-frills dense baseline**: embed the raw unit with `all-MiniLM-L6-v2`
(384-dim), cosine to the raw question. Every strong LoCoMo/LongMemEval peer adds machinery we do
**not** have in this path:
1. **LLM-based memory extraction / salience** — Mem0, Zep, MemPalace distill a conversation into
   salient fact records *before* indexing. We indexed raw turns/sessions verbatim.
2. **Reranking** — a cross-encoder or LLM reranker over the dense candidates.
3. **A memory graph / temporal KG** — Zep/Graphiti's edge that buys the temporal-reasoning gain.
4. **Turn-level is intrinsically harder than session-level.** LoCoMo asks us to pull the exact
   short turn out of ~590; LongMemEval asks for the right session out of ~50. That granularity
   difference alone explains most of the 45.8% vs 96.4% spread.

None of that is wired into the benchmarked retrieval path, so **45.8% R@10 LoCoMo is a floor for
the retrieval primitive**, not a measurement of a full memory pipeline. Our system was built for
truth-gated evidence-synthesis memory (project/verification learnings), not chat QA — this is the
first time its retrieval primitive has been put on the peers' turf, and the number should be read
in that light.

---

## 6. Reproduce

```bash
# Data (not vendored):
curl -sL -o locomo10.json https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json
curl -sL -o longmemeval_s.json "https://huggingface.co/datasets/xiaowu0162/longmemeval/resolve/main/longmemeval_s?download=true"

# Optional dep for the semantic/hybrid path (FTS path needs neither):
pip install sentence-transformers torch --extra-index-url https://download.pytorch.org/whl/cpu

cd F:\overmind   # branch: mem-recall-benchmark-2026-07-10
python -m evals.public_memory_bench.run_bench --dataset locomo      --data locomo10.json      --config semantic
python -m evals.public_memory_bench.run_bench --dataset longmemeval --data longmemeval_s.json --config semantic
python -m pytest tests/unit/test_public_memory_bench.py -q          # 5 passed
```

Environment: Python 3.13, `torch 2.13.0+cpu`, `sentence-transformers 5.6.0`, embedder
`all-MiniLM-L6-v2` (384-dim). All 500 LongMemEval questions and all 1982 LoCoMo gold-bearing QA
were used — no sampling.

---

## 7. Bottom line

- **We now have a real, publicly-comparable recall number** where GAP #2 said we had none:
  **96.4% R@10 (LongMemEval, session) / 45.8% R@10 (LoCoMo, turn)** for the shipped semantic path.
- **The honest apples-to-apples verdict** (vs MemPalace's 88.9% R@10 LoCoMo): our un-augmented
  dense retriever is **~half** the best published LoCoMo retriever, and our keyword-only default
  is effectively non-functional for NL questions.
- **Do not** put our retrieval-recall next to the Mem0/Zep 94.4/63.8 QA-accuracy headlines as if
  they were the same metric — they are not, and we did not produce a QA-accuracy number.
- **Cheapest credible gains** if we choose to close the LoCoMo gap: (a) fix the FTS query builder
  to not AND stopwords so `hybrid` degrades gracefully; (b) add an LLM/extractor salience step
  before indexing; (c) add a reranker. All are behaviour changes and out of scope for this
  measurement-only pass.
