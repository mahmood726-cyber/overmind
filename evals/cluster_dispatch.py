"""Eval 12 — cluster job-dispatch correctness (the self-load-balancing fleet).

Proves the four scheduler guarantees on deterministic, offline fixtures (injected
executors / transports — no live nodes needed):

  1. **Capability + data-locality routing** — a job goes only to a node that has
     its required engine AND its required data volume; a job needing a capability
     no online node has is reported *unschedulable*, never silently dropped or
     mis-routed.
  2. **Load balancing** — between two equally-capable nodes, the job lands on the
     **least-loaded** one (fewer in-flight jobs).
  3. **Delta-skip safety** — unchanged repos are skipped, but a repo whose
     cross-repo dependency changed is NOT skipped (routed through the impact graph),
     and only the to-run set is dispatched.
  4. **Requeue on offline** — a node that fails mid-job with a transient SSH error
     is marked offline and its job is requeued to another capable node; the work is
     never lost and the result lands on the healthy node.

Every number is computed from the REAL ``JobScheduler`` / ``select_node`` /
``DeltaSkipGate`` / ``SSHExecutor`` — not a mock of them.
"""
from __future__ import annotations

from overmind.cluster import (
    Capabilities,
    DeltaSkipGate,
    Job,
    JobScheduler,
    Node,
    NodeRegistry,
    SSHExecutor,
    SSHTransport,
    select_node,
)
from overmind.cluster.transport import RemoteTransientError
from overmind.verification.contract_impact import ContractImpactGraph

from evals.common import pct, write_result


def _runner(job: dict) -> dict:
    return {"repo": job["repo"], "verdict": "PASS"}


def _online_node(reg: NodeRegistry, name: str, *, engines=(), data=(), cores=4, max_parallel=4) -> Node:
    node = reg.register_local(
        name, max_parallel=max_parallel,
        capabilities=Capabilities(engines=tuple(engines), data_volumes=tuple(data), cores=cores),
    )
    return node


# ── 1. capability + data-locality routing ───────────────────────────


def _eval_routing() -> dict:
    reg = NodeRegistry()
    # "gpu" has agy + the ubcma volume; "data" has claude + the aact volume.
    _online_node(reg, "gpu", engines=("agy",), data=("ubcma",))
    _online_node(reg, "data", engines=("claude",), data=("aact",))

    jobs = [
        Job(repo="ubcma-job", needs_engines=("agy",), needs_data=("ubcma",)),   # → gpu
        Job(repo="aact-job", needs_engines=("claude",), needs_data=("aact",)),  # → data
        Job(repo="needs-codex", needs_engines=("codex",)),                       # → unschedulable
    ]
    res = JobScheduler(reg).schedule(jobs, _runner)

    expected = {"ubcma-job": "gpu", "aact-job": "data"}
    routed_correct = sum(1 for r, n in expected.items() if res.assignments.get(r) == n)
    locality_ok = res.assignments.get("aact-job") == "data" and res.assignments.get("ubcma-job") == "gpu"
    # the codex job has no capable node → must be unschedulable, not mis-routed
    unschedulable_repos = {u["repo"] for u in res.unschedulable}
    return {
        "assignments": res.assignments,
        "routed_correct_rate": pct(routed_correct, len(expected)),
        "data_locality_respected": locality_ok,
        "unschedulable": sorted(unschedulable_repos),
        "uncapable_job_unschedulable": "needs-codex" in unschedulable_repos,
        "no_misroute_of_uncapable": "needs-codex" not in res.assignments,
    }


# ── 2. load balancing ───────────────────────────────────────────────


def _eval_load_balancing() -> dict:
    reg = NodeRegistry()
    _online_node(reg, "busy", engines=("claude",), max_parallel=4)
    _online_node(reg, "idle", engines=("claude",), max_parallel=4)
    # Pre-load "busy" with 2 in-flight jobs; "idle" has 0.
    reg.mark_running_delta("busy", +2)

    job = Job(repo="j", needs_engines=("claude",))
    chosen = select_node(reg, job)
    return {
        "busy_running": reg.state("busy").running,
        "idle_running": reg.state("idle").running,
        "least_loaded_chosen": chosen.name if chosen else None,
        "load_balanced_to_idle": (chosen is not None and chosen.name == "idle"),
    }


# ── 3. delta-skip safety (unchanged skipped, impacted NOT skipped) ───


def _eval_delta_skip() -> dict:
    repos = ["R1", "R2", "R3", "R4", "R5"]
    g = ContractImpactGraph()
    for r in repos:
        g.add_repo(r)
    g.add_dependency("R1", depends_on="M")
    g.add_dependency("R2", depends_on="M")
    g.add_dependency("R3", depends_on="R1")  # transitive on M

    last = {r: "h0" for r in repos} | {"M": "m0"}
    current = {r: "h0" for r in repos} | {"M": "m1"}   # only shared M changed
    decision = DeltaSkipGate(impact_graph=g).decide(last, current)

    impacted_truth = {"R1", "R2", "R3"}
    impacted_skipped = impacted_truth & set(decision.skipped)

    # Dispatch only the to-run set across a small fleet.
    reg = NodeRegistry()
    _online_node(reg, "n1", engines=(), max_parallel=4)
    jobs = [Job(repo=r) for r in decision.to_run]
    res = JobScheduler(reg).schedule(jobs, _runner)

    return {
        "to_run": decision.to_run,
        "skipped": decision.skipped,
        "skip_rate": pct(len(decision.skipped), len(repos)),
        "impacted_dependents_skipped": len(impacted_skipped),
        "safe_no_impacted_skipped": len(impacted_skipped) == 0,
        "dispatched_only_to_run": sorted(res.assignments) == sorted(decision.to_run),
    }


# ── 4. requeue on offline ────────────────────────────────────────────


def _transient_executor(node: Node) -> SSHExecutor:
    """An SSH executor whose transport always reports a connection failure."""
    return SSHExecutor(node, transport=SSHTransport(run_fn=lambda argv, t: (255, "", "Connection refused")))


def _eval_requeue() -> dict:
    reg = NodeRegistry()
    # "alpha" (sorts first → selected first) is a REMOTE node whose SSH transport
    # always fails (transient); "bravo" is a healthy local node. Both have claude.
    reg.register_remote(
        "alpha", address="100.0.0.1", tailscale_ip="100.0.0.1", ssh_user="u",
        ssh_key_path="/k/id_ed25519",
        capabilities=Capabilities(engines=("claude",), cores=4),
    )
    reg.set_status("alpha", "online", detail="probed online")  # remote starts 'unknown'
    _online_node(reg, "bravo", engines=("claude",), max_parallel=4)
    reg.set_executor("alpha", _transient_executor(reg.get("alpha")))

    job = Job(repo="j", needs_engines=("claude",), command="python -m pytest -q", max_attempts=3)
    res = JobScheduler(reg).schedule([job], _runner)

    landed = res.assignments.get("j")
    return {
        "requeued": res.requeued,                 # records {repo, from_node}
        "requeue_count": len(res.requeued),
        "requeued_from_alpha": any(q["from_node"] == "alpha" for q in res.requeued),
        "alpha_marked_offline": reg.state("alpha").status == "offline",
        "landed_on": landed,
        "work_not_lost": landed == "bravo",
        "errors": res.errors,
    }


def evaluate() -> dict:
    routing = _eval_routing()
    load = _eval_load_balancing()
    delta = _eval_delta_skip()
    requeue = _eval_requeue()

    all_pass = (
        routing["routed_correct_rate"] == 1.0
        and routing["data_locality_respected"]
        and routing["uncapable_job_unschedulable"]
        and load["load_balanced_to_idle"]
        and delta["safe_no_impacted_skipped"]
        and delta["dispatched_only_to_run"]
        and requeue["work_not_lost"]
        and requeue["alpha_marked_offline"]
    )
    return {
        "eval": "cluster_dispatch",
        "routing": routing,
        "load_balancing": load,
        "delta_skip": delta,
        "requeue": requeue,
        "all_guarantees_hold": all_pass,
    }


def main() -> dict:
    payload = evaluate()
    path = write_result("cluster_dispatch", payload)
    r, l, d, q = payload["routing"], payload["load_balancing"], payload["delta_skip"], payload["requeue"]
    print(f"[cluster_dispatch] routing: {r['routed_correct_rate']:.0%} correct, "
          f"data-locality={r['data_locality_respected']}, "
          f"uncapable->unschedulable={r['uncapable_job_unschedulable']}")
    print(f"[cluster_dispatch] load-balance: chose least-loaded '{l['least_loaded_chosen']}' "
          f"(busy={l['busy_running']} vs idle={l['idle_running']}) -> {l['load_balanced_to_idle']}")
    print(f"[cluster_dispatch] delta-skip: {d['skip_rate']:.0%} skipped, "
          f"impacted skipped={d['impacted_dependents_skipped']}, "
          f"dispatched-only-to-run={d['dispatched_only_to_run']}")
    print(f"[cluster_dispatch] requeue: alpha offline={q['alpha_marked_offline']}, "
          f"requeued={q['requeue_count']}, landed on '{q['landed_on']}' (work not lost={q['work_not_lost']})")
    print(f"[cluster_dispatch] ALL guarantees hold: {payload['all_guarantees_hold']} -> {path}")
    return payload


if __name__ == "__main__":
    main()
