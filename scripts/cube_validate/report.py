"""report.md: trust verdict first, held findings second. Aggregates only."""

from __future__ import annotations

from collections import Counter

from . import workbook
from .cells import COINCIDENTAL, FORMULA_GAP, ORDER, PASS, ROW_GAP, answer_key

SMALL = 10


def small(n: int) -> str:
    """Counts 1 to 9 show as <10, so the report can go to #data_team."""
    return "<10" if 0 < n < SMALL else f"{n:,}"


def _mask(value) -> str:
    """A gap-table value, with whole counts from 1 to 9 shown as <10."""
    if value is None:
        return "None"
    if isinstance(value, str):
        t = value.strip().replace(",", "")
        if t.isdigit() and 0 < int(t) < SMALL:
            return "<10"
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value).is_integer() and 0 < value < SMALL:
            return "<10"
    return str(value)


def compared(cells: list) -> int:
    """Cells where Cube's number was set against the dashboard's and judged."""
    judged = (PASS, COINCIDENTAL, ROW_GAP, FORMULA_GAP)
    return sum(1 for c in cells if c.verdict in judged)


def trust(invariants: dict[str, bool], results: dict[str, str], compared: int) -> str:
    """The verdict line.

    Args:
        invariants: Each balance or capture check and whether it holds.
        results: Each hand check's recorded status.
        compared: How many cells were judged against Cube; see `compared`.
    """
    broken = [k for k, v in invariants.items() if not v]
    if broken:
        return f"Not trusted: invariant broken: {', '.join(broken)}."
    bad = sum(1 for v in results.values() if v == "disagree")
    if bad:
        return f"Not trusted: {bad} hand check{'s' if bad > 1 else ''} disagree."
    if "capture completeness" not in invariants:
        return "Pending: capture completeness was not recorded for this snapshot."
    if compared == 0:
        return "Pending: no cell was compared yet (see the mapping unproven reasons)"
    if not results:
        return "Pending: no hand checks recorded yet."
    open_checks = sum(1 for v in results.values() if v != "agree")
    if open_checks:
        return f"Pending: {open_checks} of {len(results)} hand checks still open."
    return "Trusted for this run: invariants hold and every hand check agrees."


def _row_gap_buckets(gaps: list) -> list[str]:
    """Each row-gap mark's buckets, once per mark: its measures share the rows."""
    by_mark: dict[tuple, list] = {}
    for c in gaps:
        if c.verdict == ROW_GAP:
            marks = ", ".join(f"{k}={v}" for k, v in c.dims.items())
            by_mark.setdefault((c.cut, c.sheet, marks), c.buckets)
    if not by_mark:
        return []
    out = [
        "",
        "#### Row gap buckets",
        "",
        "| Cut | Sheet | Marks | Base | Cause | Rows | Students |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for (cut, sheet, marks), buckets in by_mark.items():
        for base, cause, n, students in buckets:
            out.append(
                f"| {cut} | {sheet} | {marks} | {base} | {cause} | {small(n)} | {small(students)} |"
            )
    return out


def _untested(checks, cells: list) -> list[tuple[str, str]]:
    """Mapped measures with no cell whose rows all match, so no cut tests the formula."""
    tested = {(c.sheet, c.measure) for c in cells if c.verdict in (PASS, FORMULA_GAP)}
    return [
        (s, h)
        for s, sm in checks.sheets.items()
        for h, m in sm.measures.items()
        if m.cube and (s, h) not in tested
    ]


def _formula(twb_text: str, measure: str, params: dict[str, str]) -> str | None:
    """The measure's calculation, narrowed to the branch a cut's parameter picks."""
    whole = workbook.measure_formula(twb_text, measure, None)
    for p in params.items():
        got = workbook.measure_formula(twb_text, measure, p)
        if got != whole:
            return got
    return whole


def render(
    checks,
    manifest: dict,
    rows_result,
    cells: list,
    results: dict,
    twb_text: str,
    answers: dict,
) -> str:
    inv = {**(manifest.get("invariants") or {}), **rows_result.invariants}
    out = [f"# {checks.dashboard}: Cube validation", ""]
    out += [
        "## Trust verdict",
        "",
        trust(inv, results, compared(cells)),
        "",
        "Unit tests are part of trust: `uv run --with tableauhyperapi pytest tests/scripts/cube_validate`.",
        "",
    ]
    out += ["## Invariants", "", "| Invariant | Holds |", "| --- | --- |"]
    out += [f"| {k} | {'yes' if v else '**no**'} |" for k, v in inv.items()]
    out += ["", "## Capture", ""]
    for k in (
        "period",
        "extract_refreshed",
        "cube_refresh",
        "cost",
        "scope_size",
        "clock_risk",
    ):
        if k in manifest:
            out.append(f"- {k.replace('_', ' ')}: {manifest[k]}")
    out += [
        "",
        "## Findings (held until the tool is trusted)",
        "",
        "### Row buckets",
        "",
    ]
    t = rows_result.totals
    out.append(
        f"Dashboard rows {small(t['tableau'])}, Cube rows {small(t['cube'])}, joined {small(t['joined'])}."
    )
    out.append("")
    if rows_result.buckets:
        keys = [k for k in rows_result.buckets[0] if k not in ("rows", "students")]
        out += [
            "| " + " | ".join(keys) + " | rows | students |",
            "| " + " | ".join("---" for _ in keys) + " | --- | --- |",
        ]
        for b in rows_result.buckets:
            out.append(
                "| "
                + " | ".join(str(b[k]) for k in keys)
                + f" | {small(b['rows'])} | {small(b['students'])} |"
            )
    if rows_result.differing_columns:
        out += [
            "",
            "Value differences by column: "
            + ", ".join(
                f"{k} {small(v)}" for k, v in rows_result.differing_columns.items()
            ),
        ]
    out += ["", "### Cell verdicts", "", "| Verdict | Cells |", "| --- | --- |"]
    counts = Counter(c.verdict for c in cells)
    out += [f"| {v} | {small(counts[v])} |" for v in ORDER if counts[v]]
    gaps = [c for c in cells if c.verdict in (ROW_GAP, FORMULA_GAP)]
    if gaps:
        out += [
            "",
            "| Cut | Sheet | Measure | Marks | Verdict | Tableau | Cube |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for c in gaps:
            marks = ", ".join(f"{k}={v}" for k, v in c.dims.items())
            out.append(
                f"| {c.cut} | {c.sheet} | {c.measure} | {marks} | {c.verdict} | {_mask(c.tableau)} | {_mask(c.cube)} |"
            )
    out += _row_gap_buckets(gaps)
    shown = set()
    cut_params = {c.id: c.params for c in getattr(checks, "cuts", ())}
    for c in cells:
        params = cut_params.get(c.cut, {})
        key = (c.sheet, c.measure, tuple(sorted(params.items())))
        if c.verdict != FORMULA_GAP or key in shown:
            continue
        shown.add(key)
        out += [
            "",
            f"#### Formula gap: {c.sheet} / {c.measure}",
            "",
            "Workbook formula:",
            "",
            "```text",
            _formula(twb_text, c.measure, params) or "(no calculation found)",
            "```",
            "",
            "Cube SQL:",
            "",
            "```sql",
            (answers.get(answer_key(c.cut, c.sheet)) or {}).get("sql", ""),
            "```",
        ]
    out += ["", "### Formulas not tested", ""]
    out += [f"- {s} / {m}" for s, m in _untested(checks, cells)] or ["- (none)"]
    out += ["", "## Not checked", ""]
    out += [f"- {s}: {why}" for s, why in checks.excluded_sheets.items()] or [
        "- (none)"
    ]
    return "\n".join(out) + "\n"
