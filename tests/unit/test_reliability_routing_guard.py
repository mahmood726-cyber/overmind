"""Tests for the F:/E: routing guard (reliability item 5)."""
from __future__ import annotations

import pytest

from overmind.reliability.routing_guard import (
    RoutingViolation,
    assert_fs_routing,
    check_fs_routing,
    local_fs_drives_referenced,
    requires_local_fs,
)


def test_detects_f_and_e_drives():
    assert local_fs_drives_referenced(r"python F:\overmind\run.py") == {"F"}
    assert local_fs_drives_referenced("read E:/data/aact.csv") == {"E"}
    assert local_fs_drives_referenced("F:/a and E:\\b") == {"E", "F"}


def test_ignores_c_drive_and_relative():
    assert local_fs_drives_referenced(r"python C:\tool\x.py") == set()
    assert requires_local_fs("python ./run.py --out data/x") is False


def test_no_local_fs_always_ok():
    d = check_fs_routing("echo hello", is_sandbox=True, is_code_task=False)
    assert d.requires_local_fs is False
    assert d.ok is True


def test_sandbox_rejected_for_local_fs():
    d = check_fs_routing(r"python F:\overmind\daily.py", is_sandbox=True)
    assert d.ok is False
    assert "Cowork sandbox" in d.violation
    assert d.needs_drives == ["F"]


def test_non_code_task_rejected():
    d = check_fs_routing(r"summarize F:\journal\paper.md", is_code_task=False, node_fs_drives=("F",))
    assert d.ok is False
    assert "CODE task" in d.violation


def test_node_missing_drive_rejected():
    d = check_fs_routing(r"python F:\x.py", node_name="laptop", node_fs_drives=("C",), is_code_task=True)
    assert d.ok is False
    assert "cannot reach" in d.violation


def test_valid_route_ok():
    d = check_fs_routing(
        r"python F:\overmind\run.py", node_name="pc1",
        node_fs_drives=("C", "F", "E"), is_code_task=True, is_sandbox=False,
    )
    assert d.ok is True
    assert d.needs_drives == ["F"]


def test_drive_letters_with_colon_suffix_accepted():
    d = check_fs_routing(r"python F:\x.py", node_fs_drives=("F:",))
    assert d.ok is True


def test_assert_raises_on_violation():
    with pytest.raises(RoutingViolation):
        assert_fs_routing(r"python F:\x.py", is_sandbox=True)


def test_assert_returns_decision_when_ok():
    d = assert_fs_routing("python run.py")
    assert d.ok is True
