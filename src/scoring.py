"""Deterministic scoring for agent answers. No network, so it is unit testable.

Each case lists regex patterns: `required` must appear in a correct answer,
`forbidden` marks a specific wrong claim. Matching is case-insensitive.
This catches gross errors, not subtle ones — read the saved answers too.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

FLAGS = re.IGNORECASE | re.DOTALL


@dataclass
class Case:
    """One evaluation question and the claims that decide its verdict."""

    id: str
    question: str
    fact: str
    required: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    """The outcome of scoring one answer against one case."""

    case_id: str
    passed: bool
    missing_required: list[str]
    matched_forbidden: list[str]
    used_knowledge_base: bool

    @property
    def reason(self) -> str:
        """Short explanation of why a case failed."""
        if self.passed:
            return "ok"
        parts = []
        if not self.used_knowledge_base:
            parts.append("no knowledge base call")
        if self.missing_required:
            parts.append("missing: " + ", ".join(self.missing_required))
        if self.matched_forbidden:
            parts.append("wrong claim: " + ", ".join(self.matched_forbidden))
        return "; ".join(parts)


def load_cases(path: Path) -> list[Case]:
    """Read the case file and return it as Case objects."""
    return [Case(**e) for e in json.loads(path.read_text())["cases"]]


def score(case: Case, answer: str, tool_calls: list[str]) -> Verdict:
    """Score one answer. An answer that skipped the knowledge base fails."""
    missing = [p for p in case.required if not re.search(p, answer, FLAGS)]
    matched = [p for p in case.forbidden if re.search(p, answer, FLAGS)]
    grounded = bool(tool_calls)
    ok = grounded and not missing and not matched
    return Verdict(case.id, ok, missing, matched, grounded)


def stability(verdicts: list[Verdict]) -> str:
    """Whether repeated runs of one case agreed with each other."""
    return "unstable" if len({v.passed for v in verdicts}) > 1 else "stable"
