from __future__ import annotations

from collections import Counter
import re


class LoopDetector:
    _divider_pattern = re.compile(r"^[=\-_*#~]{4,}$")

    def _is_substantive(self, line: str) -> bool:
        stripped = line.strip().lower()
        if not stripped:
            return False
        if self._divider_pattern.fullmatch(stripped):
            return False
        return any(character.isalnum() for character in stripped)

    def detect(self, lines: list[str], threshold: int = 3) -> bool:
        normalized = [line.strip().lower() for line in lines if self._is_substantive(line)]
        if len(normalized) < threshold:
            return False
        counts = Counter(normalized)
        if any(count >= threshold for count in counts.values()):
            return True
        trailing = normalized[-threshold:]
        return len(set(trailing)) == 1
