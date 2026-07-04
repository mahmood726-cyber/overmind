"""Vendor auth preflight (reliability — item 3).

``codex login status`` / session-presence checks LIE: a seat can report "logged
in" while its refresh token is 401-revoked, so work dispatched to it silently
fails. The only truthful check is to actually run the vendor: a real
``codex exec`` (low effort) and a real ``agy --print`` smoke. This module runs
those before dispatching vendor work and reports each seat live / degraded.

Reuses the Codex seat smoke from ``cross_vendor_check`` and the ``AgyBackend``
``--print`` path. Backends are injectable so it is testable without a CLI.
The CODEX_HOME-per-seat + node2_ed25519 SSH + logout->login recipe is codified in
``harness/AUTH_PREFLIGHT_RUNBOOK.md`` and runnable via ``scripts/auth_preflight.py``.
"""
from __future__ import annotations

from dataclasses import dataclass

from overmind.verification.cross_vendor_check import smoke_probe_codex_seats
from overmind.verification.judge_backends import JUDGE_ERROR, AgyBackend

# agy smoke: a real code-exec proof (SOP: `python -c "print(6*7)"` -> 42).
AGY_SMOKE_PROMPT = "Run python to compute 6*7 and reply with only the number."


@dataclass(slots=True)
class VendorProbe:
    vendor: str
    seat: str
    alive: bool
    detail: str = ""

    def to_dict(self) -> dict:
        return {"vendor": self.vendor, "seat": self.seat, "alive": self.alive, "detail": self.detail}


def preflight_codex(
    seats: tuple[str, ...] | list[str] = ("mahmood", "noreen"),
    *,
    backends: dict[str, object] | None = None,
) -> list[VendorProbe]:
    """Real `codex exec` (effort=low) smoke of each seat — not `login status`."""
    return [
        VendorProbe("codex", p.seat, p.alive, p.detail)
        for p in smoke_probe_codex_seats(seats, backends=backends)
    ]


def preflight_agy(*, backend: object | None = None, probe_prompt: str = AGY_SMOKE_PROMPT) -> VendorProbe:
    """Real `agy --print` smoke — alive only if the driver returns a completion."""
    backend = backend or AgyBackend()
    available = getattr(backend, "available", None)
    if callable(available) and not available():
        return VendorProbe("agy", "default", False, "unavailable (agy driver not found)")
    resp = backend.query(probe_prompt)
    if isinstance(resp, str) and resp.startswith(JUDGE_ERROR):
        return VendorProbe("agy", "default", False, resp[:120])
    return VendorProbe("agy", "default", True, "ok")


def preflight_all(
    *,
    codex_seats: tuple[str, ...] | list[str] = ("mahmood", "noreen"),
    codex_backends: dict[str, object] | None = None,
    agy_backend: object | None = None,
) -> list[VendorProbe]:
    """Preflight every non-Claude vendor seat with a real exec smoke."""
    probes = preflight_codex(codex_seats, backends=codex_backends)
    probes.append(preflight_agy(backend=agy_backend))
    return probes


def live_vendors(probes: list[VendorProbe]) -> list[str]:
    """Distinct vendors with at least one live seat."""
    return sorted({p.vendor for p in probes if p.alive})


def degraded_seats(probes: list[VendorProbe]) -> list[VendorProbe]:
    """Seats that failed the real smoke — do NOT dispatch work to these."""
    return [p for p in probes if not p.alive]


def summarize(probes: list[VendorProbe]) -> str:
    live = [f"{p.vendor}:{p.seat}" for p in probes if p.alive]
    dead = [f"{p.vendor}:{p.seat}" for p in probes if not p.alive]
    return f"auth preflight: live={live or 'none'} degraded={dead or 'none'}"
