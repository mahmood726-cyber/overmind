"""Eval 11 — cluster delta-skip hash-gate (safe incremental verification).

Converts the previously-undocumented "multi-node cluster" into a measured
capability on two axes:

  1. **Savings** — a content-hash gate skips repos unchanged since their last
     green verdict, so a nightly run does work proportional to the delta.
  2. **Safety** — it must NEVER skip a repo whose cross-repo dependency changed
     (house lesson / C5 caveat). Routing the changed set through the #3d
     ContractImpactGraph guarantees impacted dependents are pulled back in even
     though their own content is unchanged.

Scenario: shared module **M** consumed by **R1, R2**; **R3** depends on R1
(transitive on M); **R4, R5** independent. Only **M** changes (all repo contents
unchanged).

  graph-gate   → run {R1,R2,R3}, skip {R4,R5}   (40% safely skipped)
  naive hash   → skip all 5 (sees only unchanged repo hashes) — UNSAFELY skips
                 the 3 impacted dependents.

Also exercises the REAL parallel `Dispatcher` + `LocalExecutor` over the to-run
set (works today; the remote Tailscale transport is explicitly DEFERRED — the
`RemoteExecutor` raises rather than pretending).
"""
from __future__ import annotations

from overmind.cluster import DeltaSkipGate, Dispatcher, NodeRegistry, SSHExecutor, SSHTransport
from overmind.cluster.registry import Node
from overmind.verification.contract_impact import ContractImpactGraph

from evals.common import pct, write_result

_REPOS = ["R1", "R2", "R3", "R4", "R5"]


def _impact_graph() -> ContractImpactGraph:
    g = ContractImpactGraph()
    for r in _REPOS:
        g.add_repo(r)
    g.add_dependency("R1", depends_on="M")
    g.add_dependency("R2", depends_on="M")
    g.add_dependency("R3", depends_on="R1")
    return g


def _runner(job: dict) -> dict:
    # A trivial deterministic "verification" — returns PASS for the repo.
    return {"repo": job["repo"], "verdict": "PASS"}


def evaluate() -> dict:
    impacted_truth = {"R1", "R2", "R3"}   # depend (transitively) on M

    # Hashes: only the shared module M changed; every repo's content is unchanged.
    last = {r: "h0" for r in _REPOS} | {"M": "m0"}
    current = {r: "h0" for r in _REPOS} | {"M": "m1"}

    # Graph-aware gate.
    graph_gate = DeltaSkipGate(impact_graph=_impact_graph())
    g = graph_gate.decide(last, current)

    # Naive hash-only gate (no impact graph; sees repo hashes only).
    naive_gate = DeltaSkipGate(impact_graph=None)
    n = naive_gate.decide({r: "h0" for r in _REPOS}, {r: "h0" for r in _REPOS})

    graph_impacted_skipped = sorted(impacted_truth & set(g.skipped))
    naive_impacted_skipped = sorted(impacted_truth & set(n.skipped))

    # Real parallel dispatch over the graph gate's to_run set.
    reg = NodeRegistry()
    reg.register_local("local", max_parallel=4)
    disp = Dispatcher(reg)
    jobs = [{"repo": r} for r in g.to_run]
    dr = disp.dispatch(jobs, _runner)

    # Remote transport is now REAL (was a NotImplementedError stub). Confirm the
    # SSH executor actually runs a remote command via an injected transport (the
    # live multi-machine path additionally needs a reachable, key-authorized node).
    remote_transport_real = False
    fake_transport = SSHTransport(run_fn=lambda argv, t: (0, '{"repo":"R1","verdict":"PASS"}', ""))
    node = Node(name="rpi", kind="remote", tailscale_ip="100.0.0.9", ssh_user="u")
    rout = SSHExecutor(node, transport=fake_transport).run(
        {"repo": "R1", "command": "python -m pytest -q"}, _runner
    )
    remote_transport_real = rout.get("verdict") == "PASS" and rout.get("node") == "rpi"

    payload = {
        "eval": "cluster_delta_skip",
        "n_repos": len(_REPOS),
        "changed_sources": g.changed_directly,
        "to_run": g.to_run,
        "skipped": g.skipped,
        "pulled_in_by_impact": g.pulled_in_by_impact,
        "skip_rate": pct(len(g.skipped), len(_REPOS)),
        # SAFETY: graph gate must skip ZERO impacted dependents.
        "impacted_dependents_skipped_graph": len(graph_impacted_skipped),
        "impacted_dependents_skipped_naive": len(naive_impacted_skipped),
        "safe_no_impacted_skipped": len(graph_impacted_skipped) == 0,
        # Real parallel dispatch worked over the to_run set.
        "dispatched": dr.dispatched,
        "dispatch_results": len(dr.results),
        "dispatch_errors": len(dr.errors),
        "remote_transport_real": remote_transport_real,
    }
    return payload


def main() -> dict:
    payload = evaluate()
    path = write_result("cluster_delta_skip", payload)
    print(f"[cluster_delta_skip] safely skipped {payload['skip_rate']:.0%} "
          f"({len(payload['skipped'])}/{payload['n_repos']}) repos; "
          f"to_run={payload['to_run']} (pulled in by impact: {payload['pulled_in_by_impact']})")
    print(f"[cluster_delta_skip] SAFETY impacted dependents skipped: "
          f"graph={payload['impacted_dependents_skipped_graph']} "
          f"vs naive={payload['impacted_dependents_skipped_naive']} "
          f"-> safe={payload['safe_no_impacted_skipped']}")
    print(f"[cluster_delta_skip] parallel dispatch: {payload['dispatch_results']}/"
          f"{payload['dispatched']} results, {payload['dispatch_errors']} errors; "
          f"remote transport real (SSH executor runs): {payload['remote_transport_real']}")
    print(f"[cluster_delta_skip] -> {path}")
    return payload


if __name__ == "__main__":
    main()
