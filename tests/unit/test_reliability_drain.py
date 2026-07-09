"""Tests for drain robustness + monitoring (reliability items 1 & 2):
heartbeat files, cap-log, supervised loop (auto-restart + cap back-off), and the
truthful drain monitor. Clocks/sleeps injected — no real waiting.
"""
from __future__ import annotations

from overmind.reliability.cap_log import CapLog
from overmind.reliability.drain_monitor import DrainMonitor
from overmind.reliability.heartbeat import CAPPED, IDLE, RUNNING, STOPPED, HeartbeatFile
from overmind.reliability.supervised_loop import SupervisedLoop


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt


# --- heartbeat ------------------------------------------------------------------

def test_heartbeat_write_read_roundtrip(tmp_path):
    clk = _Clock()
    hbf = HeartbeatFile(tmp_path / "loop.hb.json", clock=clk)
    hbf.beat("claude-drain", RUNNING, detail="ok", iteration=3)
    hb = hbf.read()
    assert hb is not None
    assert hb.loop == "claude-drain" and hb.status == RUNNING and hb.iteration == 3


def test_heartbeat_staleness(tmp_path):
    clk = _Clock()
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    hbf.beat("l", RUNNING)
    assert hbf.is_stale(60) is False
    clk.advance(120)
    assert hbf.is_stale(60) is True


def test_heartbeat_missing_is_stale(tmp_path):
    hbf = HeartbeatFile(tmp_path / "nope.hb.json")
    assert hbf.read() is None
    assert hbf.is_stale(60) is True


def test_heartbeat_atomic_no_partial(tmp_path):
    # after a beat, no leftover .tmp files remain
    hbf = HeartbeatFile(tmp_path / "l.hb.json")
    hbf.beat("l", RUNNING)
    assert not list(tmp_path.glob("*.tmp*"))


# --- cap-log --------------------------------------------------------------------

def test_cap_log_active_and_reset(tmp_path):
    clk = _Clock(1000.0)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    cap.record_cap("codex-mahmood", "usage limit reached", reset_at=2000.0)
    assert "codex-mahmood" in cap.active_caps(now=1500.0)
    # reset_at passed => no longer active
    assert "codex-mahmood" not in cap.active_caps(now=2500.0)


def test_cap_log_explicit_reset_clears(tmp_path):
    clk = _Clock(1000.0)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    cap.record_cap("agy", "over capacity", reset_at=9999.0)
    assert "agy" in cap.active_caps(now=1500.0)
    clk.advance(100)
    cap.record_reset("agy")
    assert "agy" not in cap.active_caps(now=1600.0)


def test_cap_log_reset_timestamp_readable(tmp_path):
    cap = CapLog(tmp_path / "cap.jsonl", clock=_Clock(1000.0))
    ev = cap.record_cap("codex-noreen", "quota", reset_at=3000.0)
    active = cap.active_caps(now=1500.0)["codex-noreen"]
    assert active.reset_at == 3000.0
    assert ev.detected_at == 1000.0


# --- supervised loop ------------------------------------------------------------

def test_supervised_loop_heartbeats_each_iteration(tmp_path):
    clk = _Clock()
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    calls = {"n": 0}
    def worker():
        calls["n"] += 1
        return ["drained one task"]
    loop = SupervisedLoop("l", worker, heartbeat=hbf, cap_log=cap, clock=clk, sleep=lambda s: None)
    res = loop.run(max_iterations=3)
    assert calls["n"] == 3
    assert res.iterations == 3
    assert hbf.read().status == IDLE


def test_supervised_loop_auto_restarts_then_stops(tmp_path):
    clk = _Clock()
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    def worker():
        raise RuntimeError("boom")
    loop = SupervisedLoop("l", worker, heartbeat=hbf, cap_log=cap, max_restarts=2,
                          clock=clk, sleep=lambda s: None)
    res = loop.run(max_iterations=10)
    assert res.restarts == 3          # 2 allowed restarts, 3rd exceeds -> stop
    assert "max_restarts" in res.stopped_reason
    assert hbf.read().status == STOPPED


def test_supervised_loop_recovers_from_transient_error(tmp_path):
    clk = _Clock()
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    seq = iter([RuntimeError("blip"), ["ok"], ["ok"]])
    def worker():
        item = next(seq)
        if isinstance(item, Exception):
            raise item
        return item
    loop = SupervisedLoop("l", worker, heartbeat=hbf, cap_log=cap, max_restarts=3,
                          clock=clk, sleep=lambda s: None)
    res = loop.run(max_iterations=3)
    assert res.restarts == 1
    assert res.stopped_reason == "completed"


def test_supervised_loop_cap_backoff_records_and_sleeps(tmp_path):
    clk = _Clock(1000.0)
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    slept = []
    def worker():
        return ["Error: usage limit reached, try again later"]
    loop = SupervisedLoop(
        "claude-drain", worker, seat="claude", heartbeat=hbf, cap_log=cap,
        cap_backoff_seconds=1800.0, clock=clk, sleep=lambda s: slept.append(s),
    )
    res = loop.run(max_iterations=1)
    assert res.caps == 1
    assert slept == [1800.0]                       # slept to reset, not busy-loop
    # cap recorded with a reset timestamp; after back-off a reset is logged
    events = cap.events()
    assert any(e.get("kind") == "cap" and e["seat"] == "claude" for e in events)


# --- drain monitor (truthful, file-based) ---------------------------------------

def test_drain_monitor_sees_stale_loop(tmp_path):
    clk = _Clock(1000.0)
    hb_dir = tmp_path / "hb"
    HeartbeatFile(hb_dir / "alive.hb.json", clock=clk).beat("alive", RUNNING)
    old = HeartbeatFile(hb_dir / "dead.hb.json", clock=clk)
    old.beat("dead", RUNNING)
    clk.advance(2000)  # dead loop's last beat is now 2000s old
    HeartbeatFile(hb_dir / "alive.hb.json", clock=clk).beat("alive", RUNNING)  # refresh alive
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    mon = DrainMonitor(hb_dir, cap, stale_after_seconds=900, clock=clk)
    report = mon.report()
    assert "dead" in report.stale_loops
    assert "alive" not in report.stale_loops
    assert report.healthy is False


def test_drain_monitor_reports_capped_seats(tmp_path):
    clk = _Clock(1000.0)
    hb_dir = tmp_path / "hb"
    HeartbeatFile(hb_dir / "l.hb.json", clock=clk).beat("l", CAPPED)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    cap.record_cap("codex-mahmood", "usage limit", reset_at=5000.0)
    mon = DrainMonitor(hb_dir, cap, stale_after_seconds=900, clock=clk)
    report = mon.report()
    assert "codex-mahmood" in report.capped_seats
    assert report.capped_seats["codex-mahmood"]["reset_at"] == 5000.0


def test_drain_monitor_healthy_when_all_fresh(tmp_path):
    clk = _Clock(1000.0)
    hb_dir = tmp_path / "hb"
    HeartbeatFile(hb_dir / "l.hb.json", clock=clk).beat("l", RUNNING)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    mon = DrainMonitor(hb_dir, cap, stale_after_seconds=900, clock=clk)
    report = mon.report()
    assert report.healthy is True
    assert "1 loops" in report.headline()


def test_drain_monitor_empty_dir(tmp_path):
    cap = CapLog(tmp_path / "cap.jsonl")
    mon = DrainMonitor(tmp_path / "nohb", cap)
    assert mon.report().loops == []


def test_supervised_loop_out_of_credits_is_5h_autorefill_then_resumes(tmp_path):
    """'out of credits' => time-based 5h auto-refill cap (not terminal): stable
    reset_at = cap_start + 5h, re-probes on the back-off cadence, and auto-resumes
    (records reset) the moment a probe returns a real completion."""
    clk = _Clock(1000.0)
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)
    calls = {"n": 0}

    def worker():
        calls["n"] += 1
        if calls["n"] <= 2:
            return ["ERROR: Your workspace is out of credits. Ask your workspace owner to refill in order to continue."]
        return ["=== QA BATCH done ==="]

    def sleep(s):
        clk.advance(s)  # advance clock so re-probe cadence is observable

    loop = SupervisedLoop("l", worker, seat="seatA", heartbeat=hbf, cap_log=cap,
                          cap_backoff_seconds=900.0, clock=clk, sleep=sleep)
    res = loop.run(max_iterations=3)

    assert res.caps == 2
    caps = [e for e in cap.events() if e["kind"] == "cap"]
    resets = [e for e in cap.events() if e["kind"] == "reset"]
    # both cap events share the SAME 5h reset (cap_start 1000 + 18000)
    assert caps and all(abs(c["reset_at"] - 19000.0) < 1e-6 for c in caps), caps
    # slept the 900s re-probe cadence, NOT the full 5h (clock advanced only 1800 over 2 sleeps)
    assert abs(clk.t - 2800.0) < 1e-6, clk.t
    # recovered on the clean 3rd iteration
    assert len(resets) == 1
    assert "seatA" not in cap.active_caps(now=clk.t)


def test_supervised_loop_weekly_exhausted_after_5h5_still_capped(tmp_path):
    """If still out-of-credits past cap_start + 5.5h, reclassify as WEEKLY-EXHAUSTED:
    reset_at=None (weekly reset unknown), hourly probe, and weekly_exhausted flag set."""
    clk = _Clock(1000.0)
    hbf = HeartbeatFile(tmp_path / "l.hb.json", clock=clk)
    cap = CapLog(tmp_path / "cap.jsonl", clock=clk)

    def worker():
        return ["ERROR: Your workspace is out of credits. Ask your workspace owner to refill in order to continue."]

    def sleep(s):
        clk.advance(s)  # each cap sleep advances the clock

    loop = SupervisedLoop("l", worker, seat="seatA", heartbeat=hbf, cap_log=cap,
                          cap_backoff_seconds=900.0, credit_refill_seconds=5*3600.0,
                          weekly_reclassify_seconds=5.5*3600.0, weekly_probe_seconds=3600.0,
                          clock=clk, sleep=sleep)
    # run enough iterations that elapsed passes 5.5h (900s sleeps => ~22 iters to reach 19800s)
    res = loop.run(max_iterations=40)

    assert res.weekly_exhausted is True
    caps = [e for e in cap.events() if e["kind"] == "cap"]
    # early caps are 5h-window (reset_at set); late caps are weekly (reset_at None)
    assert any(c["reset_at"] is not None for c in caps), "expected 5h-window caps first"
    weekly = [c for c in caps if c["reset_at"] is None]
    assert weekly, "expected weekly-exhausted caps (reset_at None) after 5.5h"
    assert "WEEKLY-EXHAUSTED" in weekly[-1]["cap_message"]
