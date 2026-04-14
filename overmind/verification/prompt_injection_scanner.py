"""Detect prompt-injection artefacts in agent output.

Complements the prompt-sanitisation defence added to
`Orchestrator._sanitize_prompt_value`. Catches cases where an injected
instruction inside a task title, project name, or tool output already
reached the agent and altered its behaviour — evidenced by canary
tokens, "I will ignore previous instructions" patterns, or attempts to
execute instruction blocks the agent read as data.

Designed to plug into PolicyGuard or the orchestrator's intervention
pipeline, not to judge correctness of behaviour. If this scanner finds
a match, something reached the agent that shouldn't have.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True, frozen=True)
class InjectionFinding:
    category: Literal[
        "canary_echoed", "instruction_override", "data_exfil_pattern",
        "role_confusion", "system_prompt_leak",
    ]
    matched_line: str
    pattern_name: str


# Canary tokens Overmind may inject into agent prompts; if they show up in
# output it means the agent echoed them (injection possible) or the agent
# itself is leaking injected context.
DEFAULT_CANARY_TOKENS: tuple[str, ...] = (
    "OVERMIND_CANARY_TOKEN",
    "__OVERMIND_INJECTION_PROBE__",
)

# Injection patterns — agents "confirming" they were redirected.
_INSTRUCTION_OVERRIDE_PATTERNS = [
    ("ignore_previous",
     re.compile(r"ignore (all|any|the|previous|prior|earlier) (instructions|rules|system prompt)", re.IGNORECASE)),
    ("new_persona",
     re.compile(r"(you are now|acting as|pretend to be|roleplay as)\s+[a-z][\w -]{0,40}", re.IGNORECASE)),
    ("disregard_safety",
     re.compile(r"(disregard|bypass|override)\s+(the\s+)?(safety|guardrails?|rules|restrictions)", re.IGNORECASE)),
    ("print_system_prompt",
     re.compile(r"(print|show|reveal|dump|output)\s+(your\s+)?(system\s+prompt|initial instructions)", re.IGNORECASE)),
]

# Data-exfiltration scaffolding that agents occasionally generate verbatim when
# a prompt-injection wants them to post secrets outward.
_EXFIL_PATTERNS = [
    ("curl_post_env",
     re.compile(r"curl\s+.*(?:-X\s+POST|--data|-d\s).*\$\{?[A-Z_]*(?:KEY|TOKEN|SECRET|PASS)", re.IGNORECASE)),
    ("base64_env",
     re.compile(r"base64.*\$\{?[A-Z_]*(?:KEY|TOKEN|SECRET|PASS)", re.IGNORECASE)),
    ("exfil_webhook",
     re.compile(r"(?:webhook\.site|requestbin|ngrok\.io|\.burpcollaborator\.net)", re.IGNORECASE)),
]

# Agents signalling role confusion ("as an AI I was told to...", system-prompt
# paraphrase). These are soft signals, not hard evidence.
_ROLE_CONFUSION_PATTERNS = [
    ("i_was_told",
     re.compile(r"^(i was told|my instructions are|my system prompt (says|told))", re.IGNORECASE | re.MULTILINE)),
    ("you_are_prompt_echo",
     re.compile(r"^(you are (an? )?(helpful|expert|senior|professional|autonomous)\b.{0,120})", re.IGNORECASE | re.MULTILINE)),
]


class PromptInjectionScanner:
    def __init__(self, canary_tokens: tuple[str, ...] = DEFAULT_CANARY_TOKENS) -> None:
        self.canary_tokens = canary_tokens

    def scan(self, lines: list[str]) -> list[InjectionFinding]:
        findings: list[InjectionFinding] = []
        for line in lines:
            stripped = line.strip()
            for token in self.canary_tokens:
                if token in stripped:
                    findings.append(InjectionFinding(
                        category="canary_echoed",
                        matched_line=stripped[:200],
                        pattern_name=f"canary:{token}",
                    ))
            for name, pattern in _INSTRUCTION_OVERRIDE_PATTERNS:
                if pattern.search(stripped):
                    findings.append(InjectionFinding(
                        category="instruction_override",
                        matched_line=stripped[:200],
                        pattern_name=name,
                    ))
            for name, pattern in _EXFIL_PATTERNS:
                if pattern.search(stripped):
                    findings.append(InjectionFinding(
                        category="data_exfil_pattern",
                        matched_line=stripped[:200],
                        pattern_name=name,
                    ))
            for name, pattern in _ROLE_CONFUSION_PATTERNS:
                if pattern.search(stripped):
                    findings.append(InjectionFinding(
                        category="role_confusion",
                        matched_line=stripped[:200],
                        pattern_name=name,
                    ))
        return findings

    def has_hard_evidence(self, findings: list[InjectionFinding]) -> bool:
        """Canary echo or exfil scaffold = hard evidence; others are soft signals."""
        return any(f.category in {"canary_echoed", "data_exfil_pattern"} for f in findings)
