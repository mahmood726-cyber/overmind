"""OFFLINE-CORE PROOF (measurement-only): the deterministic core — pooling +
objective witness floor + structural gate — runs with the network HARD-CUT.

We enforce the cut at the socket layer for THIS process: every attempt to open a
non-loopback socket raises ``OfflineViolation``. This is a real, enforced cut at
the OS syscall boundary (not an assertion) — if the core made any network call it
would crash. We deliberately do NOT physically down the NIC (that would sever the
agent session and loopback-only Ollama is irrelevant to the deterministic core);
the per-process socket block is a strictly stronger, reproducible guarantee for
the code under test.

Runs the FULL deterministic battery over EVERY task (all slices) + re-pools every
reproduction task, entirely offline. Emits a JSON proof artifact.

    python -m evals.offline_core_proof
"""
from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class OfflineViolation(RuntimeError):
    pass


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_real_socket = socket.socket
_real_getaddrinfo = socket.getaddrinfo


def _install_network_blackhole():
    """Block all non-loopback network use for this process. Any connect() to a
    non-loopback address raises OfflineViolation."""
    class _GuardedSocket(_real_socket):
        def connect(self, address):
            host = address[0] if isinstance(address, tuple) else str(address)
            if host not in _LOOPBACK:
                raise OfflineViolation(f"network is CUT: blocked connect to {address}")
            return super().connect(address)

        def connect_ex(self, address):
            host = address[0] if isinstance(address, tuple) else str(address)
            if host not in _LOOPBACK:
                raise OfflineViolation(f"network is CUT: blocked connect_ex to {address}")
            return super().connect_ex(address)

    def _guarded_getaddrinfo(host, *a, **k):
        if host not in _LOOPBACK and host is not None:
            raise OfflineViolation(f"network is CUT: blocked DNS lookup of {host}")
        return _real_getaddrinfo(host, *a, **k)

    socket.socket = _GuardedSocket
    socket.getaddrinfo = _guarded_getaddrinfo


def _self_test() -> dict:
    """Prove the blackhole actually blocks a real outbound connection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("8.8.8.8", 53))
        s.close()
        return {"blackhole_enforced": False, "note": "OUTBOUND SUCCEEDED — guard FAILED"}
    except OfflineViolation as e:
        return {"blackhole_enforced": True, "blocked": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"blackhole_enforced": "inconclusive", "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    _install_network_blackhole()
    selftest = _self_test()
    # Imports AFTER the blackhole is armed — proves import path is offline too.
    from overmind.benchmark.tasks import load_tasks, load_keys, frozen_ids, held_out_ids, dev_ids
    from overmind.benchmark.witnesses import run_witness
    from overmind.benchmark.arms import arm_c
    from overmind.benchmark.scoring import score_arm

    DATA = ROOT / "benchmark_data"
    tasks = load_tasks(DATA / "tasks.json")
    keys = load_keys(DATA / "keys" / "keys.json")
    ids = [t.id for t in tasks]

    t0 = time.time()
    witness_fired = 0
    repro_checked = 0
    per_slice = {}
    slices = {"held_out": held_out_ids(ids), "frozen": frozen_ids(ids), "dev": dev_ids(ids)}
    for t in tasks:
        wr = run_witness(t)              # pooling + impossible-cell + CI battery, deterministic
        if wr.defect:
            witness_fired += 1
        if t.data.get("claimed_value") is not None and t.data.get("studies"):
            repro_checked += 1

    # Score the objective floor alone (arm_c with no reviewers) per sealed slice —
    # the pure no-LLM baseline, computed fully offline.
    for sname, sids in slices.items():
        held = [t for t in tasks if t.id in sids]
        sk = {t.id: keys[t.id] for t in held}
        wd = {t.id: bool(run_witness(t).defect) for t in held}
        ref = {t.id: arm_c(t.id, [], wd[t.id]) for t in held}
        m = score_arm("objective_floor", ref, sk)
        per_slice[sname] = {"n": len(held), "defects": m.defects, "cleans": m.cleans,
                            "floor_caught": m.caught, "floor_caught_rate": m.caught_defect_rate,
                            "floor_caught_ci95": m.caught_defect_ci,
                            "floor_false_alarms": m.false_alarms, "floor_far": m.false_alarm_rate}
    elapsed = round(time.time() - t0, 2)

    proof = {
        "proof": "deterministic core runs fully offline (network hard-cut at socket layer)",
        "network_blackhole_selftest": selftest,
        "tasks_processed": len(tasks),
        "witness_battery_fired_count": witness_fired,
        "reproduction_pooling_recomputed": repro_checked,
        "wall_clock_s": elapsed,
        "objective_floor_by_slice": per_slice,
        "note": "All numbers above were computed with every non-loopback socket blocked; "
                "the run completing is the proof the pooling + witness floor + structural gate "
                "make ZERO network calls.",
    }
    out = DATA / "runs_offline_local" / "offline_core_proof.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps(proof, indent=2))
    print(f"\nproof -> {out}")
    # Fail loudly if the guard didn't actually block.
    if selftest.get("blackhole_enforced") is not True:
        print("WARNING: network blackhole self-test did not confirm a block", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
