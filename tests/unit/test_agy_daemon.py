"""agy stale-daemon reaper — trip-tests (#5). Injected process list/kill: no real
processes touched. TRIPS the reaper on stale daemons; proves a fresh daemon and a
non-agy process are never killed (the false-positive we must avoid)."""
from __future__ import annotations

from overmind.reliability.agy_daemon import find_stale_daemons, reap_stale_daemons


def _procs(now):
    return [
        {"pid": 100, "name": "language_server.exe", "create_time": now - 600},  # stale
        {"pid": 101, "name": "language_server.exe", "create_time": now - 30},   # fresh
        {"pid": 102, "name": "python.exe", "create_time": now - 9999},          # not agy
        {"pid": 103, "name": "LANGUAGE_SERVER.EXE", "create_time": now - 700},  # stale (case)
    ]


def test_find_stale_daemons_selects_only_old_agy():
    now = 10_000.0
    stale = find_stale_daemons(_procs(now), now=now, min_age=300.0)
    assert {p["pid"] for p in stale} == {100, 103}  # fresh 101 + python 102 excluded


def test_reap_kills_stale_and_spares_fresh():
    now = 10_000.0
    killed = []
    reaped = reap_stale_daemons(
        list_procs=lambda: _procs(now),
        kill=lambda pid: (killed.append(pid) or True),
        now=now, min_age=300.0,
    )
    assert set(reaped) == {100, 103}
    assert 101 not in killed and 102 not in killed  # fresh + non-agy spared


def test_reap_reports_only_successful_kills():
    now = 10_000.0
    # kill fails for pid 100, succeeds for 103
    reaped = reap_stale_daemons(
        list_procs=lambda: _procs(now),
        kill=lambda pid: pid == 103,
        now=now, min_age=300.0,
    )
    assert reaped == [103]


def test_no_daemons_is_noop():
    assert reap_stale_daemons(list_procs=lambda: [], kill=lambda p: True, now=0.0) == []
