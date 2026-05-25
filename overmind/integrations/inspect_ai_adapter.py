"""Phase-3 N: convert Overmind nightly bundles into inspect_ai-compatible
EvalLog JSON.

inspect_ai (UKGovernmentBEIS) is the de-facto standard for LLM-evaluation
transcript viewing. Overmind's witness verdicts + arbitration shape map
cleanly onto inspect_ai's Sample/Score/EvalError vocabulary:

  CertBundle.witness_results[]  ->  EvalLog.samples[]
  per-witness verdict           ->  Sample.scores
  per-witness stderr            ->  Sample.error (when verdict == FAIL)
  arbitration_reason            ->  EvalLog.results.summary

This is an ADDITIVE integration — the original Overmind bundle pipeline
is unchanged. Operators who already use inspect view to triage LLM-eval
transcripts can drop Overmind's nightly into the same viewer.

Usage from a script:
    from overmind.integrations.inspect_ai_adapter import bundle_to_inspect
    eval_log_dict = bundle_to_inspect(bundle_json_blob)
    Path("out.json").write_text(json.dumps(eval_log_dict))

The output JSON is shaped to be readable by `inspect view <path>` per the
inspect_ai EvalLog schema; we emit a minimal subset that's enough for the
viewer to render the witness verdicts and the arbitration text.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _verdict_to_score(verdict: str) -> dict:
    """Map an Overmind witness verdict to an inspect_ai Score blob.
    inspect_ai's Score takes a `value` (numeric or string) and an optional
    `answer` / `explanation`. We use string values matching Overmind's
    verdict vocabulary."""
    return {
        "value": verdict,
        "answer": verdict,
        "explanation": f"Overmind witness verdict: {verdict}",
    }


def bundle_to_inspect(bundle: dict) -> dict:
    """Convert one Overmind CertBundle JSON to a minimal inspect_ai EvalLog.

    Output structure (subset of EvalLog that inspect view renders):
      {
        "version": 2,
        "status": "success" | "error",
        "eval": {
          "task": "overmind/<project>",
          "task_id": "<project_id>",
          "task_version": "<verdict>",
          "created": "<iso>",
          ...
        },
        "samples": [
          {
            "id": "<witness_type>",
            "input": "<command>",
            "target": "PASS",
            "output": {"choices": [...]},
            "scores": {"verdict": <Score>},
            "error": null | {"message": stderr_tail}
          }
        ],
        "results": {"scores": [...], "summary": "<arbitration_reason>"}
      }
    """
    project_id = bundle.get("project_id", "unknown")
    scope_lock = bundle.get("scope_lock", {}) or {}
    project_path = scope_lock.get("project_path", "")
    verdict = bundle.get("verdict", "UNKNOWN")
    arbitration = bundle.get("arbitration_reason", "")
    witness_results = bundle.get("witness_results", []) or []
    created = bundle.get("created_at") or datetime.now(timezone.utc).isoformat()

    samples = []
    for w in witness_results:
        wtype = w.get("witness_type", "unknown")
        wverdict = w.get("verdict", "UNKNOWN")
        stderr = w.get("stderr") or ""
        stdout = w.get("stdout") or ""
        sample = {
            "id": wtype,
            "input": scope_lock.get("test_command", ""),
            "target": "PASS",
            "output": {
                "choices": [{
                    "message": {
                        "content": (stdout or stderr or "")[:2000],
                        "role": "assistant",
                    }
                }]
            },
            "scores": {"verdict": _verdict_to_score(wverdict)},
            "metadata": {
                "exit_code": w.get("exit_code"),
                "elapsed": w.get("elapsed"),
                "witness_type": wtype,
            },
        }
        if wverdict == "FAIL":
            sample["error"] = {"message": (stderr or "")[:1000]}
        samples.append(sample)

    return {
        "version": 2,
        "status": "success" if verdict in ("CERTIFIED", "PASS") else "error",
        "eval": {
            "task": f"overmind/{project_id}",
            "task_id": project_id,
            "task_version": verdict,
            "created": created,
            "model": "overmind-witnesses",
            "dataset": {
                "name": "overmind-nightly",
                "location": project_path,
            },
            "config": {
                "risk_profile": scope_lock.get("risk_profile", ""),
                "witness_count": scope_lock.get("witness_count", 0),
            },
        },
        "samples": samples,
        "results": {
            "scores": [
                {
                    "name": "verdict",
                    "value": verdict,
                    "metrics": {
                        wtype.get("witness_type", "?"): {"value": wtype.get("verdict", "?")}
                        for wtype in witness_results
                    },
                }
            ],
            "summary": arbitration or f"Overmind verdict: {verdict}",
        },
    }


def bundle_file_to_inspect(bundle_path: Path) -> dict:
    """Load + convert one bundle file."""
    return bundle_to_inspect(json.loads(Path(bundle_path).read_text(encoding="utf-8")))
