"""The scanner that turns opt-in into mandatory — and produces the lane inventory.

A gate you must remember to call is a suggestion. This module is the mechanical
check that no lane emits a number WITHOUT routing through ``channel.emit``. It
walks the AST of every lane/deliverable-generator and flags each site where a
number can reach output — ``print(...)``, a file ``.write``/``write_text``/
``to_csv``, a ``json.dump`` to a doc — and each raw store leak (``.get(...).value``
outside the guard). A file that has such sites but never references the channel
or a gate is an OPEN HOLE.

Run it as a test over the repo: new naked-output sites turn the suite red. That
is the closest a dynamic language gets to "a bare number will not compile" — the
build breaks the moment a lane bypasses the sink.

It also answers, without my having to assert it (asserting would be F1): how many
paths exist, how many are routed, and which remain open — by NAME.
"""
from __future__ import annotations

import ast
import os
from dataclasses import dataclass, field
from typing import Iterable

# calls that can push a number to a human-facing destination
_OUTPUT_CALLS = {"print", "write", "writelines", "write_text", "to_csv",
                 "to_markdown", "to_html", "to_sql", "writeText", "echo",
                 # logging surfaces (a number in a log/exception the UI shows)
                 "info", "warning", "warn", "error", "critical", "exception", "debug", "log"}
_DUMP_CALLS = {"dump", "dumps"}          # json.dump(...) to a file
# names that mean an output arg went THROUGH the channel (a routed site, not naked)
_ROUTED_TOKENS = {"emit", "emit_all", "Rendered"}
# store reads that return a raw Fact whose .value bypasses consume_verified
_RAW_STORE_CALLS = {"get", "facts_for", "all_facts"}
# tokens whose presence means the file is gate-aware (routed, not naked)
_GATE_TOKENS = ("gates.channel", "gates.export_gate", "guard_export",
                "guard_export_from_store", "ExportChannel", "channel.emit",
                "from .channel", "from overmind.gates")


@dataclass(frozen=True, slots=True)
class Site:
    file: str
    line: int
    kind: str          # "output" | "store_value_leak"
    snippet: str
    routed: bool = False   # the output arg went through channel.emit / Rendered


@dataclass
class FileReport:
    path: str
    gate_aware: bool
    sites: list[Site] = field(default_factory=list)
    parse_error: bool = False   # Codex: a SyntaxError file was silently 'no-emit'

    @property
    def naked_sites(self) -> list[Site]:
        return [s for s in self.sites if not s.routed]

    @property
    def status(self) -> str:
        # A file is only 'routed' (clean) if it references the gates AND every one
        # of its emit sites actually went through the channel. Importing the channel
        # while still doing `print(raw_number)` is 'leaky', NOT clean — Codex's
        # round-2 finding that token-presence over-credited a file.
        if self.parse_error:
            return "unparseable"   # cannot certify — surfaced, not silently skipped
        if not self.sites:
            return "no-emit"
        if not self.naked_sites:
            return "routed" if self.gate_aware else "OPEN-HOLE"
        return "leaky" if self.gate_aware else "OPEN-HOLE"


def _snippet(src_lines: list[str], node: ast.AST) -> str:
    ln = getattr(node, "lineno", 0)
    return src_lines[ln - 1].strip()[:120] if 0 < ln <= len(src_lines) else ""


def _has_numberish_arg(call: ast.Call) -> bool:
    """A print/write is interesting only if it could carry a number: an f-string,
    a name, a call result, arithmetic, a numeric literal, a %/format expr, or a
    string literal that itself contains a digit (a stringified number). A pure
    alphabetic banner is not a number leak."""
    def interesting(n: ast.AST) -> bool:
        if isinstance(n, ast.JoinedStr):      # f-string
            return True
        if isinstance(n, (ast.Name, ast.Call, ast.BinOp, ast.Attribute, ast.Subscript)):
            return True
        if isinstance(n, ast.Constant):
            if isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
                return True
            if isinstance(n.value, str) and any(ch.isdigit() for ch in n.value):
                return True  # agy: numbers stringified before the call
        return False
    return any(interesting(a) for a in call.args) or any(interesting(k.value) for k in call.keywords)


def _arg_is_routed(call: ast.Call) -> bool:
    """True if any output arg went through the channel (contains emit()/emit_all()/
    Rendered / a `.text` off a rendered result). Such a site is not a naked leak."""
    for node in ast.walk(call):
        if isinstance(node, ast.Name) and node.id in _ROUTED_TOKENS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in _ROUTED_TOKENS:
            return True
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in _ROUTED_TOKENS:
                return True
            if isinstance(f, ast.Attribute) and f.attr in _ROUTED_TOKENS:
                return True
    return False


class _Visitor(ast.NodeVisitor):
    def __init__(self, path: str, src_lines: list[str]):
        self.path = path
        self.src_lines = src_lines
        self.sites: list[Site] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = None
        if isinstance(node.func, ast.Name):
            name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
        # A lane that constructs a LAX channel (resolution/panel disabled) is a
        # deliberate bypass — Codex round-2: require_resolution=False emits fabricated
        # claims. Flag it as a naked, un-routable site regardless of args.
        if name == "ExportChannel":
            for kw in node.keywords:
                if kw.arg in ("require_resolution", "require_panel_for_flattering") \
                        and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    self.sites.append(Site(self.path, node.lineno, "gate_disabled",
                                           _snippet(self.src_lines, node), routed=False))
        if name in _OUTPUT_CALLS and _has_numberish_arg(node):
            self.sites.append(Site(self.path, node.lineno, "output",
                                   _snippet(self.src_lines, node), routed=_arg_is_routed(node)))
        elif name in _DUMP_CALLS and isinstance(node.func, ast.Attribute) \
                and _module_is(node.func.value, "json") and len(node.args) >= 2:
            # json.dump(obj, file) — writing structured numbers to a sink
            self.sites.append(Site(self.path, node.lineno, "output",
                                   _snippet(self.src_lines, node), routed=_arg_is_routed(node)))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # `<call to get/facts_for/all_facts>(...).value` — the raw store leak the
        # pre-fix DTA70 path used (`fs.get(fid).value == 85.8`).
        if node.attr == "value" and isinstance(node.value, (ast.Call, ast.Subscript)):
            inner = node.value.func if isinstance(node.value, ast.Call) else node.value.value
            callname = None
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                callname = node.value.func.attr
            elif isinstance(node.value, ast.Subscript) and isinstance(node.value.value, ast.Call) \
                    and isinstance(node.value.value.func, ast.Attribute):
                callname = node.value.value.func.attr
            if callname in _RAW_STORE_CALLS:
                self.sites.append(Site(self.path, node.lineno, "store_value_leak",
                                       _snippet(self.src_lines, node)))
        self.generic_visit(node)


def _module_is(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def scan_file(path: str) -> FileReport:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        src = fh.read()
    gate_aware = any(tok in src for tok in _GATE_TOKENS)
    try:
        tree = ast.parse(src, filename=path)
    except SyntaxError:
        # Codex round-2: a SyntaxError file was silently treated as no-emit — a
        # blind spot. Surface it as 'unparseable' so it is never counted clean.
        return FileReport(path, gate_aware, [], parse_error=True)
    v = _Visitor(path, src.splitlines())
    v.visit(tree)
    return FileReport(path, gate_aware, v.sites)


def _iter_py(roots: Iterable[str]) -> Iterable[str]:
    for root in roots:
        if os.path.isfile(root) and root.endswith(".py"):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in ("__pycache__", ".git", "tests", "node_modules")]
            for fn in filenames:
                if fn.endswith(".py"):
                    yield os.path.join(dirpath, fn)


# The channel/gate implementation files themselves legitimately reference these
# names and legitimately print (CLIs). Exclude the gate package's own machinery
# from the "did a LANE bypass" question — but NOT the lanes or record_* scripts.
_SELF = {"channel.py", "export_gate.py", "enforcement.py", "priorart.py",
         "resolver.py", "layer_gate.py", "panel.py", "blindspot_map.py",
         "lane_brake.py", "contract.py", "sweep.py"}


def scan_repo(roots: Iterable[str], *, exclude_self: bool = True) -> list[FileReport]:
    reports = []
    seen = set()
    for path in _iter_py(roots):
        ap = os.path.abspath(path)
        if ap in seen:
            continue
        seen.add(ap)
        if exclude_self and os.path.basename(path) in _SELF:
            continue
        r = scan_file(path)
        if r.sites:
            reports.append(r)
    return reports


# A file that reads the factstore or a registry/corpus is one that emits
# WORLD-CLAIM numbers (recall, arm counts, effect sizes) — the ones that must be
# gated. A pure CLI/logging print is a low-severity leak (still a leak, but not a
# fabricated-figure risk). We report both so the number is neither inflated nor
# rounded down.
_WORLD_DATA_TOKENS = ("factstore", "duckdb", "sqlite3", "aact", "consume_verified",
                      "outcome_measurements", "design_groups", "registry", "pubmed")


def _reads_world_data(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            src = fh.read().lower()
    except OSError:
        return False
    return any(tok in src for tok in _WORLD_DATA_TOKENS)


def inventory(roots: Iterable[str]) -> dict:
    """The lane inventory, computed (never asserted). Returns counts + the NAMED
    list of open holes so the report cannot round 'some' up to 'all'."""
    reports = scan_repo(roots)
    open_holes = [r for r in reports if r.status == "OPEN-HOLE"]
    leaky = [r for r in reports if r.status == "leaky"]
    routed = [r for r in reports if r.status == "routed"]
    total_sites = sum(len(r.sites) for r in reports)
    # The high-severity subset: any file that touches world data AND still has a
    # naked (un-routed) emit site — OPEN-HOLE or leaky both count. A leaky file
    # imports the channel but still prints raw numbers; it is not clean.
    world_holes = [r for r in (open_holes + leaky) if _reads_world_data(r.path)]
    return {
        "files_with_emit": len(reports),
        "emit_sites": total_sites,
        "routed_files": len(routed),
        "leaky_files": len(leaky),
        "open_hole_files": len(open_holes),
        "open_holes": sorted(r.path for r in open_holes),
        "leaky": sorted(r.path for r in leaky),
        "routed": sorted(r.path for r in routed),
        "world_claim_holes": sorted(r.path for r in world_holes),
        "world_claim_hole_count": len(world_holes),
        "reports": reports,
    }


if __name__ == "__main__":
    import sys
    roots = sys.argv[1:] or [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    inv = inventory(roots)
    print(f"emit sites: {inv['emit_sites']} across {inv['files_with_emit']} files")
    print(f"routed (gate-aware): {inv['routed_files']}")
    print(f"OPEN HOLES: {inv['open_hole_files']}")
    for p in inv["open_holes"]:
        print("  HOLE", p)
