"""Read-only adapter: run public memory benchmarks through the shipped MemoryStore.

Design (honest, no hand-tuning):
  * One fresh SQLite-backed ``MemoryStore`` per conversation/question — this is
    the natural "one memory per user" scope every peer evaluates under.
  * We ingest each retrieval unit as a real ``MemoryRecord`` and retrieve with
    the store's own public methods. The *raw* question is the query — we never
    strip stopwords, expand, or otherwise engineer the query, because the peers
    feed the raw question to their retriever too and the point is to measure OUR
    retriever, not a query we hand-built for it.
  * ``config`` selects which shipped retrieval path is exercised:
      - "fts"      : store.search()            — FTS5 keyword (AND-of-tokens), the
                                                 as-shipped default when no
                                                 embedding backend is installed.
      - "hybrid"   : store.hybrid_search()     — FTS5, then semantic fallback when
                                                 FTS returns < threshold hits.
      - "semantic" : db.semantic_search_memories() — pure vector cosine.
    "hybrid"/"semantic" require an embedding backend (sentence-transformers);
    when absent they degrade exactly as the shipped code degrades (semantic
    returns []), which is itself a reported result, not an error.

Metric: recall@k = fraction of questions for which >=1 gold evidence unit is in
the top-k retrieved set — the definition LongMemEval's retrieval eval and
MemPalace's LoCoMo R@k use. We also report gold *coverage* (mean fraction of
gold units retrieved) for transparency.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

from overmind.memory import embeddings
from overmind.memory.store import MemoryStore
from overmind.storage.db import StateDatabase
from overmind.storage.models import MemoryRecord

Config = Literal["fts", "hybrid", "semantic"]


@dataclass(frozen=True)
class Unit:
    """One retrievable item (a conversation turn or a session)."""
    unit_id: str
    title: str
    content: str


@dataclass(frozen=True)
class Question:
    qid: str
    query: str
    gold_ids: tuple[str, ...]
    category: str = ""


@dataclass(frozen=True)
class Sample:
    """One user's memory: the units to ingest + the questions to ask over them."""
    sample_id: str
    units: tuple[Unit, ...]
    questions: tuple[Question, ...]


@dataclass
class RecallResult:
    dataset: str
    config: Config
    unit_granularity: str
    ks: tuple[int, ...]
    n_questions: int
    n_samples: int
    n_units_total: int
    embedding_backend_available: bool
    recall_at_k: dict[int, float] = field(default_factory=dict)
    coverage_at_k: dict[int, float] = field(default_factory=dict)
    by_category: dict[str, dict[int, float]] = field(default_factory=dict)
    excluded_no_gold: int = 0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "config": self.config,
            "unit_granularity": self.unit_granularity,
            "ks": list(self.ks),
            "n_questions": self.n_questions,
            "n_samples": self.n_samples,
            "n_units_total": self.n_units_total,
            "embedding_backend_available": self.embedding_backend_available,
            "recall_at_k": {str(k): v for k, v in self.recall_at_k.items()},
            "coverage_at_k": {str(k): v for k, v in self.coverage_at_k.items()},
            "by_category_recall": {
                cat: {str(k): v for k, v in d.items()} for cat, d in self.by_category.items()
            },
            "excluded_no_gold": self.excluded_no_gold,
            "notes": self.notes,
        }


def _new_store(workdir: Path) -> tuple[MemoryStore, StateDatabase]:
    db = StateDatabase(workdir / "memory.db")
    store = MemoryStore(db=db, checkpoints_dir=workdir / "cp", logs_dir=workdir / "logs")
    return store, db


def _ingest(store: MemoryStore, units: Iterable[Unit], *, with_embeddings: bool) -> int:
    """Save each unit as a real MemoryRecord.

    When ``with_embeddings`` (hybrid/semantic configs) we populate
    ``record.embedding`` via the store's OWN embeddings module, exactly as
    ``MemoryExtractor.extract`` does in production (extractor.py:137). This is
    faithful ingest, not query-side tuning.
    """
    count = 0
    for u in units:
        emb = None
        if with_embeddings:
            emb = embeddings.embed(f"{u.title}\n{u.content}")
        store.save(
            MemoryRecord(
                memory_id=u.unit_id,
                memory_type="project_learning",
                scope="bench",
                title=u.title,
                content=u.content,
                embedding=emb,
            )
        )
        count += 1
    return count


def _retrieve_ids(store: MemoryStore, query: str, k: int, config: Config) -> list[str]:
    if config == "fts":
        return [m.memory_id for m in store.search(query, limit=k)]
    if config == "hybrid":
        return [m.memory_id for m in store.hybrid_search(query, limit=k)]
    if config == "semantic":
        scored = store.db.semantic_search_memories(query, limit=k)
        return [m.memory_id for m, _ in scored]
    raise ValueError(f"unknown config: {config}")


def run_recall(
    samples: list[Sample],
    *,
    dataset: str,
    config: Config,
    unit_granularity: str,
    ks: tuple[int, ...] = (1, 3, 5, 10),
    notes: str = "",
) -> RecallResult:
    """Ingest each sample into a fresh store and measure recall@k over its questions."""
    with_emb = config in ("hybrid", "semantic")
    backend = embeddings.is_available()

    kmax = max(ks)
    per_k_hits = {k: 0 for k in ks}
    per_k_cov = {k: 0.0 for k in ks}
    cat_hits: dict[str, dict[int, int]] = {}
    cat_tot: dict[str, int] = {}
    n_q = 0
    n_units_total = 0
    excluded = 0

    for s in samples:
        workdir = Path(tempfile.mkdtemp(prefix=f"pmb_{dataset}_"))
        store, db = _new_store(workdir)
        try:
            n_units_total += _ingest(store, s.units, with_embeddings=with_emb)
            for q in s.questions:
                gold = set(q.gold_ids)
                if not gold:
                    excluded += 1
                    continue
                n_q += 1
                top = _retrieve_ids(store, q.query, kmax, config)
                for k in ks:
                    topk = set(top[:k])
                    hit = len(gold & topk) > 0
                    per_k_hits[k] += int(hit)
                    per_k_cov[k] += len(gold & topk) / len(gold)
                    if q.category:
                        cat_hits.setdefault(q.category, {kk: 0 for kk in ks})
                        cat_hits[q.category][k] += int(hit)
                if q.category:
                    cat_tot[q.category] = cat_tot.get(q.category, 0) + 1
        finally:
            db.close()

    recall = {k: (per_k_hits[k] / n_q if n_q else 0.0) for k in ks}
    coverage = {k: (per_k_cov[k] / n_q if n_q else 0.0) for k in ks}
    by_cat = {
        cat: {k: (cat_hits[cat][k] / cat_tot[cat] if cat_tot[cat] else 0.0) for k in ks}
        for cat in cat_hits
    }

    return RecallResult(
        dataset=dataset,
        config=config,
        unit_granularity=unit_granularity,
        ks=ks,
        n_questions=n_q,
        n_samples=len(samples),
        n_units_total=n_units_total,
        embedding_backend_available=backend,
        recall_at_k=recall,
        coverage_at_k=coverage,
        by_category=by_cat,
        excluded_no_gold=excluded,
        notes=notes,
    )


# --------------------------------------------------------------------------- #
# Dataset loaders — pure parsing, no query manipulation.
# --------------------------------------------------------------------------- #

# LoCoMo QA category codes (snap-research/locomo README).
LOCOMO_CATEGORIES = {
    1: "multi-hop",
    2: "temporal",
    3: "open-domain",
    4: "single-hop",
    5: "adversarial",
}


def load_locomo(path: str | Path) -> list[Sample]:
    """LoCoMo: retrieval unit = one conversation turn (keyed by ``dia_id``);
    gold = the QA's ``evidence`` dia_ids. Adversarial (cat 5) / no-evidence QAs
    have empty gold and are excluded from recall (reported as excluded_no_gold).
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    samples: list[Sample] = []
    for i, conv in enumerate(raw):
        c = conv["conversation"]
        units: list[Unit] = []
        for key in c:
            if not key.startswith("session_") or key.endswith("date_time"):
                continue
            turns = c[key]
            if not isinstance(turns, list):
                continue
            for t in turns:
                did = t.get("dia_id")
                if not did:
                    continue
                speaker = t.get("speaker", "")
                text = t.get("text", "")
                # blip_caption/img content when the turn is an image share.
                cap = t.get("blip_caption") or ""
                body = text if not cap else f"{text} [shared image: {cap}]"
                units.append(Unit(unit_id=did, title=speaker, content=f"{speaker}: {body}"))
        questions: list[Question] = []
        for j, qa in enumerate(conv.get("qa", [])):
            ev = qa.get("evidence") or []
            gold = tuple(e for e in ev if isinstance(e, str))
            cat = LOCOMO_CATEGORIES.get(qa.get("category"), str(qa.get("category")))
            questions.append(
                Question(
                    qid=f"{conv.get('sample_id', i)}_q{j}",
                    query=str(qa.get("question", "")),
                    gold_ids=gold,
                    category=cat,
                )
            )
        samples.append(
            Sample(
                sample_id=str(conv.get("sample_id", f"conv{i}")),
                units=tuple(units),
                questions=tuple(questions),
            )
        )
    return samples


def load_longmemeval(path: str | Path, *, granularity: str = "session") -> list[Sample]:
    """LongMemEval: each QUESTION carries its own haystack of sessions, so each
    question becomes its own Sample (its own store).

    granularity="session": unit = one session (id = haystack_session_id, content
      = concatenated turns); gold = ``answer_session_ids``. This matches the
      session-level recall LongMemEval and the Mem0 blog report.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    samples: list[Sample] = []
    for q in raw:
        sess_ids = q["haystack_session_ids"]
        sessions = q["haystack_sessions"]
        units: list[Unit] = []
        for sid, turns in zip(sess_ids, sessions):
            parts = []
            for t in turns:
                role = t.get("role", "")
                content = t.get("content", "")
                parts.append(f"{role}: {content}")
            units.append(Unit(unit_id=sid, title=sid, content="\n".join(parts)))
        gold = tuple(q.get("answer_session_ids", []))
        question = Question(
            qid=q["question_id"],
            query=q["question"],
            gold_ids=gold,
            category=q.get("question_type", ""),
        )
        samples.append(
            Sample(sample_id=q["question_id"], units=tuple(units), questions=(question,))
        )
    return samples
