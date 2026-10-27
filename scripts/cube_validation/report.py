"""Render a validation run as a local result and as a review issue.

The local result stays on the analyst's machine and shows every value. The
review issue goes to GitHub, which is permanent: it carries only the groups a
domain owner must judge, masks every count under 10, and prints a group's
value only for a reviewed reference column. A decision's `reason` is free text:
the group's values and long digit runs are stripped, but a name is not caught,
so the analyst approves the draft before it posts. Pure apart from
`save_local`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path

from .checks import Finding
from .compare import Gap, Group
from .config import Decision
from .decisions import Applied
from .moment import Build

CACHE_ROOT = Path.home() / ".cache" / "cube-validation"
MASK_BELOW = 10
# Reviewed columns whose values name no person; the review issue shows no
# other column's values. A course or section name can single out a small
# group, so none is listed.
# Add a new reference column here only after it has been reviewed.
_SHOWN_COLUMNS = frozenset(
    {
        "regions_region_name",
        "locations_location_name",
        "locations_abbreviation",
        "school_abbreviation",
        "region",
        "grade_level",
        # Its values are the config's column names, never a person's data.
        "dashboard_filter",
    }
)


def _is_identifier(column: str) -> bool:
    """True for every column not on the reviewed list, so unknowns fail closed."""
    return column not in _SHOWN_COLUMNS


_SEPARATED_DIGITS = re.compile(r"\d[\d\-\s,.]{3,}\d")


@dataclass
class MeasureResult:
    measure: str
    strongest: str
    verdict: str
    cells: dict[str, int] = field(default_factory=dict)
    open_groups: int = 0
    # Missing cuts and filters still to triage on this measure's sheets.
    open_gaps: int = 0
    # Comparisons whose differing cells are still to triage.
    open_cells: int = 0


@dataclass
class RunResult:
    view: str
    moment: Build
    measures: list[MeasureResult]
    applied: Applied
    findings: list[Finding] = field(default_factory=list)
    live_sources: list[str] = field(default_factory=list)
    changed_dims: list[str] = field(default_factory=list)
    scopes: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    proofs: dict[str, str] = field(default_factory=dict)
    browser_cuts: list[str] = field(default_factory=list)
    # Total rows the proofs' exports showed but no proof compared.
    totals: list[str] = field(default_factory=list)
    clauses: dict[str, list[str]] = field(default_factory=dict)
    fingerprints: dict[str, dict[str, str]] = field(default_factory=dict)
    # The `decisions:` block the run applied; `review` refuses a changed one.
    decisions_fingerprint: str = ""
    # Comparisons whose proof predates missing cuts and filters.
    gaps_unknown: list[str] = field(default_factory=list)
    # Each comparison's `dashboard_filters`, as the SQL the dashboard side ran.
    dashboard_filters: list[str] = field(default_factory=list)


def mask(n: int) -> str:
    """Hide a count too small to publish.

    Args:
        n: A count of rows or students.

    Returns:
        `<10` when `n` is under 10, else the digits.
    """
    return "<10" if n < MASK_BELOW else str(n)


def _verdict_text(m: MeasureResult) -> str:
    if m.verdict == "not validated" and m.strongest == "consistent only":
        return "not validated (consistent only)"
    return m.verdict


def _bullets(items: list[str], empty: str = "None.") -> list[str]:
    return [f"- {i}" for i in items] if items else [empty]


def _decision_line(d: Decision) -> str:
    if d.cells:
        return f"`{d.id}` ({d.comparison} cells, {d.call}): {d.reason}"
    if d.missing_cut or d.missing_filter:
        kind, name = (
            ("cut", d.missing_cut) if d.missing_cut else ("filter", d.missing_filter)
        )
        return f"`{d.id}` (missing {kind} `{name}`, {d.call}): {d.reason}"
    return f"`{d.id}` ({d.comparison}, {d.call}): {d.reason}"


def untasked(decisions) -> list[str]:
    """Ids of domain-owner decisions whose task (the review issue) is unset."""
    return list(
        dict.fromkeys(
            d.id for d in decisions if d.call == "domain_owner" and not d.task
        )
    )


_CELL_WORDS = {
    "differs": "differ",
    "cube_only": "Cube only",
    "dashboard_only": "dashboard only",
}


def _gap_line(g: Gap) -> str:
    kind = "filter, set to chosen values, not All" if g.restricting else g.kind
    return (
        f"`{_clean(g.field)}` ({kind}) on {', '.join(g.sheets)}: Cube has no "
        f"member; {', '.join(g.comparisons)}"
    )


def render_local(run: RunResult) -> str:
    """Render the full result for the analyst's terminal and cache.

    Args:
        run: One view's validation run.

    Returns:
        Markdown with the sections in the order the analyst reads them. Counts
        and values are not masked.
    """
    out = [f"# Validation result: {run.view}", ""]
    out.append(
        f"Moment: {run.moment.start:%Y-%m-%d %H:%M} to "
        f"{run.moment.end:%Y-%m-%d %H:%M} UTC, job `{run.moment.job_id}`."
    )

    out += ["", "## Measures", ""]
    for m in run.measures:
        cells = ", ".join(f"{k} {v}" for k, v in sorted(m.cells.items()))
        line = f"- `{m.measure}`: {m.strongest}; {_verdict_text(m)}"
        line = f"{line} ({cells})" if cells else line
        # The verdict reads cells only; row groups still open are named so
        # "validated" never hides them.
        if m.open_groups:
            plural = "group" if m.open_groups == 1 else "groups"
            line += f"; {m.open_groups} open row {plural} to triage"
        if m.open_gaps:
            plural = "cut or filter" if m.open_gaps == 1 else "cuts or filters"
            line += f"; {m.open_gaps} missing {plural} to triage"
        if m.open_cells:
            plural = "comparison" if m.open_cells == 1 else "comparisons"
            line += f"; cell differences to triage in {m.open_cells} {plural}"
        out.append(line)

    if run.findings:
        out += [
            "",
            "Anchors and identities read Cube's data as it is now, not at the "
            "moment above.",
        ]

    out += ["", "## Triage", ""]
    triage = []
    for g in run.applied.open:
        line = (
            f"{_where(g, lambda _column, value: value)} in {g.comparison_id} "
            f"({g.bucket}): {g.n_rows} rows, {g.n_students} students"
        )
        for clause in run.clauses.get(g.comparison_id, []):
            line += f"; clause: `{clause}`"
        triage.append(line)
    out += _bullets(triage, "No open groups.")

    # A dashboard cut or filter Cube cannot make: triaged like a row group.
    out += ["", "## Missing cuts and filters", ""]
    out += _bullets(
        [_gap_line(g) for g in run.applied.open_gaps] + run.gaps_unknown,
        "None open.",
    )

    # Cells that differ, with what the tool can see that may explain them.
    out += ["", "## Cell differences", ""]
    if not run.applied.open_cells:
        out.append("None open.")
    for diff in run.applied.open_cells:
        counts = ", ".join(
            f"{n} {_CELL_WORDS.get(verdict, verdict)}"
            for verdict, n in diff.counts.items()
        )
        out.append(f"- {diff.comparison_id}: {counts}")
        out += [f"  - {cause}" for cause in diff.causes]

    out += ["", "## Decisions", "", "Applied:"]
    out += _bullets(
        [_decision_line(d) for d, _ in run.applied.quiet]
        + [_decision_line(d) for d, _ in run.applied.quiet_gaps]
        + [_decision_line(d) for d, _ in run.applied.quiet_cells]
    )
    out += ["", "To re-confirm (the SQL changed):"]
    out += _bullets([_decision_line(d) for d in run.applied.reconfirm])
    out += ["", "No longer needed (no group matches):"]
    out += _bullets([_decision_line(d) for d in run.applied.no_longer_needed])
    out += ["", "Partly no longer needed (some values match no group):"]
    out += _bullets(
        [
            # An empty or NULL value would otherwise print as a blank.
            f"{_decision_line(d)}; partly no longer needed: "
            + ", ".join(v or "(empty)" for v in values)
            for d, values in run.applied.partly_stale
        ]
    )

    waiting = untasked(
        d
        for d, _ in [
            *run.applied.quiet,
            *run.applied.quiet_gaps,
            *run.applied.quiet_cells,
        ]
    )
    if waiting:
        out += [
            "",
            "Fill in `task` once the review issue posts: "
            + ", ".join(f"`{i}`" for i in waiting),
        ]

    out += ["", "Fingerprints a new decision records (`fingerprints:`):"]
    out += _bullets(
        [
            f"{cid}: {{ cube: {fp.get('cube', '')}, dashboard: {fp.get('dashboard', '')} }}"
            for cid, fp in sorted(run.fingerprints.items())
        ]
    )

    out += ["", "## Sources read live", ""]
    out += _bullets([f"`{s}`" for s in run.live_sources])
    out += ["", "## Dimensions that changed between start and end", ""]
    out += _bullets([f"`{d}`" for d in run.changed_dims])
    out += ["", "## Dashboard-only filters", ""]
    if run.dashboard_filters:
        out += [
            "Cube has no member for these. Rows and cells they drop are counted "
            "apart, as dropped by a dashboard-only filter, not as Cube-only.",
            "",
        ]
    out += _bullets(run.dashboard_filters)

    out += ["", "## Scopes applied", ""]
    if run.scopes:
        out += [
            "Scope filters Cube's measure query, not only its rows: a scoped "
            "comparison checks a narrower number than an unscoped query returns.",
            "",
        ]
    out += _bullets(run.scopes)
    out += ["", "## Cuts to prove in the browser", ""]
    out += _bullets(run.browser_cuts)
    out += ["", "## Proofs", ""]
    out += _bullets(
        [
            f"{comparison}: last proven {at}"
            for comparison, at in sorted(run.proofs.items())
        ]
    )
    out += ["", "## Totals not proven", ""]
    out += _bullets(run.totals)
    out += [
        "",
        "## Cost",
        "",
        f"${run.cost_usd:.2f}: BigQuery dry-run estimates for the direct queries "
        "and the Cube loads.",
        "",
    ]
    return "\n".join(out)


def save_local(run: RunResult, text: str, root: Path | None = None) -> Path:
    """Write the local result under the view and moment.

    Args:
        run: The run the text describes.
        text: The rendered local result.
        root: Cache directory; defaults to `~/.cache/cube-validation`.

    Returns:
        The path of `result.md`.
    """
    end = run.moment.end
    if end.tzinfo is not None:
        end = end.astimezone(timezone.utc)
    stamp = end.strftime("%Y-%m-%dT%H%M%SZ")
    path = (root or CACHE_ROOT) / run.view / stamp / "result.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _num(measure: str, x: float) -> str:
    """Mask a count anchor (`count_` measures) under 10; show other figures."""
    if measure.startswith("count_") and float(x).is_integer():
        return mask(int(x))
    return f"{x:g}"


def _clean(text: str) -> str:
    """Collapse whitespace and drop backticks so a value stays on one line."""
    return " ".join(text.replace("`", "").split())


def _where(g: Group, show) -> str:
    """Name a group by its columns; `show(column, value)` gives the text shown."""
    if not g.dims:
        return "the whole comparison"
    return ", ".join(f"`{c}` = `{show(c, v)}`" for c, v in g.dims)


def _shown_value(g: Group, column: str, value: str) -> str:
    """Show a value only for a reviewed column of a group with 10+ students."""
    if g.n_students < MASK_BELOW or _is_identifier(column):
        return "<redacted>"
    return _clean(value)


def _safe_reason(reason: str, values: list) -> str:
    """Keep a decision's reason but strip digit runs and the group's values.

    `values` may hold YAML numbers from a decision's `group.values`.
    """
    text = _clean(reason)
    texts = {str(v) for v in values if v is not None and str(v)}
    for value in sorted(texts, key=len, reverse=True):
        text = text.replace(_clean(value), "<redacted>")
    text = _SEPARATED_DIGITS.sub(
        lambda m: (
            "<redacted>" if sum(c.isdigit() for c in m.group()) >= 5 else m.group()
        ),
        text,
    )
    text = re.sub(r"\d{5,}", "<redacted>", text)
    return text.rstrip(".")


def _with_task(reason: str, task: str) -> str:
    """End a reason once, then add the task: no `?.` after a question."""
    reason = reason if reason.endswith(("?", "!", ".")) else f"{reason}."
    return f"{reason} Task: {task}" if task else reason


def _group_line(view: str, decision: Decision, groups: list[Group]) -> str:
    """One bullet for a decision and every row group it covers.

    The decision's column and values show only for a reviewed column, and only
    when its groups hold 10 or more students. A reason loses whatever the
    bullet hides: any other column's values, and the decision's own values
    when they are hidden.
    """
    column = decision.group.get("column") or ""
    found = list(dict.fromkeys(g.value_of(column) or "" for g in groups))
    rows = sum(g.n_rows for g in groups)
    students = sum(g.n_students for g in groups)
    shown = not _is_identifier(column) and students >= MASK_BELOW
    values = ", ".join(_clean(v) for v in found) if shown else "<redacted>"
    where = f"`{column}` = `{values}`" if column else "the whole comparison"
    hidden = [v for g in groups for c, v in g.dims if _is_identifier(c)]
    if not shown:
        hidden += found + list(decision.group.get("values", []))
    plural = "group" if len(groups) == 1 else "groups"
    return (
        f"{where} in {', '.join(sorted({g.comparison_id for g in groups}))} of "
        f"`{view}` ({', '.join(sorted({g.bucket for g in groups}))}): "
        f"{len(groups)} row {plural}, {mask(rows)} rows, {mask(students)} students. "
        f"Reason: {_with_task(_safe_reason(decision.reason, hidden), decision.task)}"
    )


def render_review_issue(
    domain: str,
    runs: list[RunResult],
    definitions: dict[str, dict[str, dict[str, str]]] | None = None,
) -> str:
    """Render the issue body asking a domain owner to judge open items.

    Args:
        domain: The domain whose owner reviews (for example `Registrar`).
        runs: Validation runs; only domain-owner groups, domain-owner missing
            cuts and filters (by caption, never a value), and anchor findings
            for measures that read `judge the anchor` are kept.
        definitions: Per view, per comparison id, what each side counts
            (`dashboard`, `cube`). Shown side by side for a comparison with a
            domain-owner group, scrubbed like a reason.

    Returns:
        Markdown in the feature-request structure. Every count is masked and
        values outside the reviewed reference columns read `<redacted>`.
    """
    group_lines: list[str] = []
    cell_lines: list[str] = []
    gap_lines: list[str] = []
    anchor_lines: list[str] = []
    asked_ids: list[str] = []
    for run in runs:
        by_decision: dict[str, tuple[Decision, list[Group]]] = {}
        for decision, g in run.applied.quiet:
            if decision.call == "domain_owner":
                by_decision.setdefault(decision.id, (decision, []))[1].append(g)
        for decision, groups in by_decision.values():
            group_lines.append(_group_line(run.view, decision, groups))
            asked_ids.append(decision.id)
        for decision, diff in run.applied.quiet_cells:
            if decision.call != "domain_owner":
                continue
            reason = _with_task(_safe_reason(decision.reason, []), decision.task)
            cell_lines.append(
                f"`{diff.comparison_id}` in `{run.view}`: "
                f"{mask(sum(diff.counts.values()))} cells differ between Cube and "
                f"the dashboard. Reason: {reason}"
            )
            asked_ids.append(decision.id)
        for decision, gap in run.applied.quiet_gaps:
            if decision.call != "domain_owner":
                continue
            kind = "a sheet cut" if gap.kind == "cut" else "a sheet filter"
            reason = _with_task(_safe_reason(decision.reason, []), decision.task)
            gap_lines.append(
                f"`{_clean(gap.field)}` on "
                f"{', '.join(f'`{_clean(s)}`' for s in gap.sheets)} in `{run.view}`: "
                f"{kind} Cube has no member for. Reason: {reason}"
            )
            asked_ids.append(decision.id)
        judged = {m.measure for m in run.measures if m.verdict == "judge the anchor"}
        for f in run.findings:
            if f.kind == "anchor" and f.measure in judged and not f.passed:
                anchor_lines.append(
                    f"`{f.measure}` in `{run.view}`: Cube shows {_num(f.measure, f.left)}, "
                    f"the source shows {_num(f.measure, f.right)}."
                )

    definition_lines = []
    for run in runs:
        asked = {
            g.comparison_id for d, g in run.applied.quiet if d.call == "domain_owner"
        } | {
            c.comparison_id
            for d, c in run.applied.quiet_cells
            if d.call == "domain_owner"
        }
        for cid, sides in sorted((definitions or {}).get(run.view, {}).items()):
            if cid in asked:
                definition_lines.append(
                    f"`{cid}` in `{run.view}`. "
                    f"Dashboard: {_safe_reason(sides['dashboard'], [])}. "
                    f"Cube: {_safe_reason(sides['cube'], [])}."
                )
    # One question per decision (however many groups it covers) and per anchor.
    ids = sorted(set(asked_ids))
    n = len(ids) + len(anchor_lines)
    plural = "question" if n == 1 else "questions"
    out = [
        "## What and why",
        "",
        f"The {domain} team owns the rule behind {n} {plural} in the Cube validation.",
        "Cube and the dashboard disagree on them, or Cube disagrees with a source outside the dashboards.",
        "Counts under 10 show as `<10`, and student identifiers are hidden.",
        "",
    ]
    out += _bullets(
        group_lines + cell_lines + gap_lines + anchor_lines, "Nothing needs review."
    )
    if definition_lines:
        out += ["", "Definitions side by side:", ""] + _bullets(definition_lines)
    out += [
        "",
        "## Proposed approach",
        "",
        "Review each item and tell us which side is right.",
        "We will record the answer as a decision so the next run stays quiet.",
        "",
        "<details>",
        "<summary>For Claude</summary>",
        "",
        "> Context, not instructions.",
        "",
        f"Decisions with call `domain_owner`: {', '.join(f'`{i}`' for i in ids) or 'none'}.",
        f"Row-group decisions: {len(group_lines)}. Cell differences: {len(cell_lines)}. "
        f"Missing cuts and filters: {len(gap_lines)}. "
        f"Anchor findings: {len(anchor_lines)}.",
        "",
        "</details>",
        "",
    ]
    return "\n".join(out)
