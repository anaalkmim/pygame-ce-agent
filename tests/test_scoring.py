"""Unit tests for the scoring logic.

These run offline: no API key, no network, no cost.
"""

from pathlib import Path

import pytest

from src.scoring import Case, load_cases, score, stability

CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_cases.json"


@pytest.fixture
def sample_case() -> Case:
    return Case(
        id="sample",
        question="Does it exist in both?",
        fact="Yes, both.",
        required=["both"],
        forbidden=["pygame-ce[ -]only"],
    )


def test_correct_answer_passes(sample_case):
    verdict = score(sample_case, "It exists in both distributions.", ["read"])
    assert verdict.passed
    assert verdict.reason == "ok"


def test_missing_required_term_fails(sample_case):
    verdict = score(sample_case, "It exists in pygame.", ["read"])
    assert not verdict.passed
    assert verdict.missing_required == ["both"]


def test_forbidden_claim_fails(sample_case):
    verdict = score(sample_case, "It is both common and pygame-ce only.", ["read"])
    assert not verdict.passed
    assert verdict.matched_forbidden


def test_answer_without_knowledge_base_call_fails(sample_case):
    """An ungrounded answer fails even when the wording is right."""
    verdict = score(sample_case, "It exists in both distributions.", [])
    assert not verdict.passed
    assert not verdict.used_knowledge_base


def test_matching_ignores_case(sample_case):
    verdict = score(sample_case, "BOTH distributions have it.", ["read"])
    assert verdict.passed


def test_stability_detects_disagreement(sample_case):
    passing = score(sample_case, "It exists in both.", ["read"])
    failing = score(sample_case, "Only pygame has it.", ["read"])
    assert stability([passing, passing]) == "stable"
    assert stability([passing, failing]) == "unstable"


def test_real_case_file_loads():
    cases = load_cases(CASES_PATH)
    assert cases
    assert all(case.question for case in cases)
    assert all(case.fact for case in cases)


def test_case_ids_are_unique():
    cases = load_cases(CASES_PATH)
    ids = [case.id for case in cases]
    assert len(ids) == len(set(ids))
