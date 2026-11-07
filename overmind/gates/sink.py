"""The channel OWNS the physical write — runtime enforcement, not a lint.

Part III ended on the honest top residual, named by both external families in all
four rounds: *"the channel validates and renders; it does not yet OWN the physical
OS write."* The type sink (``channel.emit``) proves a number is the only TYPED path
to a ``Rendered`` — but any of the 18 legacy world-claim files could still call
``open(path, "w").write(f"{raw}")`` and put an un-gated number on disk. A gate you
can walk around is a suggestion.

This module closes that at the layer the bypass actually lives: the OS call. It
installs a ``sys.addaudithook`` that fires on the ``open`` audit event (raised by
``io.open`` / the builtin ``open`` / ``os.open`` / ``os.fdopen``). When a WRITE is
opened against a **registered deliverable root** — the artifacts Kampala sees: the
RapidMeta app pages, the Tuesday slides, the deliverable ``.md`` files — the hook
refuses it UNLESS the write is happening inside a channel-owned ``authorized_write``
context. The channel enters that context around ``write_report``; nothing else does.

So the physical write to a protected artifact has exactly one origin: the channel.
A lane that tries to write a raw number to a deliverable path is blocked at the
``open`` call, before a byte reaches disk — regardless of whether that lane is one
of the 18, was added yesterday, or never imported the gates. That is ownership,
not enforcement-by-remembering-to-call.

HONEST LIMITS (named, not hidden — dogfooding F1):
  * The hook covers the ``open`` audit event. A determined bypass — ``os.write(fd)``
    on a file descriptor opened BEFORE the root was registered, a ``ctypes`` syscall,
    or a child ``subprocess`` — is not intercepted. It raises the bar from "any
    print() escapes" to "only a deliberate low-level syscall escapes," and pairs
    with the static ``enforcement`` scanner that reads the source. Both, not either.
  * ``print()`` to stdout is NOT a file ``open`` and is not caught here (wrapping
    process-wide stdout would break all logging). stdout world-claims remain the
    static ratchet's job; see the named residual in the report.
  * Audit hooks cannot be uninstalled once added (CPython). We therefore install
    lazily and keep the hook cheap: it does nothing unless a protected root is set.
"""
from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field


class SinkViolation(RuntimeError):
    """A raw write to a protected deliverable path happened outside the channel's
    owned write context. Nothing reached disk."""


@dataclass
class _Violation:
    path: str
    mode: str


def _write_intent(mode: str, flags: int) -> bool:
    """True if this open is a write. Checks both the text mode string (builtin
    open) and the raw O_* flags (os.open)."""
    if mode:
        if any(ch in mode for ch in ("w", "a", "x", "+")):
            return True
    if flags:
        # O_WRONLY=1, O_RDWR=2, O_CREAT, O_APPEND, O_TRUNC all imply write
        wr = os.O_WRONLY | os.O_RDWR
        cr = getattr(os, "O_CREAT", 0) | getattr(os, "O_APPEND", 0) | getattr(os, "O_TRUNC", 0)
        if (flags & wr) or (flags & cr):
            return True
    return False


class SinkGuard:
    """Owns the physical write to registered deliverable roots via an audit hook.

    One per process; ``SINK`` is the default. ``protect(root)`` registers a
    directory tree whose writes must come through the channel. ``authorized_write()``
    is the context the channel (and ONLY the channel) enters to perform the write."""

    def __init__(self):
        self._roots: list[str] = []
        self._local = threading.local()
        self._installed = False
        self.violations: list[_Violation] = []
        self._lock = threading.Lock()

    # -- registration --------------------------------------------------------
    def protect(self, root: str) -> "SinkGuard":
        """Register a deliverable root. Writes under it are channel-only from now on.
        Installs the audit hook on first use (lazy — a process that never protects
        a root pays nothing)."""
        ap = os.path.realpath(root)   # realpath so symlinked roots compare correctly
        with self._lock:
            if ap not in self._roots:
                self._roots.append(ap)
        self._install()
        return self

    def clear(self) -> None:
        """Stop protecting all roots (the hook stays installed but goes inert).
        Used by tests; production never calls this."""
        with self._lock:
            self._roots = []

    @property
    def protected_roots(self) -> tuple[str, ...]:
        return tuple(self._roots)

    # -- the owned write context --------------------------------------------
    @property
    def _is_authorized(self) -> bool:
        return getattr(self._local, "depth", 0) > 0

    @contextmanager
    def authorized_write(self):
        """The ONE sanctioned window in which a protected path may be written. The
        channel enters it around its physical write; a raw lane never does, so a raw
        lane's ``open(...,'w')`` on a protected path is refused. Thread-local and
        re-entrant so nested channel writes are fine, and one thread's authorization
        never leaks to another.

        NAMED RESIDUAL (Codex round-4): this context is public, so in-process code can
        enter it and then write raw (``with SINK.authorized_write(): Path(p).write_text(...)``).
        Combined with the ``open``/``rename`` hook this stops the accidental and the
        naive-malicious lane, but it is NOT a same-process security boundary — the hard
        guarantee is a separate privileged writer process (agy's finding)."""
        self._local.depth = getattr(self._local, "depth", 0) + 1
        try:
            yield
        finally:
            self._local.depth -= 1

    # -- the hook ------------------------------------------------------------
    def _under_protected_root(self, path: str) -> bool:
        if not self._roots or not path:
            return False
        try:
            # realpath, NOT abspath: Codex round-4 caught that a symlink/junction whose
            # target is inside a protected root would pass an abspath containment check
            # but point elsewhere (or vice-versa). Resolve links before comparing.
            ap = os.path.realpath(path)
        except (ValueError, OSError):
            return False
        for root in self._roots:
            # os.path.commonpath is the safe containment check (prefix-string
            # matching would treat /a/bc as under /a/b).
            try:
                if os.path.commonpath([ap, root]) == root:
                    return True
            except ValueError:
                continue  # different drive on Windows -> not under root
        return False

    def _hook(self, event: str, args) -> None:
        if not self._roots:
            return
        # Codex round-4: os.replace()/os.rename() moves a file written OUTSIDE the root
        # INTO a protected path without ever firing an 'open' on the destination. Guard
        # the rename destination too (audit event 'os.rename', args (src, dst)).
        if event == "os.rename":
            # audit args: (src, dst, src_dir_fd, dst_dir_fd)
            dst = args[1] if len(args) > 1 else None
            dfd = args[3] if len(args) > 3 else None
            self._check_write(dst, "rename->dst", dir_fd=dfd)
            return
        # Codex round-5: os.link (hardlink) / os.symlink create a protected-path entry
        # pointing at content written elsewhere — the file's bytes never pass an 'open'
        # under the root. Guard the link/symlink destination too. Audit args are
        # (src, dst, src_dir_fd, dst_dir_fd) for link, (src, dst, dir_fd) for symlink.
        if event == "os.link":
            self._check_write(args[1] if len(args) > 1 else None, event,
                              dir_fd=args[3] if len(args) > 3 else None)
            return
        if event == "os.symlink":
            self._check_write(args[1] if len(args) > 1 else None, event,
                              dir_fd=args[2] if len(args) > 2 else None)
            return
        if event != "open":
            return
        # audit 'open' args are (path, mode, flags)
        path, mode, flags = (tuple(args) + (None, None, None))[:3]
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        mode = mode if isinstance(mode, str) else ""
        flags = flags if isinstance(flags, int) else 0
        if not _write_intent(mode, flags):
            return
        self._check_write(path, mode or f"flags={flags}")

    def _resolve_dir_fd(self, path: str, dir_fd) -> str | None:
        """Codex round-6: a *_dir_fd-relative destination is a cwd-relative name to our
        check, so it misses the protected root. Best-effort resolve the fd to its dir
        (Linux /proc/self/fd) and join. If the fd cannot be resolved but dir_fd IS a
        real fd and roots are protected, return a sentinel so the caller fails CLOSED
        rather than waving a possibly-protected write through."""
        if not isinstance(dir_fd, int) or dir_fd < 0:
            return None
        if os.path.isabs(path):
            return None  # absolute path ignores dir_fd
        try:
            base = os.readlink(f"/proc/self/fd/{dir_fd}")
            return os.path.join(base, path)
        except (OSError, ValueError):
            return "\x00UNRESOLVED"  # can't resolve -> caller fails closed

    def _check_write(self, path, mode: str, *, dir_fd=None) -> None:
        """Shared refusal path for a write to `path` (an open in write mode, or a
        rename destination). Raises unless inside the channel's authorized context."""
        if not isinstance(path, (str, bytes, os.PathLike)):
            return
        if isinstance(path, bytes):
            try:
                path = os.fsdecode(path)
            except Exception:
                return
        p = os.fspath(path)
        if dir_fd is not None:
            resolved = self._resolve_dir_fd(p, dir_fd)
            if resolved == "\x00UNRESOLVED":
                # a dir_fd we cannot resolve while roots are protected -> fail closed
                if self._roots and not self._is_authorized:
                    raise SinkViolation(
                        f"REFUSED: write via an unresolvable dir_fd (relative {p!r}) while "
                        f"deliverable roots are protected — failing closed rather than "
                        f"risk a dir_fd-relative write into a protected root.")
                return
            if resolved:
                p = resolved
        if not self._under_protected_root(p):
            return
        if self._is_authorized:
            return
        self.violations.append(_Violation(path=p, mode=mode))
        raise SinkViolation(
            f"REFUSED: raw write to protected deliverable path {p!r} "
            f"(mode {mode}) outside the channel. A world-claim artifact may only be "
            f"written through overmind.gates.channel (which enters SINK.authorized_write). "
            f"Route the number through emit()/write_report — do not open/rename the file "
            f"yourself."
        )

    def _install(self) -> None:
        if self._installed:
            return
        # addaudithook is irreversible; install once, keep it inert until a root is set.
        sys.addaudithook(self._hook)
        self._installed = True


# The process-wide sink owner. The channel imports THIS.
SINK = SinkGuard()


# The deliverable roots Kampala actually sees, in priority order (app pages first).
# A caller seals these once at startup; the sweep/retrofit uses the same list so the
# thing we PROTECT and the thing we AUDIT are the same set (no drift).
def default_deliverable_roots() -> list[str]:
    cands = [
        r"C:\Projects",            # deliverable .md + slides live here
        r"F:\rapidmeta-finerenone",  # a RapidMeta app-page tree (example)
    ]
    return [c for c in cands if os.path.isdir(c)]
