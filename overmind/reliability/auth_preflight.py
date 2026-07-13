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

import time
from dataclasses import dataclass
from typing import Callable

from overmind.verification.cross_vendor_check import smoke_probe_codex_seats
from overmind.verification.judge_backends import JUDGE_ERROR, AgyBackend, ClaudeCodeBackend

# agy smoke: a real code-exec proof (SOP: `python -c "print(6*7)"` -> 42).
AGY_SMOKE_PROMPT = "Run python to compute 6*7 and reply with only the number."
# Claude smoke: a real `claude -p` completion on the subscription OAuth token.
CLAUDE_SMOKE_PROMPT = "Reply with exactly the token READY and nothing else."

# Markers that mean the CLI ran but auth failed (NOT a live seat).
_CLAUDE_AUTH_FAIL_MARKERS = ("not logged in", "invalid bearer", "401", "please run /login", "authenticate")

# --- Quota classification (A1/A3, agy-Gemini-pool 2026-07-12) --------------------
# A degraded probe is not one undifferentiated "dead". Per the recurring
# quota-misdiagnosis errors, distinguish:
#   * auth        — token revoked / not logged in (401): fix is re-auth, no reset.
#   * model_quota — THIS model's individual quota is exhausted while the vendor's
#                   OTHER model pools may be fully live (agy probed the Claude/
#                   GPT-OSS pool and declared "agy dead" while Gemini was 57%).
#                   NEVER infer another pool's death from this.
#   * credit_pool — workspace credit balance depleted: does NOT auto-reset; do not
#                   compute a cap+5h refill clock.
#   * rolling_5h  — 5h rolling plan limit: auto-recovers; a cap+5h clock IS valid.
# The classification keys off the vendor's own error string. Ordered most- to
# least-specific; "model/individual quota" must win over a bare "quota".
_QUOTA_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("auth", _CLAUDE_AUTH_FAIL_MARKERS),
    ("credit_pool", ("workspace owner", "refill", "out of credits", "credit balance")),
    ("rolling_5h", ("add credits", "5h", "rolling", "try again later", "resets in")),
    ("model_quota", ("individual quota", "model quota", "quota reached",
                     "quota exceeded", "per-model", "this model")),
    ("weekly_quota", ("weekly limit", "weekly quota", "weekly usage")),
)


def classify_degradation(response: str) -> str:
    """Classify WHY a vendor smoke failed from its own error text.

    Returns one of ``auth`` / ``credit_pool`` / ``rolling_5h`` / ``model_quota`` /
    ``weekly_quota`` / ``unknown``. ``model_quota`` is the pool-specific one: it is
    scoped to the model that was probed and must NOT be generalised to the vendor's
    other model pools. An empty/non-error response classifies ``unknown``.
    """
    low = (response or "").lower()
    for kind, markers in _QUOTA_SIGNALS:
        if any(m in low for m in markers):
            return kind
    return "unknown"


def preflight_claude(*, backend: object | None = None, probe_prompt: str = CLAUDE_SMOKE_PROMPT) -> VendorProbe:
    """Real headless `claude -p` smoke on the SUBSCRIPTION OAuth token (not an API
    key). Reports degraded on a missing/stale token (401 / not logged in) rather
    than a false 'logged in'."""
    backend = backend or ClaudeCodeBackend()
    available = getattr(backend, "available", None)
    if callable(available) and not available():
        return VendorProbe("claude", "oauth", False,
                           "no auth (set CLAUDE_CODE_OAUTH_TOKEN via `claude setup-token`)")
    resp = backend.query(probe_prompt)
    low = (resp or "").lower()
    if not resp or resp.startswith(JUDGE_ERROR) or any(m in low for m in _CLAUDE_AUTH_FAIL_MARKERS):
        return VendorProbe("claude", "oauth", False, (resp or "empty")[:120],
                           quota=classify_degradation(resp or ""))
    return VendorProbe("claude", "oauth", True, "ok")


@dataclass(slots=True)
class VendorProbe:
    vendor: str
    seat: str
    alive: bool
    detail: str = ""
    model: str = ""          # the exact model/pool this probe exercised ("" = default)
    quota: str = ""          # degradation class when not alive (see classify_degradation)

    def to_dict(self) -> dict:
        return {
            "vendor": self.vendor, "seat": self.seat, "alive": self.alive,
            "detail": self.detail, "model": self.model, "quota": self.quota,
        }

    @property
    def pool_key(self) -> str:
        """Identity of the exact pool probed — vendor:seat:model. Per-pool liveness
        is keyed on THIS, never on the bare vendor, so one exhausted pool never
        marks another pool of the same vendor dead."""
        return f"{self.vendor}:{self.seat}:{self.model or 'default'}"


def preflight_codex(
    seats: tuple[str, ...] | list[str] = ("mahmood", "noreen"),
    *,
    backends: dict[str, object] | None = None,
) -> list[VendorProbe]:
    """Real `codex exec` (effort=low) smoke of each seat — not `login status`."""
    return [
        VendorProbe("codex", p.seat, p.alive, p.detail,
                    quota="" if p.alive else classify_degradation(p.detail))
        for p in smoke_probe_codex_seats(seats, backends=backends)
    ]


def preflight_agy(
    *,
    backend: object | None = None,
    model: str = "pro",
    probe_prompt: str = AGY_SMOKE_PROMPT,
) -> VendorProbe:
    """Real `agy --print` smoke of ONE agy model pool — alive only if the driver
    returns a completion. Records the model probed so per-pool liveness is keyed on
    the exact pool. A failure is classified (model_quota vs auth vs …); a
    model_quota result is scoped to THIS model and never generalised."""
    backend = backend or AgyBackend(model=model)
    probed_model = getattr(backend, "model", model)
    available = getattr(backend, "available", None)
    if callable(available) and not available():
        return VendorProbe("agy", "default", False, "unavailable (agy driver not found)", model=probed_model)
    resp = backend.query(probe_prompt)
    if isinstance(resp, str) and resp.startswith(JUDGE_ERROR):
        return VendorProbe("agy", "default", False, resp[:120], model=probed_model,
                           quota=classify_degradation(resp))
    return VendorProbe("agy", "default", True, "ok", model=probed_model)


def preflight_agy_pools(
    models: tuple[str, ...] | list[str] = ("pro",),
    *,
    backends: dict[str, object] | None = None,
    probe_prompt: str = AGY_SMOKE_PROMPT,
) -> list[VendorProbe]:
    """Probe EACH agy model pool independently (agy-Gemini-pool 2026-07-12).

    The recurring error: probing one agy pool (an exhausted Claude/GPT-OSS model)
    and declaring the whole CLI dead while its Gemini pool was 57% live. Because
    agy `--print` ignores `--model` (the model is set in settings.json / the /model
    picker), a caller that wants a specific pool must configure the backend for
    that pool and probe it; this helper runs one independent probe per requested
    model so a per-pool map is produced and no pool's liveness is inferred from
    another's. Pass explicit ``backends={model: backend}`` in tests.
    """
    out: list[VendorProbe] = []
    for m in models:
        backend = (backends or {}).get(m)
        out.append(preflight_agy(backend=backend, model=m, probe_prompt=probe_prompt))
    return out


def preflight_all(
    *,
    codex_seats: tuple[str, ...] | list[str] = ("mahmood", "noreen"),
    codex_backends: dict[str, object] | None = None,
    agy_backend: object | None = None,
    claude_backend: object | None = None,
    include_claude: bool = True,
) -> list[VendorProbe]:
    """Preflight every vendor seat with a real exec smoke.

    Headless Claude (subscription OAuth) is a FIRST-CLASS live vendor here — it is
    NOT capped like Codex/agy, so it is the arm most likely to be live."""
    probes: list[VendorProbe] = []
    if include_claude:
        probes.append(preflight_claude(backend=claude_backend))
    probes.extend(preflight_codex(codex_seats, backends=codex_backends))
    probes.append(preflight_agy(backend=agy_backend))
    return probes


def live_vendors(probes: list[VendorProbe]) -> list[str]:
    """Distinct vendors with at least one live seat."""
    return sorted({p.vendor for p in probes if p.alive})


def degraded_seats(probes: list[VendorProbe]) -> list[VendorProbe]:
    """Seats that failed the real smoke — do NOT dispatch work to these."""
    return [p for p in probes if not p.alive]


def summarize(probes: list[VendorProbe]) -> str:
    live = [p.pool_key for p in probes if p.alive]
    dead = [f"{p.pool_key}({p.quota or 'dead'})" for p in probes if not p.alive]
    return f"auth preflight: live={live or 'none'} degraded={dead or 'none'}"


# --- Cheap TTL cache (no runtime token burn on the happy path) -------------------
# A real-exec preflight costs vendor tokens, so a lane that (re)checks liveness
# every dispatch must not re-burn a smoke each time. This memoises the last probe
# set for a short TTL: within the window the cached result is returned WITHOUT
# running any vendor exec. Keyed by the caller-supplied ``key`` so distinct probe
# configurations (different seats/models) don't collide. Single-process, no I/O.
_CACHE: dict[str, tuple[float, list[VendorProbe]]] = {}
DEFAULT_PROBE_TTL_SECONDS: float = 300.0


def preflight_cached(
    probe_fn: Callable[[], list[VendorProbe]],
    *,
    key: str = "all",
    ttl: float = DEFAULT_PROBE_TTL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    force: bool = False,
) -> list[VendorProbe]:
    """Return a cached probe set if a fresh one exists (<= ``ttl`` old), else run
    ``probe_fn`` once and cache it. ``force=True`` bypasses and refreshes the cache.

    This is the ergonomic default a dispatch path should call so liveness stays
    real-exec-verified WITHOUT burning a vendor token on every task — the smoke
    runs at most once per TTL window per key.
    """
    now = clock()
    if not force:
        hit = _CACHE.get(key)
        if hit is not None and (now - hit[0]) <= ttl:
            return hit[1]
    probes = probe_fn()
    _CACHE[key] = (now, probes)
    return probes


def clear_probe_cache() -> None:
    """Drop all cached probe sets (test hook / force a full re-probe)."""
    _CACHE.clear()
