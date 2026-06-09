"""Scoring for the academic-year resolver eval.

Maps the filter the model built (captured by the harness) to a canonical
academic-year START integer, compares it to each prompt's ground truth, and
aggregates per (model, arm).

Metrics
-------
Determinate prompts (families 1 & 2 — a correct year exists):
    correct_rate     queried AY start == ground truth
    wrong_rate       queried AY start present but != ground truth  (the bug)
    no_query_rate    model never pinned an AY filter
    silent_wrong     wrong AND no interpretation echoed in the reply
Ambiguous prompts (family 3 — no correct year):
    disambig_rate    model echoed an interpretation / noted the ambiguity
All arms:
    resolver_rate    fraction of reps that called resolve_academic_year
                     (only meaningful for arm C; measures the soft "REQUIRED"
                      gate's reliability)
"""

import math
import re
from typing import Any

# A year-span ("2025-2026", "2025-26", "2025–26") or the phrase "school year"
# near a year, or an explicit "interpret..." — taken as the model surfacing its
# reading of the year to the user.
_ECHO_RE = re.compile(
    r"20\d{2}\s*[-–]\s*(?:20)?\d{2}|interpret|school year", re.IGNORECASE
)
_LABEL_RE = re.compile(r"^\s*(\d{4})\s*[-–]\s*(?:\d{2}|\d{4})\s*$")
_INT_RE = re.compile(r"^\s*(\d{4})\s*$")


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


def _label_start(value: Any) -> int | None:
    m = _LABEL_RE.match(str(value))
    return int(m.group(1)) if m else None


def _int_start(value: Any) -> int | None:
    m = _INT_RE.match(str(value))
    return int(m.group(1)) if m else None


def ay_filter(query: Any) -> dict[str, Any] | None:
    """Return the first filter on an academic-year member, or None.

    Returns {"member": str, "values": list} so callers can distinguish a
    *malformed* AY filter (e.g. label = "SY26", which matches zero rows) from
    *no* AY filter at all — different failure modes that must score differently.
    """
    if not isinstance(query, dict):
        return None
    for f in _flatten_filters(query.get("filters")):
        member = str(f.get("member", ""))
        if member.endswith("academic_year") or member.endswith("academic_year_label"):
            raw_values = f.get("values")
            values: list[Any] = raw_values if isinstance(raw_values, list) else []
            return {"member": member, "values": values}
    return None


def _start_from_ay(filt: dict[str, Any] | None) -> int | None:
    """Map an ay_filter to a START year, or None if its value is malformed."""
    if not filt:
        return None
    is_label = str(filt["member"]).endswith("academic_year_label")
    for v in filt["values"]:
        start = _label_start(v) if is_label else (_int_start(v) or _label_start(v))
        if start is not None:
            return start
    return None


def score_record(prompt: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Score one rep. ``prompt`` is a prompts.yaml entry; ``result`` a harness
    transcript summary."""
    gt = prompt.get("ground_truth_start")
    family = prompt["family"]
    # First load query that filters an AY member wins (even if its value is
    # malformed — that's a wrong query, not an absent one).
    filt: dict[str, Any] | None = None
    for q in result.get("load_queries", []):
        filt = ay_filter(q)
        if filt is not None:
            break
    start = _start_from_ay(filt)
    echoed = bool(_ECHO_RE.search(result.get("final_text") or ""))
    resolver_called = len(result.get("resolve_calls", [])) > 0

    rec: dict[str, Any] = {
        "id": prompt["id"],
        "family": family,
        "ground_truth_start": gt,
        "queried_start": start,
        "ay_filter": filt,
        "echoed": echoed,
        "resolver_called": resolver_called,
        "error": result.get("error"),
    }
    if gt is not None:  # determinate
        rec["no_query"] = filt is None
        rec["correct"] = start == gt
        # Wrong = filtered an AY member but landed on the wrong year, OR a
        # malformed value (filter present, start unparseable -> zero rows).
        rec["wrong"] = filt is not None and start != gt
        rec["silent_wrong"] = rec["wrong"] and not echoed
    else:  # ambiguous
        rec["disambiguated"] = echoed
    return rec


def _wilson(k: int, n: int) -> tuple[float, float, float]:
    """Return (rate, lo, hi) — Wilson 95% interval. (0,0,0) when n == 0."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def aggregate(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate scored records keyed by (model, arm)."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        cells.setdefault((r["model"], r["arm"]), []).append(r)

    summary: dict[tuple[str, str], dict[str, Any]] = {}
    for key, recs in cells.items():
        determinate = [r for r in recs if r["ground_truth_start"] is not None]
        ambiguous = [r for r in recs if r["ground_truth_start"] is None]
        n_det = len(determinate)
        wrong = sum(1 for r in determinate if r["wrong"])
        correct = sum(1 for r in determinate if r["correct"])
        no_query = sum(1 for r in determinate if r["no_query"])
        silent = sum(1 for r in determinate if r["silent_wrong"])
        resolver = sum(1 for r in recs if r["resolver_called"])
        errors = sum(1 for r in recs if r.get("error"))
        disambig = sum(1 for r in ambiguous if r["disambiguated"])

        summary[key] = {
            "n_total": len(recs),
            "n_determinate": n_det,
            "errors": errors,
            "wrong_rate": _wilson(wrong, n_det),
            "correct_rate": _wilson(correct, n_det),
            "no_query_rate": _wilson(no_query, n_det),
            "silent_wrong_rate": _wilson(silent, n_det),
            "resolver_rate": _wilson(resolver, len(recs)),
            "disambig_rate": _wilson(disambig, len(ambiguous)),
        }
    return summary


def format_summary(summary: dict[tuple[str, str], dict[str, Any]]) -> str:
    """Render the per-cell summary as a fixed-width table."""

    def pct(triple: tuple[float, float, float]) -> str:
        p, lo, hi = triple
        return f"{p * 100:5.1f}% [{lo * 100:4.0f}-{hi * 100:4.0f}]"

    header = (
        f"{'model':<22} {'arm':<16} {'n':>4} "
        f"{'wrong':>16} {'silent_wrong':>16} {'correct':>16} "
        f"{'no_query':>16} {'resolver':>16} {'disambig':>16}"
    )
    lines = [header, "-" * len(header)]
    for model, arm in sorted(summary):
        s = summary[(model, arm)]
        lines.append(
            f"{model:<22} {arm:<16} {s['n_determinate']:>4} "
            f"{pct(s['wrong_rate']):>16} {pct(s['silent_wrong_rate']):>16} "
            f"{pct(s['correct_rate']):>16} {pct(s['no_query_rate']):>16} "
            f"{pct(s['resolver_rate']):>16} {pct(s['disambig_rate']):>16}"
        )
    return "\n".join(lines)
