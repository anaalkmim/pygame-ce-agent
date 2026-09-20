"""Deterministic scoring for agent answers. No network, so it is unit testable.

The agent ends each answer with lines shaped like

    VERDICT: premul_alpha = pygame:yes, pygame-ce:no

Scoring compares those lines, not the prose. Matching prose by substring
proved unusable: "not available in pygame" contains "available in pygame",
and an answer about two methods cannot say which claim a match belongs to.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

VERDICT_LINE = re.compile(r"^\s*VERDICT:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
NOT_COVERED = "not covered"


@dataclass
class Case:
    """One evaluation question and the verdict a correct answer must reach."""

    id: str
    question: str
    fact: str
    expected: str


@dataclass
class Verdict:
    """The outcome of scoring one answer against one case."""

    case_id: str
    passed: bool
    expected: str
    found: list[str]
    used_knowledge_base: bool

    @property
    def reason(self) -> str:
        """Short explanation of why a case failed."""
        if self.passed:
            return "ok"
        if not self.used_knowledge_base:
            return "no knowledge base call"
        if not self.found:
            return "no verdict line in answer"
        return f"got {self.found}"


def parse_claim(text: str) -> tuple[str, dict[str, str]] | None:
    """Turn one verdict body into a name and a distribution map.

    Returns None when the text does not have the expected shape, so a
    malformed line counts as no verdict rather than as a silent pass.
    """
    body = text.strip().rstrip(".")
    if body.lower() == NOT_COVERED:
        return NOT_COVERED, {}
    if "=" not in body:
        return None

    name, _, rest = body.partition("=")
    distributions = {}
    for chunk in rest.split(","):
        key, sep, value = chunk.partition(":")
        if not sep:
            return None
        distributions[key.strip().lower()] = value.strip().lower()

    if not distributions:
        return None
    # Keep only the last dotted segment: the model writes the same claim
    # as "premul_alpha", "Surface.premul_alpha" or "pygame.Surface.premul_alpha".
    return name.strip().lower().rsplit(".", 1)[-1], distributions


def find_claims(answer: str) -> list[tuple[str, dict[str, str]]]:
    """Collect every well-formed verdict line in an answer."""
    parsed = [parse_claim(m) for m in VERDICT_LINE.findall(answer)]
    return [claim for claim in parsed if claim is not None]


def score(case: Case, answer: str, tool_calls: list[str]) -> Verdict:
    """Score one answer. An answer that skipped the knowledge base fails."""
    expected = parse_claim(case.expected)
    claims = find_claims(answer)
    grounded = bool(tool_calls)
    passed = grounded and expected is not None and expected in claims
    found = [m.strip() for m in VERDICT_LINE.findall(answer)]
    return Verdict(case.id, passed, case.expected, found, grounded)


def load_cases(path: Path) -> list[Case]:
    """Read the case file and return it as Case objects."""
    return [Case(**e) for e in json.loads(path.read_text())["cases"]]


def stability(verdicts: list[Verdict]) -> str:
    """Whether repeated runs of one case agreed with each other."""
    return "unstable" if len({v.passed for v in verdicts}) > 1 else "stable"
