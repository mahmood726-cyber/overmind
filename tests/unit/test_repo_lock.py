"""Advisory repo-lock trip-tests (isolation #7).

TRIPS the guard: two lanes race for the same repo checkout; the second MUST be
refused with a clear error instead of silently sharing the tree.
"""
from __future__ import annotations

import pytest

from overmind.isolation.repo_lock import RepoLock, RepoLockedError, LockInfo


def test_second_lane_is_refused_with_holder_named(tmp_path):
    a = RepoLock(tmp_path, holder="lane-A").acquire()
    try:
        with pytest.raises(RepoLockedError) as ei:
            RepoLock(tmp_path, holder="lane-B").acquire()
        assert "lane-A" in str(ei.value)   # the loser is told WHO holds it
    finally:
        a.release()


def test_release_lets_the_next_lane_acquire(tmp_path):
    a = RepoLock(tmp_path, holder="lane-A")
    a.acquire()
    a.release()
    # now B can take it cleanly
    b = RepoLock(tmp_path, holder="lane-B").acquire()
    assert b._held is True
    b.release()


def test_context_manager_releases_on_exit(tmp_path):
    with RepoLock(tmp_path, holder="lane-A"):
        pass
    # released -> B acquires
    with RepoLock(tmp_path, holder="lane-B"):
        pass  # no RepoLockedError


def test_stale_lock_is_broken_loudly_but_live_lock_is_not(tmp_path):
    clock = {"t": 1000.0}
    a = RepoLock(tmp_path, holder="lane-A", stale_after=100.0, clock=lambda: clock["t"])
    a.acquire()  # stamped at t=1000

    # within TTL: a live holder must NOT be stolen
    clock["t"] = 1050.0
    with pytest.raises(RepoLockedError):
        RepoLock(tmp_path, holder="lane-B", stale_after=100.0, clock=lambda: clock["t"]).acquire()

    # past TTL: the stale lock is broken and B acquires
    clock["t"] = 2000.0
    b = RepoLock(tmp_path, holder="lane-B", stale_after=100.0, clock=lambda: clock["t"]).acquire()
    assert b._held is True
    info = LockInfo.from_path(tmp_path / ".overmind-lane.lock")
    assert info.holder == "lane-B"


def test_release_does_not_remove_another_holders_lock(tmp_path):
    # A acquires; a stale-break hands the lock to B; A.release() must not delete B's.
    clock = {"t": 1000.0}
    a = RepoLock(tmp_path, holder="lane-A", stale_after=10.0, clock=lambda: clock["t"])
    a.acquire()
    clock["t"] = 2000.0
    RepoLock(tmp_path, holder="lane-B", stale_after=10.0, clock=lambda: clock["t"]).acquire()
    a.release()  # A no longer owns it (B does) -> must be a no-op on B's lock
    info = LockInfo.from_path(tmp_path / ".overmind-lane.lock")
    assert info is not None and info.holder == "lane-B"
