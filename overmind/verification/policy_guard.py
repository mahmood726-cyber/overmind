"""Real-time policy enforcement for agent terminal output.

Inspired by Cupcake (EQTY Lab): intercepts dangerous commands in terminal
output before they cause harm.  Pure Python pattern matching — no Wasm/Rego.

Integrates into Orchestrator._decide_interventions() to generate block/warn
actions alongside existing loop and proof-gap interventions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from overmind.storage.models import utc_now

Severity = Literal["block", "warn", "review"]
SECRET_NAME_PATTERN = r"(?:[A-Z0-9_]*?(?:API[_-]?KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL)|AWS_SECRET(?:_ACCESS_KEY)?)"


@dataclass(slots=True)
class PolicyRule:
    name: str
    pattern: re.Pattern[str]
    severity: Severity
    message: str


@dataclass(slots=True)
class PolicyViolation:
    rule_name: str
    severity: Severity
    matched_line: str
    message: str
    created_at: str = field(default_factory=utc_now)


# ── Default rule set ────────────────────────────────────────────────

DEFAULT_RULES: list[PolicyRule] = [
    # Destructive filesystem
    PolicyRule(
        "rm_recursive_root",
        re.compile(r"rm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(?!\w)", re.IGNORECASE),
        "block",
        "Blocked: recursive delete targeting root filesystem",
    ),
    PolicyRule(
        "rm_rf_broad",
        re.compile(r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+\.\s*$", re.IGNORECASE),
        "block",
        "Blocked: rm -rf on current directory",
    ),
    PolicyRule(
        "powershell_remove_item_broad",
        re.compile(
            r"(?=.*\bRemove-Item\b)"
            r"(?=.*(?:^|\s)-Recurse(?:\s|$))"
            r"(?=.*(?:^|\s)-Force(?:\s|$))"
            r"(?=.*(?:-Path|-LiteralPath)\s+['\"]?(?:\.|[A-Za-z]:\\)['\"]?(?:\s|$))",
            re.IGNORECASE,
        ),
        "block",
        "Blocked: Remove-Item -Recurse -Force targeting current directory or drive root",
    ),
    PolicyRule(
        # PowerShell's Remove-Item accepts a positional path without -Path/-LiteralPath.
        # Catch positional forms like `Remove-Item -Recurse -Force C:\*` or `Remove-Item . -Recurse -Force`.
        "powershell_remove_item_positional",
        re.compile(
            r"(?=.*\bRemove-Item\b)"
            r"(?=.*(?:^|\s)-Recurse(?:\s|$))"
            r"(?=.*(?:^|\s)-Force(?:\s|$))"
            r"(?=.*(?:^|\s)['\"]?(?:\.|[A-Za-z]:\\\*?|~|/)['\"]?(?:\s|$))",
            re.IGNORECASE,
        ),
        "block",
        "Blocked: Remove-Item -Recurse -Force with positional path targeting current directory or drive root",
    ),
    PolicyRule(
        "cmd_rmdir_broad",
        re.compile(r"\b(?:rmdir|rd)\b\s+/s\s+/q\s+['\"]?(?:\.|[A-Za-z]:\\)['\"]?(?:\s|$)", re.IGNORECASE),
        "block",
        "Blocked: recursive directory delete targeting current directory or drive root",
    ),
    PolicyRule(
        "cmd_del_broad",
        re.compile(r"\b(?:del|erase)\b\s+/s\s+/q\s+['\"]?(?:\*|\.\\\*|[A-Za-z]:\\\*)['\"]?(?:\s|$)", re.IGNORECASE),
        "block",
        "Blocked: recursive delete targeting a broad Windows path",
    ),
    # Destructive git
    PolicyRule(
        # Catch both --force (excluding --force-with-lease) and -f short form.
        # Lookahead approach avoids the `\s+push\s+` swallowing the space that
        # precedes `-f` in `git push -f origin main`.
        "git_force_push",
        re.compile(
            r"git\s+push\b(?=[^\n]*?(?:--force(?!-with-lease)|\s-f(?:\s|$)))",
            re.IGNORECASE,
        ),
        "block",
        "Blocked: force push without --force-with-lease",
    ),
    PolicyRule(
        "git_reset_hard",
        re.compile(r"git\s+reset\s+--hard", re.IGNORECASE),
        "warn",
        "Warning: git reset --hard may discard uncommitted work",
    ),
    PolicyRule(
        "git_clean_force",
        re.compile(r"git\s+clean\s+-[a-zA-Z]*f", re.IGNORECASE),
        "warn",
        "Warning: git clean -f removes untracked files permanently",
    ),
    # Credential exposure
    PolicyRule(
        "secret_echo",
        re.compile(
            rf"(echo|printf|cat)\s+.*{SECRET_NAME_PATTERN}",
            re.IGNORECASE,
        ),
        "block",
        "Blocked: potential credential exposure via stdout",
    ),
    PolicyRule(
        "env_secret_set",
        re.compile(
            r"(?:" 
            rf"export\s+({SECRET_NAME_PATTERN})\s*=|"
            rf"\$env:({SECRET_NAME_PATTERN})\s*=|"
            rf"set\s+({SECRET_NAME_PATTERN})\s*=)"
            ,
            re.IGNORECASE,
        ),
        "warn",
        "Warning: setting secret in environment variable via terminal",
    ),
    # Process/system
    PolicyRule(
        "kill_all",
        re.compile(r"(kill\s+-9\s+-1|killall\s)", re.IGNORECASE),
        "block",
        "Blocked: mass process kill",
    ),
    PolicyRule(
        "chmod_world_writable",
        re.compile(r"chmod\s+[0-7]*7[0-7]*[0-7]\s", re.IGNORECASE),
        "warn",
        "Warning: world-writable permission change",
    ),
    # Database
    PolicyRule(
        "drop_database",
        re.compile(r"DROP\s+(DATABASE|TABLE|SCHEMA)\s", re.IGNORECASE),
        "block",
        "Blocked: destructive database DDL",
    ),
    # Network
    PolicyRule(
        "curl_pipe_shell",
        re.compile(r"curl\s+.*\|\s*(ba)?sh", re.IGNORECASE),
        "warn",
        "Warning: piping remote content to shell",
    ),
    PolicyRule(
        "powershell_pipe_iex",
        re.compile(
            r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\b.*\|\s*(?:Invoke-Expression|iex)\b",
            re.IGNORECASE,
        ),
        "warn",
        "Warning: piping remote PowerShell content into Invoke-Expression",
    ),
]


class PolicyGuard:
    """Evaluate terminal output lines against a set of policy rules."""

    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self.rules = rules if rules is not None else list(DEFAULT_RULES)

    def evaluate(self, lines: list[str]) -> list[PolicyViolation]:
        """Check lines against all rules.  Returns violations sorted by severity."""
        violations: list[PolicyViolation] = []
        for line in lines:
            for rule in self.rules:
                if rule.pattern.search(line):
                    violations.append(
                        PolicyViolation(
                            rule_name=rule.name,
                            severity=rule.severity,
                            matched_line=line.strip()[:200],
                            message=rule.message,
                        )
                    )
        severity_order: dict[str, int] = {"block": 0, "warn": 1, "review": 2}
        violations.sort(key=lambda v: severity_order.get(v.severity, 9))
        return violations

    def has_blocks(self, violations: list[PolicyViolation]) -> bool:
        """Return True if any violation has 'block' severity."""
        return any(v.severity == "block" for v in violations)

    def to_interventions(
        self, violations: list[PolicyViolation], task_id: str
    ) -> list[dict[str, str]]:
        """Convert violations to Overmind intervention dicts."""
        interventions: list[dict[str, str]] = []
        for v in violations:
            if v.severity == "block":
                interventions.append({
                    "task_id": task_id,
                    "action": "send_message",
                    "message": f"POLICY VIOLATION [{v.rule_name}]: {v.message}. "
                               f"Matched: {v.matched_line[:100]}. "
                               "Stop this action immediately.",
                })
                interventions.append({
                    "task_id": task_id,
                    "action": "pause",
                    "message": f"POLICY VIOLATION [{v.rule_name}]: session paused to prevent unsafe action.",
                })
            elif v.severity == "warn":
                interventions.append({
                    "task_id": task_id,
                    "action": "send_message",
                    "message": f"POLICY WARNING [{v.rule_name}]: {v.message}. "
                               f"Matched: {v.matched_line[:100]}. "
                               "Proceed with caution.",
                })
        return interventions
