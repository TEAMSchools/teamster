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

_NAMED_ROUNDS = {"BOY", "MOY", "EOY"}


def _flatten_filters(filters: Any) -> list[dict[str, Any]]:
    """Flatten a Cube filters list, descending into and/or groups."""
    out: list[dict[str, Any]] = []
    if not isinstance(filters, list):
        return out
    for f in filters:
        if not isinstance(f, dict):
            continue
        if "member" in f:
            out.append(f)
        for key in ("and", "or"):
            if key in f:
                out.extend(_flatten_filters(f[key]))
    return out


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
    """A "no proficiency level" question did not filter with notSet, on
    proficiency_level or on is_mastery (the documented "no verdict" filter)."""
    return not any(
        f.get("operator") == "notSet"
        for member in ("proficiency_level", "is_mastery")
        for f in _filters_on(queries, member)
    )


def module_code_without_subject(queries: list[dict[str, Any]], text: str) -> bool:
    """A query filtered module_code with no academic_subject pairing. Each
    query stands alone: a subject in another query does not scope this one."""
    return any(
        _filters_on([q], "module_code") and not _uses([q], "academic_subject")
        for q in queries
    )


def internal_flag_for_source(queries: list[dict[str, Any]], text: str) -> bool:
    """A source was selected with is_internal_assessment."""
    return bool(_filters_on(queries, "is_internal_assessment"))


def formative_alone(queries: list[dict[str, Any]], text: str) -> bool:
    """pct_proficient_formative stood in for "all internal checkpoints": a query
    used it without module_type. Each query stands alone, as above."""
    return any(
        _uses([q], "pct_proficient_formative") and not _uses([q], "module_type")
        for q in queries
    )


def most_recent_not_named_round(queries: list[dict[str, Any]], text: str) -> bool:
    """ "Most recent diagnostic" was not scoped to exactly one named benchmark
    round with equals."""
    for f in _filters_on(queries, "administration_period"):
        values = {str(v) for v in f.get("values") or []}
        if (
            f.get("operator") == "equals"
            and len(values) == 1
            and values <= _NAMED_ROUNDS
        ):
            return False
    return True


# The negation must govern i-Ready itself: "no i-Ready data" reports the gap,
# "no students reached grade level on i-Ready" reads the zero as a result.
_NO_IREADY = re.compile(
    r"\b(?:no|not any|isn'?t any|without|zero)\s+(?:paterson(?:'s)?\s+)?i-?ready"
    r"|\bdo(?:es)?(?:n'?t| not) have (?:any )?i-?ready"
    # Not using it: "doesn't use i-Ready", "do not administer i-Ready".
    r"|\b(?:do(?:es)?n'?t|not|never)\s+(?:use|administer|offer|give|run)\b"
    r"[^.]{0,20}?i-?ready"
    r"|i-?ready\s+(?:is|are|was)(?:n'?t| not)\s+(?:used|administered|offered|given)"
    r"|i-?ready[^.]{0,60}\b(not available|no data|isn'?t available|not (?:loaded|present))"
    r"|paterson[^.]{0,60}\b(not (?:showing|present|available|loaded|in the)"
    r"|isn'?t (?:showing|available|in the)|no data|absent"
    # "missing the mark" is a verdict on the scores, not a gap.
    r"|missing(?! (?:the|its|their) (?:mark|target|goal|bar))"
    r"|does(?:n'?t| not) (?:appear|show))",
    re.IGNORECASE,
)
# "coverage" counts only as a gap ("no coverage", "a coverage gap"), and only in
# a sentence that names Paterson or i-Ready.
_COVERAGE_GAP = re.compile(
    r"(no|not any|lacks?|missing|without)\b[^.]{0,30}\bcoverage"
    r"|coverage\b[^.]{0,30}\b(gap|missing|is not|isn'?t|does not|doesn'?t)",
    re.IGNORECASE,
)
_PATERSON_OR_IREADY = re.compile(r"paterson|i-?ready", re.IGNORECASE)


def paterson_zero_as_failure(queries: list[dict[str, Any]], text: str) -> bool:
    """Answer-scored: the reply did not report that Paterson lacks i-Ready."""
    text = text or ""
    if _NO_IREADY.search(text):
        return False
    return not any(
        _COVERAGE_GAP.search(s) and _PATERSON_OR_IREADY.search(s)
        for s in re.split(r"(?<=[.!?])\s+", text)
    )


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
