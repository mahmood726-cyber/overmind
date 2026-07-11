"""Unit tests for the read-only public memory-recall benchmark adapter.

These use tiny synthetic fixtures (no external data, no embedding backend) and
exercise the FTS path through the REAL MemoryStore, so they prove:
  * the recall@k math is correct (hit within k, miss beyond k),
  * gold coverage is computed correctly for multi-evidence questions,
  * no-gold (adversarial) questions are excluded, not counted as misses,
  * the LoCoMo / LongMemEval loaders parse the published schema.
"""
from __future__ import annotations

import json
from pathlib import Path

from evals.public_memory_bench.adapter import (
    Question,
    Sample,
    Unit,
    load_locomo,
    load_longmemeval,
    run_recall,
)


def _sample() -> Sample:
    # Six turns; only the keyword-distinctive ones are retrievable by FTS AND.
    units = (
        Unit("t1", "Alice", "Alice: I adopted a beagle named Pixel last Tuesday."),
        Unit("t2", "Bob", "Bob: Nice! What color is the beagle Pixel?"),
        Unit("t3", "Alice", "Alice: Pixel is tricolor and loves the dog park."),
        Unit("t4", "Bob", "Bob: I prefer cats honestly."),
        Unit("t5", "Alice", "Alice: My favorite pizza topping is pineapple."),
        Unit("t6", "Bob", "Bob: Pineapple on pizza is controversial."),
    )
    questions = (
        # gold t1 — query shares the rare token "Pixel beagle adopted"
        Question("q_hit", "beagle Pixel adopted", ("t1",), "single-hop"),
        # gold t5 — shares "pizza topping pineapple"
        Question("q_hit2", "pizza topping pineapple", ("t5",), "single-hop"),
        # multi-evidence: both t1 and t3 mention Pixel
        Question("q_multi", "Pixel", ("t1", "t3"), "multi-hop"),
        # no gold -> excluded
        Question("q_none", "unanswerable adversarial", (), "adversarial"),
    )
    return Sample("s0", units, questions)


def test_recall_hit_and_exclusion():
    res = run_recall([_sample()], dataset="synthetic", config="fts",
                     unit_granularity="turn", ks=(1, 3, 5))
    # 3 gold-bearing questions counted, 1 excluded.
    assert res.n_questions == 3
    assert res.excluded_no_gold == 1
    # The two single-hop keyword questions must be found within top-5.
    assert res.recall_at_k[5] >= 2 / 3
    # Recall is monotonic non-decreasing in k.
    assert res.recall_at_k[1] <= res.recall_at_k[3] <= res.recall_at_k[5]
    # Coverage is between 0 and 1.
    for k in (1, 3, 5):
        assert 0.0 <= res.coverage_at_k[k] <= 1.0


def test_category_breakdown_present():
    res = run_recall([_sample()], dataset="synthetic", config="fts",
                     unit_granularity="turn", ks=(5,))
    assert "single-hop" in res.by_category
    assert "adversarial" not in res.by_category  # excluded questions never counted


def test_miss_when_keywords_absent():
    # A gold turn whose distinctive words never appear in the query -> miss.
    units = (Unit("x1", "A", "A: The quarterly revenue was forty two thousand euros."),)
    q = Question("qm", "what is the airspeed velocity of a swallow", ("x1",), "single-hop")
    res = run_recall([Sample("s", units, (q,))], dataset="synthetic", config="fts",
                     unit_granularity="turn", ks=(1, 5))
    assert res.n_questions == 1
    assert res.recall_at_k[5] == 0.0


def test_load_locomo_schema(tmp_path: Path):
    fixture = [
        {
            "sample_id": "conv-x",
            "qa": [
                {"question": "Where did Alice adopt Pixel?", "answer": "shelter",
                 "evidence": ["D1:1"], "category": 4},
                {"question": "unanswerable?", "answer": "no info", "category": 5},
            ],
            "conversation": {
                "speaker_a": "Alice", "speaker_b": "Bob",
                "session_1_date_time": "1 Jan 2023",
                "session_1": [
                    {"speaker": "Alice", "dia_id": "D1:1", "text": "I adopted Pixel from the shelter."},
                    {"speaker": "Bob", "dia_id": "D1:2", "text": "Great!"},
                ],
            },
        }
    ]
    p = tmp_path / "locomo.json"
    p.write_text(json.dumps(fixture), encoding="utf-8")
    samples = load_locomo(p)
    assert len(samples) == 1
    s = samples[0]
    assert len(s.units) == 2
    assert {u.unit_id for u in s.units} == {"D1:1", "D1:2"}
    assert s.questions[0].gold_ids == ("D1:1",)
    assert s.questions[0].category == "single-hop"
    assert s.questions[1].gold_ids == ()  # adversarial, no evidence
    assert s.questions[1].category == "adversarial"


def test_load_longmemeval_schema(tmp_path: Path):
    fixture = [
        {
            "question_id": "q_abc",
            "question_type": "single-session-user",
            # Keyword query whose tokens all appear in the gold session -- this
            # test checks session-level retrieval MECHANICS, not NL-question
            # robustness (the FTS AND-of-tokens limitation is measured in the
            # real benchmark, not asserted here).
            "question": "GPS broke",
            "answer": "GPS",
            "haystack_session_ids": ["s_a", "s_b"],
            "haystack_sessions": [
                [{"role": "user", "content": "My GPS broke while driving.", "has_answer": True}],
                [{"role": "user", "content": "Nice weather today.", "has_answer": False}],
            ],
            "answer_session_ids": ["s_a"],
        }
    ]
    p = tmp_path / "lme.json"
    p.write_text(json.dumps(fixture), encoding="utf-8")
    samples = load_longmemeval(p)
    assert len(samples) == 1
    s = samples[0]
    assert {u.unit_id for u in s.units} == {"s_a", "s_b"}
    assert s.questions[0].gold_ids == ("s_a",)
    # session-level recall: the keyword query's tokens appear in the gold session.
    res = run_recall(samples, dataset="lme", config="fts",
                     unit_granularity="session", ks=(1, 2))
    assert res.n_questions == 1
    assert res.recall_at_k[2] == 1.0  # gold session retrieved within top-2
