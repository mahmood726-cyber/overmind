"""B1: retrofit must not alter bytes it did not mean to (newlines, bad encoding)."""
from __future__ import annotations

import pytest

from overmind.gates.retrofit import stage_corpus


@pytest.mark.parametrize("name,raw", [
    ("lf.md", b"plain note\nsecond line\n"),
    ("crlf.md", b"plain note\r\nsecond line\r\n"),
])
def test_claimless_file_roundtrips_byte_identical(tmp_path, name, raw):
    live = tmp_path / name
    live.write_bytes(raw)
    rep = stage_corpus([str(live)], str(tmp_path / "stage"), apply_in_place=True)
    assert rep.staged == 1
    assert live.read_bytes() == raw


def test_invalid_utf8_is_skipped_named_and_never_rewritten(tmp_path):
    raw = b"caf\xe9 \xff\xfe broken\r\n"
    live = tmp_path / "bad.md"
    live.write_bytes(raw)
    rep = stage_corpus([str(live)], str(tmp_path / "stage"), apply_in_place=True)
    assert rep.staged == 0
    assert rep.skipped_undecodable == [str(live)]
    assert live.read_bytes() == raw
    assert not (tmp_path / "stage" / "bad.md").exists()
