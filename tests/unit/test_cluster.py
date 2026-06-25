"""Unit tests for the codified cluster capability (#4)."""
from __future__ import annotations

import pytest

from overmind.cluster import (
    DeltaSkipGate,
    Dispatcher,
    LocalExecutor,
    NodeRegistry,
    RemoteExecutor,
    SSHExecutor,
    SSHTransport,
)
from overmind.cluster.registry import Node
from overmind.cluster.transport import RemoteTransientError, TransportResult, UnsafeCommandError
from overmind.verification.contract_impact import ContractImpactGraph


def _runner(job):
    return {"repo": job["repo"], "verdict": "PASS"}


def _fake_transport(returncode=0, stdout='{"verdict": "PASS"}', stderr="", transient=False):
    def run_fn(argv, timeout):
        return (returncode, stdout, stderr)
    return SSHTransport(run_fn=run_fn)


# ── registry / executors ────────────────────────────────────────────


def test_local_executor_runs_job():
    out = LocalExecutor("local").run({"repo": "X"}, _runner)
    assert out["repo"] == "X" and out["verdict"] == "PASS"
    assert out["executor"] == "local"


def test_ssh_executor_runs_remote_command():
    node = Node(name="r", kind="remote", tailscale_ip="100.0.0.1", ssh_user="u",
                ssh_key_path="/k/id_ed25519")
    ex = SSHExecutor(node, transport=_fake_transport(stdout='{"repo":"X","verdict":"PASS"}'))
    out = ex.run({"repo": "X", "command": "python -m pytest"}, _runner)
    assert out["verdict"] == "PASS" and out["node"] == "r" and out["executor"] == "ssh:r"


def test_ssh_executor_transient_raises_for_requeue():
    node = Node(name="r", kind="remote", tailscale_ip="100.0.0.1", ssh_user="u")
    ex = SSHExecutor(node, transport=_fake_transport(returncode=255, stderr="Connection refused"))
    with pytest.raises(RemoteTransientError):
        ex.run({"repo": "X", "command": "python -m pytest"}, _runner)


def test_ssh_executor_refuses_missing_command():
    node = Node(name="r", kind="remote", tailscale_ip="100.0.0.1", ssh_user="u")
    with pytest.raises(UnsafeCommandError):
        SSHExecutor(node, transport=_fake_transport()).run({"repo": "X"}, _runner)


def test_remote_executor_alias_is_ssh_executor():
    assert RemoteExecutor is SSHExecutor


def test_registry_tracks_local_and_remote():
    reg = NodeRegistry()
    reg.register_local("l", max_parallel=3)
    reg.register_remote("r", address="rpi.tailnet", max_parallel=8)
    assert {n.name for n in reg.local_nodes()} == {"l"}
    assert reg.total_parallelism(local_only=True) == 3
    # remote executor exists but is the deferred one
    assert isinstance(reg.executor_for("r"), RemoteExecutor)


# ── dispatch ────────────────────────────────────────────────────────


def test_dispatch_runs_all_jobs_parallel():
    reg = NodeRegistry()
    reg.register_local("local", max_parallel=4)
    disp = Dispatcher(reg)
    jobs = [{"repo": r} for r in ["A", "B", "C"]]
    res = disp.dispatch(jobs, _runner)
    assert res.dispatched == 3
    assert [r["repo"] for r in res.results] == ["A", "B", "C"]   # sorted, deterministic
    assert res.errors == []


def test_dispatch_isolates_job_error():
    def boom(job):
        if job["repo"] == "B":
            raise ValueError("x")
        return {"repo": job["repo"], "verdict": "PASS"}
    reg = NodeRegistry()
    reg.register_local("local")
    res = Dispatcher(reg).dispatch([{"repo": "A"}, {"repo": "B"}], boom)
    assert {r["repo"] for r in res.results} == {"A"}
    assert len(res.errors) == 1 and res.errors[0]["repo"] == "B"


def test_dispatch_empty_is_noop():
    reg = NodeRegistry()
    reg.register_local("local")
    res = Dispatcher(reg).dispatch([], _runner)
    assert res.dispatched == 0 and res.results == []


# ── delta-skip gate ─────────────────────────────────────────────────


def _impact_graph():
    g = ContractImpactGraph()
    for r in ["R1", "R2", "R3", "R4", "R5"]:
        g.add_repo(r)
    g.add_dependency("R1", depends_on="M")
    g.add_dependency("R2", depends_on="M")
    g.add_dependency("R3", depends_on="R1")
    return g


def test_delta_skip_runs_only_changed():
    gate = DeltaSkipGate()
    last = {"A": "h", "B": "h", "C": "h"}
    cur = {"A": "h", "B": "CHANGED", "C": "h"}
    d = gate.decide(last, cur)
    assert d.to_run == ["B"]
    assert d.skipped == ["A", "C"]


def test_delta_skip_pulls_in_impacted_dependents():
    gate = DeltaSkipGate(impact_graph=_impact_graph())
    repos = ["R1", "R2", "R3", "R4", "R5"]
    last = {r: "h0" for r in repos} | {"M": "m0"}
    cur = {r: "h0" for r in repos} | {"M": "m1"}   # only M changed
    d = gate.decide(last, cur)
    # impacted dependents pulled in despite unchanged content
    assert set(d.to_run) == {"R1", "R2", "R3"}
    assert set(d.skipped) == {"R4", "R5"}
    # SAFETY: no impacted dependent is skipped
    assert {"R1", "R2", "R3"}.isdisjoint(set(d.skipped))


def test_delta_skip_naive_would_unsafely_skip_dependents():
    # Without the impact graph, the unchanged dependents would be skipped (unsafe).
    naive = DeltaSkipGate(impact_graph=None)
    repos = ["R1", "R2", "R3", "R4", "R5"]
    d = naive.decide({r: "h0" for r in repos}, {r: "h0" for r in repos})
    assert set(d.skipped) == set(repos)   # all skipped — incl. impacted R1,R2,R3
