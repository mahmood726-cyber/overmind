"""Embedders for the optional RAG layer.

Two backends, both dependency-free at import time:

  - HashingEmbedder: deterministic feature-hashing bag-of-tokens into a fixed
    dimension, L2-normalised. No third-party packages, no network, no model
    download — so the RAG layer always *works* even with nothing installed.
    Quality is keyword-ish (sufficient for grounding recall + tests), not
    semantic.
  - LocalEmbedder: calls a local Ollama-style ``/api/embeddings`` endpoint
    (Gemma/Qwen) for real semantic vectors. Used only when explicitly selected
    and reachable; falls back to hashing on any error so it never hard-breaks.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Callable, Protocol

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


def _l2_normalise(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class HashingEmbedder:
    """Deterministic feature-hashing embedder (no dependencies)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        return _l2_normalise(vec)


class LocalEmbedder:
    """Embeddings via a local Ollama-style endpoint. Falls back to hashing."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        endpoint: str = "http://localhost:11434/api/embeddings",
        dim: int = 256,
        timeout: int = 30,
        http: Callable[[str, bytes, int], str] | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.dim = dim
        self.timeout = timeout
        self._http = http
        self._fallback = HashingEmbedder(dim=dim)

    def embed(self, text: str) -> list[float]:
        payload = json.dumps({"model": self.model, "prompt": text}).encode("utf-8")
        try:
            raw = (self._http or _default_http)(self.endpoint, payload, self.timeout)
            data = json.loads(raw)
            vec = data.get("embedding")
            if isinstance(vec, list) and vec:
                self.dim = len(vec)
                return _l2_normalise([float(x) for x in vec])
        except Exception:  # noqa: BLE001 — local runtime optional, degrade
            pass
        return self._fallback.embed(text)


def _default_http(url: str, payload: bytes, timeout: int) -> str:
    from urllib.request import Request, urlopen

    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — localhost only
        return resp.read().decode("utf-8")


def build_embedder(backend: str | None = None, dim: int = 256) -> Embedder:
    """Build an embedder by name (env OVERMIND_EMBED_BACKEND, default hashing)."""
    if backend is None:
        backend = os.environ.get("OVERMIND_EMBED_BACKEND", "hashing")
    backend = (backend or "hashing").strip().lower()
    if backend == "local":
        return LocalEmbedder(dim=dim)
    return HashingEmbedder(dim=dim)
