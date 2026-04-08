"""Recipe model for procedural memory."""
from __future__ import annotations

from dataclasses import dataclass, field

from overmind.storage.models import utc_now


@dataclass
class Recipe:
    recipe_id: str
    failure_type: str
    pattern: str
    fix_description: str
    times_seen: int = 1
    times_resolved: int = 0
    confidence: float = 0.0
    last_seen: str = ""
    first_seen: str = ""
    example_project: str = ""

    def __post_init__(self):
        if not self.last_seen:
            self.last_seen = utc_now()
        if not self.first_seen:
            self.first_seen = self.last_seen
        self._update_confidence()

    def record_seen(self, date: str) -> None:
        self.times_seen += 1
        self.last_seen = date

    def record_resolved(self) -> None:
        self.times_resolved += 1
        self._update_confidence()

    def is_proven(self) -> bool:
        return self.times_seen >= 2 and self.confidence > 0

    def _update_confidence(self) -> None:
        if self.times_seen > 0:
            self.confidence = round(self.times_resolved / self.times_seen, 2)
