"""Unit tests for the self-load-balancing cluster fleet (registry/scheduler/
health/transport/onboard/config). Companion to test_cluster.py (delta-skip +
legacy dispatch)."""
from __future__ import annotations

import json
import threading

import pytest

from overmind.cluster import (
    Capabilities,
    HealthProber,
    Job,
    JobScheduler,
    Node,
    NodeRegistry,
    SSHExecutor,
    SSHTransport,
    build_ssh_argv,
    build_registry,
    load_config,
    onboard_node,
    select_node,
)
from overmind.cluster.config_io import add_node_to_config, seed_config_path
from overmind.cluster.transport import (
    RemoteTransientError,
    UnsafeCommandError,
    assert_command_safe,
    parse_result_line,
)


# ── capabilities + node serialisation ───────────────────────────────


def test_capabilities_covers():
    c = Capabilities(engines=("claude", "agy"), data_volumes=("ubcma",))
    assert c.covers(engines=("claude",), data=("ubcma",))
    assert c.covers(engines=("AGY",))                    # case-insensitive
    assert not c.covers(engines=("codex",))
    assert not c.covers(data=("aact",))


def test_node_dict_roundtrip():
    n = Node(name="x", kind="remote", tailscale_ip="100.1.2.3", ssh_user="u",
             ssh_key_path="/k", capabilities=Capabilities(engines=("claude",), cores=8))
    n2 = Node.from_dict(n.to_dict())
    assert n2 == n
    assert n.ssh_host == "100.1.2.3"


# ── select_node: capability / locality / load / exclude ─────────────


def _reg_two_capable():
    reg = NodeRegistry()
    reg.register_local("a", capabilities=Capabilities(engines=("claude",)))
    reg.register_local("b", capabilities=Capabilities(engines=("claude",)))
    return reg


def test_select_requires_capability_and_data():
    reg = NodeRegistry()
    reg.register_local("gpu", capabilities=Capabilities(engines=("agy",), data_volumes=("ubcma",)))
    reg.register_local("cpu", capabilities=Capabilities(engines=("claude",)))
    assert select_node(reg, Job(repo="j", needs_engines=("agy",), needs_data=("ubcma",))).name == "gpu"
    assert select_node(reg, Job(repo="j", needs_data=("aact",))) is None     # locality miss
    assert select_node(reg, Job(repo="j", needs_engines=("codex",))) is None  # engine miss


def test_select_least_loaded():
    reg = _reg_two_capable()
    reg.mark_running_delta("a", +3)        # a busier than b
    assert select_node(reg, Job(repo="j", needs_engines=("claude",))).name == "b"


def test_select_excludes_offline():
    reg = _reg_two_capable()
    reg.set_status("a", "offline")
    assert select_node(reg, Job(repo="j", needs_engines=("claude",))).name == "b"


def test_select_respects_capacity_and_exclude():
    reg = NodeRegistry()
    reg.register_local("a", max_parallel=1, capabilities=Capabilities(engines=("claude",)))
    reg.mark_running_delta("a", +1)        # full
    assert select_node(reg, Job(repo="j", needs_engines=("claude",))) is None
    reg.register_local("b", capabilities=Capabilities(engines=("claude",)))
    assert select_node(reg, Job(repo="j", needs_engines=("claude",)), exclude=frozenset({"b"})) is None


# ── scheduler: routing / unschedulable / concurrency / requeue ──────


def _runner(job):
    return {"repo": job["repo"], "verdict": "PASS"}


def test_scheduler_routes_and_reports_unschedulable():
    reg = NodeRegistry()
    reg.register_local("data", capabilities=Capabilities(engines=("claude",), data_volumes=("aact",)))
    jobs = [
        Job(repo="ok", needs_engines=("claude",), needs_data=("aact",)),
        Job(repo="no", needs_engines=("codex",)),
    ]
    res = JobScheduler(reg).schedule(jobs, _runner)
    assert res.assignments == {"ok": "data"}
    assert [u["repo"] for u in res.unschedulable] == ["no"]
    assert "no" not in res.assignments       # never mis-routed


def test_scheduler_concurrency_cap():
    reg = NodeRegistry()
    reg.register_local("n", max_parallel=2, capabilities=Capabilities(engines=("claude",)))
    peak = {"v": 0}
    cur = {"v": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)

    def runner(job):
        with lock:
            cur["v"] += 1
            peak["v"] = max(peak["v"], cur["v"])
        try:
            barrier.wait()                    # only releases when 2 are running together
        except threading.BrokenBarrierError:
            pass
        with lock:
            cur["v"] -= 1
        return {"repo": job["repo"], "verdict": "PASS"}

    jobs = [Job(repo=f"r{i}", needs_engines=("claude",)) for i in range(4)]
    res = JobScheduler(reg).schedule(jobs, runner)
    assert len(res.results) == 4
    assert peak["v"] == 2                      # exactly the cap: parallel but never exceeded


def test_scheduler_requeues_offline_node():
    reg = NodeRegistry()
    reg.register_remote("alpha", address="100.0.0.1", tailscale_ip="100.0.0.1", ssh_user="u",
                        capabilities=Capabilities(engines=("claude",)))
    reg.set_status("alpha", "online")
    reg.register_local("bravo", capabilities=Capabilities(engines=("claude",)))
    reg.set_executor("alpha", SSHExecutor(
        reg.get("alpha"), transport=SSHTransport(run_fn=lambda a, t: (255, "", "Connection refused"))))
    res = JobScheduler(reg).schedule(
        [Job(repo="j", needs_engines=("claude",), command="python -m pytest")], _runner)
    assert res.assignments.get("j") == "bravo"      # work not lost
    assert reg.state("alpha").status == "offline"
    assert any(q["from_node"] == "alpha" for q in res.requeued)


def test_scheduler_isolates_hard_error():
    reg = NodeRegistry()
    reg.register_local("n", capabilities=Capabilities(engines=("claude",)))

    def boom(job):
        if job["repo"] == "bad":
            raise ValueError("kapow")
        return {"repo": job["repo"], "verdict": "PASS"}

    res = JobScheduler(reg).schedule(
        [Job(repo="ok", needs_engines=("claude",)), Job(repo="bad", needs_engines=("claude",))], boom)
    assert res.assignments == {"ok": "n"}
    assert [e["repo"] for e in res.errors] == ["bad"]


# ── transport safety + parsing ──────────────────────────────────────


def test_assert_command_safe_blocks_force_push():
    for bad in ["git push --force origin main", "git push -f", "git push origin +main",
                "git push --force-with-lease"]:
        with pytest.raises(UnsafeCommandError):
            assert_command_safe(bad)


def test_assert_command_safe_blocks_bypass():
    for bad in ["SENTINEL_BYPASS=1 git push", "git commit --no-verify", "git commit --no-gpg-sign"]:
        with pytest.raises(UnsafeCommandError):
            assert_command_safe(bad)
    assert_command_safe("python -m pytest -q")            # ordinary command is fine


def test_build_ssh_argv_uses_key_path_not_material():
    node = Node(name="r", kind="remote", tailscale_ip="100.9.9.9", ssh_user="me",
                ssh_key_path="/keys/id_ed25519")
    argv = build_ssh_argv(node, "python -m pytest")
    assert argv[0] == "ssh"
    assert "-i" in argv and "/keys/id_ed25519" in argv      # path, not contents
    assert "me@100.9.9.9" in argv
    assert "BatchMode=yes" in " ".join(argv)                # never prompt for password


def test_build_ssh_argv_refuses_force_push():
    node = Node(name="r", kind="remote", tailscale_ip="100.9.9.9")
    with pytest.raises(UnsafeCommandError):
        build_ssh_argv(node, "git push --force")


def test_parse_result_line_takes_last_json():
    out = "log noise\n{\"repo\": \"X\", \"verdict\": \"PASS\"}\n"
    assert parse_result_line(out) == {"repo": "X", "verdict": "PASS"}
    assert parse_result_line("no json here") is None


# ── health prober ───────────────────────────────────────────────────


def test_prober_local_is_online():
    reg = NodeRegistry()
    reg.register_local("self", capabilities=Capabilities(engines=("claude",)))
    HealthProber(local_load_fn=lambda: 0.2).refresh(reg)
    assert reg.state("self").status == "online"


def test_prober_remote_ping_fail_is_offline():
    reg = NodeRegistry()
    reg.register_remote("r", address="100.0.0.5", tailscale_ip="100.0.0.5")
    prober = HealthProber(ping_fn=lambda host, t: False)
    [pr] = [p for p in prober.refresh(reg) if p.node == "r"]
    assert reg.state("r").status == "offline" and "ping" in pr.detail


def test_prober_remote_refreshes_capabilities():
    reg = NodeRegistry()
    reg.register_remote("r", address="100.0.0.6", tailscale_ip="100.0.0.6", ssh_user="u",
                        capabilities=Capabilities(data_volumes=("ubcma",)))
    probe_json = '{"cores": 16, "load": 0.5, "engines": ["claude", "agy"]}'
    prober = HealthProber(
        ping_fn=lambda host, t: True,
        transport=SSHTransport(run_fn=lambda argv, t: (0, probe_json, "")),
    )
    prober.refresh(reg)
    st = reg.state("r")
    assert st.status == "online" and st.load == 0.5
    eff = reg.effective_capabilities("r")
    assert set(eff.engines) == {"claude", "agy"} and eff.cores == 16
    assert eff.data_volumes == ("ubcma",)                   # config-trusted, preserved


def test_prober_remote_transient_is_offline():
    reg = NodeRegistry()
    reg.register_remote("r", address="100.0.0.7", tailscale_ip="100.0.0.7", ssh_user="u")
    prober = HealthProber(
        ping_fn=lambda host, t: True,
        transport=SSHTransport(run_fn=lambda argv, t: (255, "", "Connection refused")),
    )
    prober.refresh(reg)
    assert reg.state("r").status == "offline"


# ── onboarding ──────────────────────────────────────────────────────


def test_onboard_node_authorizes_probes(tmp_path):
    keyfile = tmp_path / "id_ed25519"
    keyfile.write_text("PRIVATE", encoding="utf-8")
    (tmp_path / "id_ed25519.pub").write_text("ssh-ed25519 AAAA test", encoding="utf-8")

    authorized = {}

    def fake_authorize(node, pubkey):
        authorized["host"] = node.ssh_host
        authorized["pub"] = pubkey.strip()
        return True, "authorized"

    prober = HealthProber(
        ping_fn=lambda host, t: True,
        transport=SSHTransport(run_fn=lambda argv, t: (0, '{"cores":8,"load":0.1,"engines":["claude"]}', "")),
    )
    res = onboard_node(
        name="pc3", host="100.0.0.30", ssh_user="mahmo", ssh_key_path=str(keyfile),
        authorize_fn=fake_authorize, prober=prober,
    )
    assert res.key_authorized and res.online
    assert authorized["host"] == "100.0.0.30"
    assert res.node.kind == "remote"


# ── config I/O ──────────────────────────────────────────────────────


def test_seed_config_loads_and_localizes_pc2():
    cfg = load_config(seed_config_path())
    assert cfg["local_node"] == "pc2"
    reg = build_registry(cfg, this_hostname="pc2")
    assert {n.name for n in reg.nodes} == {"pc2", "mahmood"}
    assert reg.get("pc2").kind == "local"        # localized
    assert reg.get("mahmood").kind == "remote"
    # data volume declared on pc2
    assert "ubcma" in reg.get("pc2").capabilities.data_volumes


def test_build_registry_remote_when_not_local_host():
    cfg = load_config(seed_config_path())
    reg = build_registry(cfg, this_hostname="some-other-box")
    # pc2 is still local because config pins local_node=pc2
    assert reg.get("pc2").kind == "local"


def test_add_node_to_config_roundtrip(tmp_path):
    cfg = {"local_node": "pc2", "nodes": []}
    node = Node(name="pc4", kind="remote", tailscale_ip="100.0.0.40", ssh_user="u")
    cfg2 = add_node_to_config(cfg, node)
    path = tmp_path / "nodes.json"
    path.write_text(json.dumps(cfg2), encoding="utf-8")
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert [n["name"] for n in reloaded["nodes"]] == ["pc4"]
