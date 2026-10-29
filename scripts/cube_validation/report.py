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

import json
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
        "academic_year",
        "dates_academic_year",
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
    # Comparison id to the reshape its proof's copy carried (`dropped ...;
    # added ...`): that proof covers the reshaped grain, not the sheet's own.
    reshaped: dict[str, str] = field(default_factory=dict)
    clauses: dict[str, list[str]] = field(default_factory=dict)
    fingerprints: dict[str, dict[str, str]] = field(default_factory=dict)
    # The `decisions:` block the run applied; `review` refuses a changed one.
    decisions_fingerprint: str = ""
    # Comparisons whose proof predates missing cuts and filters.
    gaps_unknown: list[str] = field(default_factory=list)
    # Each comparison's `dashboard_filters`, as the SQL the dashboard side ran.
    dashboard_filters: list[str] = field(default_factory=list)
    # What the result was proven against: the Cube server's host and the
    # `dataset.table` fact, so an analyst can say so in a PR description.
    cube_host: str = ""
    fact: str = ""
    # What an owner's hand check needs, kept in run.json and never printed:
    # each cell that neither passes nor is dashboard-filtered (`comparison`,
    # `cut`, `key`, `dims` as Cube name and value pairs, `dashboard`, `cube`,
    # `n_students`, None without `rows`), and per comparison and cut label
    # the [dashboard, Cube] SQL the run executed and each one's dry-run USD.
    diff_cells: list[dict] = field(default_factory=list)
    cell_sql: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    cell_sql_usd: dict[str, dict[str, list[float]]] = field(default_factory=dict)


def mask(n: int) -> str:
    """Hide a count too small to publish.

    Args:
        n: A count of rows or students.

    Returns:
        `<10` when `n` is under 10, else the digits.
    """
    return "<10" if n < MASK_BELOW else str(n)


SUPPRESSED = "masked"


def suppress(total: int, parts: list[int]) -> tuple[str, list[str]]:
    """Mask a total and its parts so no small part can be worked out.

    Each part under `MASK_BELOW` reads `<10`. The total minus the shown parts
    gives the masked parts' sum, so the masked parts must hold `MASK_BELOW` or
    more together and include at least one `masked` part with no upper bound:
    `<10` parts alone are pinned by their sum (18 over two `<10` parts is 9
    and 9). Until both hold, the next-smallest shown part reads `masked` too.
    When no part is left to mask, the total reads `masked`, or `<10` when it
    is under `MASK_BELOW`.

    Returns:
        The total's text and each part's, in order.
    """
    hidden = {i for i, n in enumerate(parts) if n < MASK_BELOW}
    shown = sorted(
        (i for i in range(len(parts)) if i not in hidden), key=parts.__getitem__
    )
    extra: set[int] = set()
    while (
        hidden
        and shown
        and (not extra or sum(parts[i] for i in hidden | extra) < MASK_BELOW)
    ):
        extra.add(shown.pop(0))
    texts = [
        "<10" if i in hidden else SUPPRESSED if i in extra else str(n)
        for i, n in enumerate(parts)
    ]
    if hidden and not extra and total >= MASK_BELOW:
        return SUPPRESSED, texts
    return mask(total), texts


def shown_counts(total: int, parts: list[int], posted: bool) -> tuple[str, list[str]]:
    """A total and its parts as text: masked only where the text is posted.

    Text bound for GitHub or a commit (the review issue, decision YAML, the
    run report the runbook posts) goes through `suppress`. The terminal and
    the local cache show exact counts.
    """
    if posted:
        return suppress(total, parts)
    return str(total), [str(n) for n in parts]


def _verdict_text(m: MeasureResult) -> str:
    if m.verdict == "not validated" and m.strongest == "consistent only":
        return "not validated (consistent only)"
    return m.verdict


def _bullets(items: list[str], empty: str = "None.") -> list[str]:
    return [f"- {i}" for i in items] if items else [empty]


def _decision_line(d: Decision) -> str:
    if d.cause:
        return (
            f"`{d.id}` ({d.comparison} {d.cause.get('side')} step "
            f"`{_clean(str(d.cause.get('step')))}`, {d.call}): {d.reason}"
        )
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
    out += ["", f"Cube: {run.cube_host}", "", f"Fact: {run.fact}"]

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
        # A cause decision quiets many groups; it is listed once.
        + list(dict.fromkeys(_decision_line(d) for d, _ in run.applied.quiet_causes))
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
            *run.applied.quiet_causes,
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
            + (
                f"; proven on a reshaped copy: {run.reshaped[comparison]}"
                if comparison in run.reshaped
                else ""
            )
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


def _by_reason(pairs) -> list[tuple[list[Decision], list]]:
    """Domain-owner decisions grouped by their reason and task, each with the
    items they cover, in first-seen order: one shared reason, one question.
    """
    out: dict[tuple[str, str], tuple[list[Decision], list]] = {}
    for decision, item in pairs:
        if decision.call != "domain_owner":
            continue
        decisions, items = out.setdefault((decision.reason, decision.task), ([], []))
        if decision not in decisions:
            decisions.append(decision)
        items.append(item)
    return list(out.values())


def _group_part(
    view: str, decisions: list[Decision], groups: list[Group]
) -> tuple[str, list]:
    """The row-group part of a question, and the values its reason must lose.

    The decision's column shows each value only for a reviewed column, and only
    when that value's groups hold 10 or more students. A reason loses whatever
    the bullet hides: any other column's values, and each hidden value of the
    decision's own. Other dims of a group never show in the bullet; a reason
    is free text the analyst approves, so it must not name them for a small
    group either.
    """
    columns = {d.group.get("column") or "" for d in decisions}
    # Decisions on different columns name none; their values stay hidden.
    column = columns.pop() if len(columns) == 1 else ""
    found = list(dict.fromkeys(g.value_of(column) or "" for g in groups))
    rows = sum(g.n_rows for g in groups)
    # Students are counted within one comparison only: the same students sit in
    # every comparison on a sheet, so a sum across them counts them again.
    per_comparison: dict[str, int] = {}
    per_value: dict[tuple[str, str], int] = {}
    for g in groups:
        value = g.value_of(column) or ""
        per_comparison[g.comparison_id] = (
            per_comparison.get(g.comparison_id, 0) + g.n_students
        )
        key = (g.comparison_id, value)
        per_value[key] = per_value.get(key, 0) + g.n_students
    students = max(per_comparison.values())
    # A value shows only when one comparison alone has 10 of its students.
    shown = (
        set()
        if _is_identifier(column)
        else {v for (_, v), n in per_value.items() if n >= MASK_BELOW}
    )
    values = ", ".join(
        dict.fromkeys(_clean(v) if v in shown else "<redacted>" for v in found)
    )
    where = f"`{column}` = `{values}`" if column else "the whole comparison"
    hidden = [v for g in groups for c, v in g.dims if _is_identifier(c)]
    hidden += [
        v
        for v in [*found, *(v for d in decisions for v in d.group.get("values", []))]
        if str(v) not in shown
    ]
    plural = "group" if len(groups) == 1 else "groups"
    who = (
        f"{mask(students)} students"
        if len(per_comparison) == 1
        else f"up to {mask(students)} students per comparison"
    )
    return (
        f"{where} in {', '.join(sorted(per_comparison))} of "
        f"`{view}` ({', '.join(sorted({g.bucket for g in groups}))}): "
        f"{len(groups)} row {plural}, {mask(rows)} rows, {who}"
    ), hidden


def _by_cause(pairs) -> list[tuple[Decision, list[Group]]]:
    """Domain-owner cause decisions, each with its groups, in first-seen order."""
    out: dict[str, tuple[Decision, list[Group]]] = {}
    for decision, group in pairs:
        if decision.call == "domain_owner":
            out.setdefault(decision.id, (decision, []))[1].append(group)
    return list(out.values())


def _cause_part(view: str, d: Decision, groups: list[Group]) -> tuple[str, list]:
    """A cause question's part, and the values its reason must lose.

    It names the step, never a group's values, and masks the counts of its
    groups and of their rows.
    """
    rows = sum(g.n_rows for g in groups)
    plural = "group" if len(groups) == 1 else "groups"
    hidden = [
        v for g in groups for c, v in g.dims if _shown_value(g, c, v) == "<redacted>"
    ]
    return (
        f"step `{_clean(str(d.cause.get('step')))}` on the "
        f"{d.cause.get('side')} side of `{d.comparison}` in `{view}` "
        f"({', '.join(sorted({g.bucket for g in groups}))}): "
        f"{mask(len(groups))} row {plural}, {mask(rows)} rows"
    ), hidden


def _gap_part(view: str, gaps: list[Gap]) -> str:
    if len(gaps) == 1:
        kind = "a sheet cut" if gaps[0].kind == "cut" else "a sheet filter"
    else:
        kind = {
            frozenset({"cut"}): "sheet cuts",
            frozenset({"filter"}): "sheet filters",
        }.get(frozenset(g.kind for g in gaps), "sheet cuts and filters")
    sheets = list(dict.fromkeys(s for g in gaps for s in g.sheets))
    return (
        f"{', '.join(f'`{_clean(g.field)}`' for g in gaps)} on "
        f"{', '.join(f'`{_clean(s)}`' for s in sheets)} in `{view}`: "
        f"{kind} Cube has no member for"
    )


def _questions(runs: list[RunResult]) -> list[dict]:
    """Group the runs' domain-owner decisions into the review's questions.

    One question per reason and task, across decision kinds and files: each
    kind and view adds a part to its bullet, and the reason prints once. A
    cause decision is its own question, whatever its reason: one per cause
    and task, never one per school.

    Returns:
        In the order the issue asks them, dicts of `reason`, `task`, `parts`
        (the masked count text per kind and view), `kinds`, `hidden` (values
        the reason and any evidence must lose), `decisions` as (view,
        Decision) pairs and `comparisons` as (view, comparison id, kind)
        triples, each listed once; a cause question also has `n_groups`.
    """
    questions: dict[tuple, dict] = {}

    def add(view, kind, decisions, part, hidden, comparisons, key=None) -> None:
        d = decisions[0]
        q = questions.setdefault(
            key or (d.reason, d.task),
            {
                "reason": d.reason,
                "task": d.task,
                "parts": [],
                "kinds": [],
                "hidden": [],
                "decisions": [],
                "comparisons": [],
            },
        )
        q["parts"].append(part)
        q["kinds"].append(kind)
        q["hidden"] += hidden
        q["decisions"] += [(view, x) for x in decisions]
        for cid in comparisons:
            if (view, cid) not in [(v, c) for v, c, _ in q["comparisons"]]:
                q["comparisons"].append((view, cid, kind))

    for run in runs:
        for decisions, groups in _by_reason(run.applied.quiet):
            part, hidden = _group_part(run.view, decisions, groups)
            add(
                run.view,
                "group",
                decisions,
                part,
                hidden,
                [g.comparison_id for g in groups],
            )
        for decision, groups in _by_cause(run.applied.quiet_causes):
            part, hidden = _cause_part(run.view, decision, groups)
            add(
                run.view,
                "cause",
                [decision],
                part,
                hidden,
                [decision.comparison],
                key=("cause", run.view, decision.id, decision.task),
            )
            questions[("cause", run.view, decision.id, decision.task)]["n_groups"] = (
                len(groups)
            )
        for decisions, diffs in _by_reason(run.applied.quiet_cells):
            add(
                run.view,
                "cells",
                decisions,
                f"{', '.join(f'`{c.comparison_id}`' for c in diffs)} in `{run.view}`: "
                f"{mask(sum(n for c in diffs for n in c.counts.values()))} cells "
                "differ between Cube and the dashboard",
                [],
                [c.comparison_id for c in diffs],
            )
        for decisions, gaps in _by_reason(run.applied.quiet_gaps):
            add(
                run.view,
                "gap",
                decisions,
                _gap_part(run.view, gaps),
                [],
                [c for g in gaps for c in g.comparisons],
            )
    return list(questions.values())


def question_reason(q: dict) -> str:
    """The question's reason as the issue shows it, without its task."""
    return _safe_reason(q["reason"], q["hidden"])


def defined_comparisons(questions: list[dict], view: str) -> set[str]:
    """The view's comparisons whose definitions the issue shows.

    Those are the comparisons with a domain-owner row group, cause or cell
    difference.
    """
    return {
        cid
        for q in questions
        for v, cid, kind in q["comparisons"]
        if v == view and kind in ("group", "cause", "cells")
    }


def definition_text(text: str) -> str:
    """A comparison's definition as the issue shows it, scrubbed like a reason."""
    return _safe_reason(text, [])


def _dashboard_location(check: dict) -> str:
    """Where to read a hand check's dashboard number: its sheet and filters.

    Filter values are shown like the cut, which already carries them.
    """
    sheet = check.get("sheet")
    where = f"sheet `{_clean(sheet)}`" if sheet else ""
    if sheet and check.get("workbook"):
        where += f" in `{_clean(check['workbook'])}`"
    filters = check.get("filters") or {}
    settings = "; ".join(
        f"`{_clean(caption)}` = "
        + ", ".join(
            f"`{_clean(str(v))}`"
            for v in (value if isinstance(value, list) else [value])
        )
        for caption, value in filters.items()
    )
    if settings:
        todo = f"set {settings}"
    else:
        todo = "leave its filters as they are" if where else ""
    if not where and not todo:
        return "On the dashboard: leave the sheet's filters as they are."
    return f"On the dashboard: {', '.join(p for p in (where, todo) if p)}."


def _hand_check_lines(question_id: str, check: dict) -> list[str]:
    """One question's hand check: what to expect, then the pinned SQL folded."""
    where = f"{question_id}, `{check['comparison']}` in `{check['view']}`"
    if "none" in check:
        return [f"{where}: {check['none']}.", ""]
    dims = ", ".join(f"`{c}` = `{_clean(v)}`" for c, v in check["dims"])
    line = (
        f"{where}, cut `{_clean(check['cut'])}`"
        f"{', ' + dims if dims else ', the total'}: the dashboard shows "
        f"{check['dashboard']}, Cube shows {check['cube']}. "
    )
    if check["expired"]:
        line += (
            f"The pinned SQL stopped working at {check['expires']}; re-run `run` "
            "for a fresh moment."
        )
    else:
        line += f"The pinned SQL works until {check['expires']}."
    return [
        line,
        "",
        _dashboard_location(check),
        "",
        "<details>",
        f"<summary>BigQuery SQL for each side (dry run: dashboard "
        f"${check['dashboard_usd']:.2f}, Cube ${check['cube_usd']:.2f})</summary>",
        "",
        "Dashboard:",
        "",
        "```sql",
        check["dashboard_sql"],
        "```",
        "",
        "Cube:",
        "",
        "```sql",
        check["cube_sql"],
        "```",
        "",
        "</details>",
        "",
    ]


def render_review_issue(
    domain: str,
    runs: list[RunResult],
    definitions: dict[str, dict[str, dict[str, str]]] | None = None,
    questions: list[dict] | None = None,
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
        questions: `answers.questions_json` for the same runs. When given, each
            question's hand checks follow the bullets, and the body ends with
            the list as a fenced JSON block for the owner's Claude session.

    Returns:
        Markdown in the feature-request structure. Every count is masked and
        values outside the reviewed reference columns read `<redacted>`.
    """
    asked = _questions(runs)
    kinds = [k for q in asked for k in q["kinds"]]
    asked_ids = [d.id for q in asked for _, d in q["decisions"]]
    anchor_lines: list[str] = []
    for run in runs:
        judged = {m.measure for m in run.measures if m.verdict == "judge the anchor"}
        for f in run.findings:
            if f.kind == "anchor" and f.measure in judged and not f.passed:
                anchor_lines.append(
                    f"`{f.measure}` in `{run.view}`: Cube shows {_num(f.measure, f.left)}, "
                    f"the source shows {_num(f.measure, f.right)}."
                )

    definition_lines = []
    for run in runs:
        shown = defined_comparisons(asked, run.view)
        for cid, sides in sorted((definitions or {}).get(run.view, {}).items()):
            if cid in shown:
                definition_lines.append(
                    f"`{cid}` in `{run.view}`. "
                    f"Dashboard: {definition_text(sides['dashboard'])}. "
                    f"Cube: {definition_text(sides['cube'])}."
                )
    # Numbered like the JSON's question ids, so a hand check names its bullet.
    question_lines = [
        f"Q{n}. {'; '.join(q['parts'])}. "
        f"Reason: {_with_task(question_reason(q), q['task'])}"
        for n, q in enumerate(asked, start=1)
    ]
    check_lines = [
        line
        for q in questions or []
        for check in q["hand_checks"]
        for line in _hand_check_lines(q["id"], check)
    ]
    # One question per bullet and per anchor finding.
    ids = sorted(set(asked_ids))
    n = len(question_lines) + len(anchor_lines)
    plural = "question" if n == 1 else "questions"
    out = [
        "## What and why",
        "",
        f"The {domain} team owns the rule behind {n} {plural} in the Cube validation.",
        "Cube and the dashboard disagree on them, or Cube disagrees with a source outside the dashboards.",
        "Counts under 10 show as `<10`, and identifiers of students and staff are hidden.",
        "",
    ]
    out += _bullets(question_lines + anchor_lines, "Nothing needs review.")
    if definition_lines:
        out += ["", "Definitions side by side:", ""] + _bullets(definition_lines)
    if check_lines:
        out += [
            "",
            "Checks to run yourself: the example cell with the biggest difference, "
            "and BigQuery SQL for each side pinned to the run's moment, to paste "
            "into the console under your own access. Tableau shows its last "
            "refresh, so a small difference may not match there.",
            "",
            *check_lines[:-1],
        ]
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
        f"Questions: {len(question_lines)}. Row-group parts: {kinds.count('group')}. "
        f"Cause parts: {kinds.count('cause')}. "
        f"Cell differences: {kinds.count('cells')}. "
        f"Missing cuts and filters: {kinds.count('gap')}. "
        f"Anchor findings: {len(anchor_lines)}.",
        "",
        "</details>",
        "",
    ]
    if questions is not None:
        out += [
            "<details>",
            "<summary>Questions for Claude (JSON)</summary>",
            "",
            "```json",
            json.dumps(questions, indent=1),
            "```",
            "",
            "</details>",
            "",
        ]
    return "\n".join(out)
