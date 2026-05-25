from __future__ import annotations

from overmind.telemetry import machine_health


def test_machine_health_snapshot_falls_back_when_psutil_missing(monkeypatch):
    monkeypatch.setattr(machine_health, "psutil", None)

    snapshot = machine_health.MachineHealthMonitor().snapshot(active_sessions=2)

    assert snapshot.active_sessions == 2
    assert snapshot.load_state == "unknown"
    assert snapshot.cpu_percent == 0.0
    assert snapshot.ram_percent == 0.0
    assert snapshot.swap_used_mb == 0.0
