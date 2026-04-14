"""Tests for DeterminismWitness + nondeterminism normalization."""
from __future__ import annotations

import sys

from overmind.verification.witnesses import (
    DeterminismWitness,
    _normalize_for_determinism,
)


def test_normalize_strips_iso_timestamps():
    raw = "start 2026-04-14T10:45:33Z -> end 2026-04-14T10:45:37.123+00:00"
    normalized = _normalize_for_determinism(raw)
    assert "2026-04-14" not in normalized
    assert "<TS>" in normalized


def test_normalize_strips_elapsed_durations():
    raw = "tests passed in 1.234s (elapsed=0.456)"
    normalized = _normalize_for_determinism(raw)
    assert "1.234s" not in normalized
    assert "<DUR>" in normalized


def test_normalize_strips_hex_addresses():
    raw = "at 0x7ffa1234 in function foo"
    normalized = _normalize_for_determinism(raw)
    assert "0x7ffa1234" not in normalized
    assert "<ADDR>" in normalized


def test_determinism_witness_passes_on_deterministic_output(tmp_path):
    script = tmp_path / "det.py"
    script.write_text("print('stable-output')\n", encoding="utf-8")

    witness = DeterminismWitness(timeout=10)
    result = witness.run(f'"{sys.executable}" "{script}"', str(tmp_path))

    assert result.verdict == "PASS"
    assert "identical normalized output" in result.stdout


def test_determinism_witness_passes_despite_timestamp_noise(tmp_path):
    script = tmp_path / "noisy.py"
    script.write_text(
        "import datetime\n"
        "print('start:', datetime.datetime.now().isoformat())\n"
        "print('value: 42')\n",
        encoding="utf-8",
    )

    witness = DeterminismWitness(timeout=10)
    result = witness.run(f'"{sys.executable}" "{script}"', str(tmp_path))

    # Timestamps differ between runs but normalization maps them to <TS>.
    assert result.verdict == "PASS"


def test_determinism_witness_fails_on_real_nondeterminism(tmp_path):
    import random as _random
    counter = tmp_path / "counter.txt"
    script = tmp_path / "flaky.py"
    script.write_text(
        "import random, sys\n"
        "print('value:', random.randint(0, 10_000_000))\n",
        encoding="utf-8",
    )
    _ = _random, counter  # quiet linters

    witness = DeterminismWitness(timeout=10)
    result = witness.run(f'"{sys.executable}" "{script}"', str(tmp_path))

    assert result.verdict == "FAIL"
    assert "Hashes differ" in result.stdout


def test_determinism_witness_blocks_unsafe_command(tmp_path):
    witness = DeterminismWitness(timeout=5)
    result = witness.run("definitely-not-a-real-binary", str(tmp_path))

    assert result.verdict == "FAIL"
    assert "not allowlisted" in result.stderr or "Blocked" in result.stderr
