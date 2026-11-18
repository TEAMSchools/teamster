"""Scoring for the academic-year eval.

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

Every rate carries a 95% Wilson interval clustered on prompt id (see
_clustered_wilson): reps of one prompt are not independent trials.
"""

import json
import math
import re
import statistics
from typing import Any

import traps
from traps import _flatten_filters

# A year-span ("2025-2026", "2025-26", "2025–26") or the phrase "school year"
# near a year, or an explicit "interpret..." — taken as the model surfacing its
# reading of the year to the user.
_ECHO_RE = re.compile(
    r"20\d{2}\s*[-–]\s*(?:20)?\d{2}|interpret|school year", re.IGNORECASE
)
_LABEL_RE = re.compile(r"^\s*(\d{4})\s*[-–]\s*(?:\d{2}|\d{4})\s*$")
_INT_RE = re.compile(r"^\s*(\d{4})\s*$")


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
    if "trap" in prompt:  # family 4: assessment traps
        view_queries = [
            q
            for q in result.get("load_queries", [])
            if isinstance(q, dict) and "student_assessment_scores_view" in json.dumps(q)
        ]
        return {
            "id": prompt["id"],
            "family": prompt["family"],
            "ground_truth_start": None,
            "trap": prompt["trap"],
            "trap_fired": traps.TRAPS[prompt["trap"]](
                view_queries, result.get("final_text") or ""
            ),
            "n_view_queries": len(view_queries),
            "error": result.get("error"),
            "subtype": result.get("subtype"),
        }
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

    rec: dict[str, Any] = {
        "id": prompt["id"],
        "family": family,
        "ground_truth_start": gt,
        "queried_start": start,
        "ay_filter": filt,
        "echoed": echoed,
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


# The clustered interval and the t quantile below are ported from Inspect AI's
# ci_wilson(cluster=...) in src/inspect_ai/scorer/_metrics/std.py (MIT,
# Copyright (c) 2024 UK AI Security Institute). The clustered variance is
# Appendix A of Miller, "Adding Error Bars to Evals"
# (https://arxiv.org/abs/2411.00640), with a C / (C - 1) finite-cluster
# correction.


def _clustered_wilson(
    recs: list[dict[str, Any]], flag: str
) -> tuple[float, float, float]:
    """Return (rate, lo, hi) — a 95% Wilson interval clustered on prompt ``id``.

    Reps of one prompt are correlated, so the records are not independent
    trials. The interval uses the Korn-Graubard effective sample size
    p(1 - p) / clustered variance, capped at the record count, and a Student-t
    critical value with clusters - 1 degrees of freedom. At a rate of exactly 0
    or 1 the clustered variance is 0 and says nothing about correlation, so the
    record count is used and only the t value widens the interval.
    (0, 0, 0) when there are no records; (rate, 0, 1) with one prompt, where
    the between-prompt variance cannot be estimated.
    """
    if not recs:
        return (0.0, 0.0, 0.0)
    groups: dict[str, list[float]] = {}
    for r in recs:
        groups.setdefault(r["id"], []).append(float(bool(r[flag])))
    n = len(recs)
    p = sum(sum(g) for g in groups.values()) / n
    k = len(groups)
    if k < 2:
        return (p, 0.0, 1.0)

    # Each cluster's deviation sum, squared: sum_i sum_j (s_i - p)(s_j - p).
    variance = sum((sum(g) - p * len(g)) ** 2 for g in groups.values())
    variance *= k / (k - 1) / (n * n)
    n_eff = float(n)
    if 0.0 < p < 1.0 and variance > 0.0:
        n_eff = min(p * (1 - p) / variance, n_eff)

    t = _t_inv_cdf(0.975, k - 1)
    denom = 1 + t * t / n_eff
    center = (p + t * t / (2 * n_eff)) / denom
    half = t * math.sqrt(p * (1 - p) / n_eff + t * t / (4 * n_eff * n_eff)) / denom
    return (p, max(0.0, center - half), min(1.0, center + half))


def _t_inv_cdf(p: float, df: int) -> float:
    """Student-t inverse CDF for 0.5 < p < 1, by bisection on the exact CDF."""

    def cdf(t: float) -> float:
        return 1.0 - 0.5 * _reg_inc_beta(df / 2.0, 0.5, df / (df + t * t))

    hi = 1.0
    while cdf(hi) < p:
        hi *= 2.0
    lo = 0.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _reg_inc_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b) (Numerical Recipes 6.4)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    # The continued fraction converges fast below (a + 1) / (a + b + 2); above
    # it, use the symmetry I_x(a, b) = 1 - I_(1-x)(b, a).
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Lentz's continued fraction for the incomplete beta function."""
    tiny = 1e-300

    def clamp(v: float) -> float:
        return tiny if abs(v) < tiny else v

    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 / clamp(1.0 - qab * x / qap)
    h = d
    for m in range(1, 201):
        m2 = 2 * m
        for aa in (
            m * (b - m) * x / ((qam + m2) * (a + m2)),
            -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2)),
        ):
            d = 1.0 / clamp(1.0 + aa * d)
            c = clamp(1.0 + aa / c)
            h *= d * c
        if abs(d * c - 1.0) < 3e-16:
            break
    return h


def _hit_turn_limit(rec: dict[str, Any]) -> bool:
    """The SDK result subtype; records saved before it was captured fall back
    to the CLI's error text."""
    if rec.get("subtype") is not None:
        return rec["subtype"] == "error_max_turns"
    return "maximum number of turns" in str(rec.get("error") or "")


def _trap_scorable(rec: dict[str, Any]) -> bool:
    if rec.get("error") and not _hit_turn_limit(rec):
        return False
    if rec.get("trap") in traps.ANSWER_SCORED:
        return True
    return rec.get("n_view_queries", 1) > 0


def _common_trap_prompts(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Per model, the trap prompt ids that every arm scored at least once.

    A session limit cuts a sweep partway, so arms can finish different prompt
    sets; comparing their rates over different prompts compares the prompts,
    not the arms.
    """
    scored: dict[str, dict[str, set[str]]] = {}
    for r in records:
        if "trap" not in r:
            continue
        ids = scored.setdefault(r["model"], {}).setdefault(r["arm"], set())
        if _trap_scorable(r):
            ids.add(r["id"])
    return {m: set.intersection(*by_arm.values()) for m, by_arm in scored.items()}


def aggregate(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate scored records keyed by (model, arm)."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        cells.setdefault((r["model"], r["arm"]), []).append(r)
    common = _common_trap_prompts(records)

    summary: dict[tuple[str, str], dict[str, Any]] = {}
    for key, recs in cells.items():
        # A query-scored trap needs a query on the view: with none, 4 of the 6
        # predicates read a pass and 2 a fire, so the outcome means nothing. A
        # harness cutoff (session limit, crash) is dropped for the same reason.
        # Hitting the turn limit is the model's own doing and its queries were
        # captured, so it still scores. The rate then covers only the prompts
        # every arm of the model scored; k_dropped counts the rest.
        trap_recs = [r for r in recs if "trap" in r]
        scorable = [r for r in trap_recs if _trap_scorable(r)]
        trapped = [r for r in scorable if r["id"] in common.get(key[0], set())]
        year = [r for r in recs if "trap" not in r]
        determinate = [r for r in year if r["ground_truth_start"] is not None]
        ambiguous = [r for r in year if r["ground_truth_start"] is None]
        # A rate's independent unit is the prompt, not the rep: k_* counts
        # the prompts (clusters) behind each interval.
        summary[key] = {
            "n_total": len(recs),
            "n_determinate": len(determinate),
            "k_determinate": len({r["id"] for r in determinate}),
            "k_ambiguous": len({r["id"] for r in ambiguous}),
            "errors": sum(1 for r in recs if r.get("error")),
            "wrong_rate": _clustered_wilson(determinate, "wrong"),
            "correct_rate": _clustered_wilson(determinate, "correct"),
            "no_query_rate": _clustered_wilson(determinate, "no_query"),
            "silent_wrong_rate": _clustered_wilson(determinate, "silent_wrong"),
            "disambig_rate": _clustered_wilson(ambiguous, "disambiguated"),
            "n_trap": len(trapped),
            "k_trap": len({r["id"] for r in trapped}),
            "n_unscored": len(trap_recs) - len(scorable),
            "k_dropped": len({r["id"] for r in scorable})
            - len({r["id"] for r in trapped}),
            "trap_rate": _clustered_wilson(trapped, "trap_fired"),
        }
    return summary


def format_summary(summary: dict[tuple[str, str], dict[str, Any]]) -> str:
    """Render the per-cell summary as a fixed-width table.

    ``n/k`` is records / prompts. The intervals are clustered on prompt, so k
    is the sample size that matters; at k under about 10 they are rough.
    ``drop`` counts the trap prompts this arm scored but another arm of the
    same model did not, left out of the trap rate.
    """

    def pct(triple: tuple[float, float, float]) -> str:
        p, lo, hi = triple
        return f"{p * 100:5.1f}% [{lo * 100:4.0f}-{hi * 100:4.0f}]"

    header = (
        f"{'model':<22} {'arm':<16} {'n/k':>7} "
        f"{'wrong':>16} {'silent_wrong':>16} {'correct':>16} "
        f"{'no_query':>16} {'disambig':>16} {'trap n/k':>8} {'drop':>4} "
        f"{'trap_rate':>16}"
    )
    lines = [header, "-" * len(header)]
    for model, arm in sorted(summary):
        s = summary[(model, arm)]
        det = f"{s['n_determinate']}/{s['k_determinate']}"
        trap = f"{s['n_trap']}/{s['k_trap']}"
        lines.append(
            f"{model:<22} {arm:<16} {det:>7} "
            f"{pct(s['wrong_rate']):>16} {pct(s['silent_wrong_rate']):>16} "
            f"{pct(s['correct_rate']):>16} {pct(s['no_query_rate']):>16} "
            f"{pct(s['disambig_rate']):>16} {trap:>8} {s['k_dropped']:>4} "
            f"{pct(s['trap_rate']):>16}"
        )
    return "\n".join(lines)


_COST_FIELDS = [
    "input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "output_tokens",
    "cost_usd",
    "num_turns",
    "duration_ms",
]


def format_cost_summary(records: list[dict[str, Any]]) -> str:
    """Median tokens, cost, turns, tool calls and duration per (model, arm)."""
    cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        cells.setdefault((r["model"], r["arm"]), []).append(r)
    header = f"{'model':<22} {'arm':<16} " + " ".join(
        f"{c:>14}" for c in [*_COST_FIELDS, "tool_calls"]
    )
    lines = ["median per conversation", header, "-" * len(header)]
    for key in sorted(cells):
        recs = cells[key]
        vals = []
        for field in _COST_FIELDS:
            xs = [r[field] for r in recs if isinstance(r.get(field), int | float)]
            vals.append(f"{statistics.median(xs):>14.4g}" if xs else f"{'-':>14}")
        calls = [len(r.get("tool_calls") or []) for r in recs]
        vals.append(f"{statistics.median(calls):>14.4g}" if calls else f"{'-':>14}")
        lines.append(f"{key[0]:<22} {key[1]:<16} " + " ".join(vals))
    return "\n".join(lines)
