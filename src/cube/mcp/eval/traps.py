"""Eval family 4 trap predicates.

Each takes the captured `load` queries on the assessment view and the final
answer text, and returns True when the trap FIRED. They are importable on
purpose: #5613 runs the query-scored ones against logged production queries.
`paterson_zero_as_failure` is the one answer-scored trap.
"""

import json
import re
from collections.abc import Callable
from typing import Any

from scorer import _flatten_filters

_NAMED_ROUNDS = {"BOY", "MOY", "EOY"}


def _filters(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for q in queries for f in _flatten_filters(q.get("filters"))]


def _members(queries: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for q in queries:
        out += list(q.get("measures") or []) + list(q.get("dimensions") or [])
        out += [f.get("member", "") for f in _flatten_filters(q.get("filters"))]
        out += [t.get("dimension", "") for t in q.get("timeDimensions") or []]
    return out


def _uses(queries: list[dict[str, Any]], member: str) -> bool:
    return any(str(m).endswith(f".{member}") for m in _members(queries))


def _filters_on(queries: list[dict[str, Any]], member: str) -> list[dict[str, Any]]:
    return [
        f for f in _filters(queries) if str(f.get("member", "")).endswith(f".{member}")
    ]


def grade_filter_on_vendor(queries: list[dict[str, Any]], text: str) -> bool:
    """An i-Ready grade question filtered grade_level_tested (null for vendors)."""
    return bool(_filters_on(queries, "grade_level_tested"))


def null_via_equals(queries: list[dict[str, Any]], text: str) -> bool:
    """A "no proficiency level" question did not filter with notSet."""
    return not any(
        f.get("operator") == "notSet" for f in _filters_on(queries, "proficiency_level")
    )


def module_code_without_subject(queries: list[dict[str, Any]], text: str) -> bool:
    """A module_code filter with no academic_subject pairing."""
    return bool(_filters_on(queries, "module_code")) and not _uses(
        queries, "academic_subject"
    )


def internal_flag_for_source(queries: list[dict[str, Any]], text: str) -> bool:
    """A source was selected with is_internal_assessment."""
    return bool(_filters_on(queries, "is_internal_assessment"))


def formative_alone(queries: list[dict[str, Any]], text: str) -> bool:
    """pct_proficient_formative stood in for "all internal checkpoints"."""
    return _uses(queries, "pct_proficient_formative") and not _uses(
        queries, "module_type"
    )


def most_recent_not_named_round(queries: list[dict[str, Any]], text: str) -> bool:
    """ "Most recent diagnostic" was not scoped to a named benchmark round."""
    for f in _filters_on(queries, "administration_period"):
        values = {str(v) for v in f.get("values") or []}
        if values and values <= _NAMED_ROUNDS:
            return False
    return True


_COVERAGE = re.compile(
    r"(no|not any|doesn'?t have|does not have|isn'?t any|without)\b[^.]{0,60}i-?ready"
    r"|i-?ready[^.]{0,60}\b(not available|no data|isn'?t available|not (?:loaded|present))"
    r"|coverage",
    re.IGNORECASE,
)


def paterson_zero_as_failure(queries: list[dict[str, Any]], text: str) -> bool:
    """Answer-scored: the reply did not report that Paterson lacks i-Ready."""
    return not _COVERAGE.search(text or "")


def is_paterson_query(query: dict[str, Any]) -> bool:
    """True when a filter value names Paterson; the eval stub returns 0 rows."""
    return any(
        "paterson" in json.dumps(f.get("values") or []).lower()
        for f in _flatten_filters(query.get("filters"))
    )


ANSWER_SCORED = {"paterson_zero_as_failure"}

TRAPS: dict[str, Callable[[list[dict[str, Any]], str], bool]] = {
    "grade_filter_on_vendor": grade_filter_on_vendor,
    "null_via_equals": null_via_equals,
    "module_code_without_subject": module_code_without_subject,
    "internal_flag_for_source": internal_flag_for_source,
    "formative_alone": formative_alone,
    "most_recent_not_named_round": most_recent_not_named_round,
    "paterson_zero_as_failure": paterson_zero_as_failure,
}
