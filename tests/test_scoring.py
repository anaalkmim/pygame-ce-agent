"""Unit tests for verdict-line scoring. Offline: no key, no network, no cost."""

from pathlib import Path

import pytest

from src.scoring import Case, find_claims, load_cases, parse_claim, score, stability

CASES_PATH = Path(__file__).resolve().parent.parent / "data" / "eval_cases.json"
ANSWER = "Prose here.\n\nVERDICT: premul_alpha = pygame:yes, pygame-ce:yes"


@pytest.fixture
def case() -> Case:
    return Case("s", "q?", "both", "premul_alpha = pygame:yes, pygame-ce:yes")


def test_matching_verdict_passes(case):
    assert score(case, ANSWER, ["read"]).passed


def test_wrong_verdict_fails(case):
    answer = "VERDICT: premul_alpha = pygame:no, pygame-ce:yes"
    assert not score(case, answer, ["read"]).passed


def test_negated_prose_does_not_affect_the_verdict(case):
    """The v1 scorer failed here: 'not available in pygame' matched 'available in pygame'."""
    answer = "premul_alpha_ip is not available in pygame.\n" + ANSWER
    assert score(case, answer, ["read"]).passed


def test_extra_verdict_about_another_name_is_allowed(case):
    answer = ANSWER + "\nVERDICT: premul_alpha_ip = pygame:no, pygame-ce:yes"
    assert score(case, answer, ["read"]).passed


def test_missing_verdict_line_fails(case):
    assert not score(case, "It exists in both.", ["read"]).passed


def test_answer_without_knowledge_base_call_fails(case):
    assert not score(case, ANSWER, []).passed


def test_distribution_order_does_not_matter(case):
    answer = "VERDICT: premul_alpha = pygame-ce:yes, pygame:yes"
    assert score(case, answer, ["read"]).passed


def test_pygame_prefix_is_stripped():
    case = Case("s", "q?", "f", "IS_CE = pygame:no, pygame-ce:yes")
    answer = "VERDICT: pygame.IS_CE = pygame:no, pygame-ce:yes"
    assert score(case, answer, ["read"]).passed


def test_not_covered_verdict():
    case = Case("s", "q?", "f", "not covered")
    assert score(case, "No networking.\nVERDICT: not covered", ["read"]).passed


def test_malformed_line_is_not_a_claim():
    assert find_claims("VERDICT: something vague") == []
    assert parse_claim("no equals sign here") is None


def test_stability_detects_disagreement(case):
    good = score(case, ANSWER, ["read"])
    bad = score(case, "VERDICT: premul_alpha = pygame:no, pygame-ce:no", ["read"])
    assert stability([good, good]) == "stable"
    assert stability([good, bad]) == "unstable"


def test_real_case_file_parses():
    cases = load_cases(CASES_PATH)
    assert cases
    assert all(parse_claim(c.expected) is not None for c in cases)
    assert len({c.id for c in cases}) == len(cases)


def test_dotted_prefix_is_stripped(case):
    """The model writes Surface.premul_alpha; the case declares premul_alpha."""
    answer = "VERDICT: Surface.premul_alpha = pygame:yes, pygame-ce:yes"
    assert score(case, answer, ["read"]).passed


def test_deep_dotted_prefix_is_stripped(case):
    answer = "VERDICT: pygame.Surface.premul_alpha = pygame:yes, pygame-ce:yes"
    assert score(case, answer, ["read"]).passed


def test_a_different_name_still_fails(case):
    """Stripping prefixes must not make unrelated names collide."""
    answer = "VERDICT: Surface.premul_alpha_ip = pygame:yes, pygame-ce:yes"
    assert not score(case, answer, ["read"]).passed
