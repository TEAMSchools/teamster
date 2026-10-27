"""Render a validation run as a local result and as a review issue.

The local result stays on the analyst's machine and shows every value. The
review issue goes to GitHub, which is permanent: it carries only the groups a
domain owner must judge, masks every count under 10, and never prints a value
from a student-identifier column. Pure apart from `save_local`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path

from .checks import Finding
from .compare import Group
from .config import Decision
from .decisions import Applied
from .moment import Build

CACHE_ROOT = Path.home() / ".cache" / "cube-validation"
MASK_BELOW = 10
_IDENTIFIER_COLUMN = re.compile(
    r"student|lea_|_number|identifier|name|lastfirst|email|dob|birth|ssid|leaid|smid|phone|address|_id$|^id$|^sid$|state_id|local_id",
    re.IGNORECASE,
)
# Reviewed columns whose values name no person. The list is exact so an
# unknown column fails closed; a course or section name can single out a
# small group, so none is listed.
_SHOWN_COLUMNS = frozenset(
    {
        "regions_region_name",
        "locations_location_name",
        "locations_abbreviation",
        "school_abbreviation",
        "region",
        "grade_level",
    }
)


def _is_identifier(column: str) -> bool:
    """True unless the column is on the reviewed list or matches no pattern."""
    return column not in _SHOWN_COLUMNS and bool(_IDENTIFIER_COLUMN.search(column))


_SEPARATED_DIGITS = re.compile(r"\d[\d\-\s,.]{3,}\d")


@dataclass
class MeasureResult:
    measure: str
    strongest: str
    verdict: str
    cells: dict[str, int] = field(default_factory=dict)


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
    clauses: dict[str, list[str]] = field(default_factory=dict)
    fingerprints: dict[str, dict[str, str]] = field(default_factory=dict)


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
    return f"`{d.id}` ({d.comparison}, {d.call}): {d.reason}"


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
        out.append(f"{line} ({cells})" if cells else line)

    out += ["", "## Triage", ""]
    triage = []
    for g in run.applied.open:
        line = (
            f"`{g.column}` = `{g.value}` in {g.comparison_id} ({g.bucket}): "
            f"{g.n_rows} rows, {g.n_students} students"
        )
        for clause in run.clauses.get(g.comparison_id, []):
            line += f"; clause: `{clause}`"
        triage.append(line)
    out += _bullets(triage, "No open groups.")

    out += ["", "## Decisions", "", "Applied:"]
    out += _bullets([_decision_line(d) for d, _ in run.applied.quiet])
    out += ["", "To re-confirm (the SQL changed):"]
    out += _bullets([_decision_line(d) for d in run.applied.reconfirm])
    out += ["", "No longer needed (no group matches):"]
    out += _bullets([_decision_line(d) for d in run.applied.no_longer_needed])

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
    out += ["", "## Scopes applied", ""]
    out += _bullets(run.scopes)
    out += ["", "## Cuts to prove in the browser", ""]
    cuts = []
    for cut in run.browser_cuts:
        cuts.append(cut)
    for comparison, proven_at in sorted(run.proofs.items()):
        cuts.append(f"{comparison}: last proven {proven_at}")
    out += _bullets(cuts)
    out += ["", "## Cost", "", f"${run.cost_usd:.2f}", ""]
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


def _shown_value(g: Group) -> str:
    """Show a group's value only for a harmless column with 10+ students."""
    if g.n_students < MASK_BELOW or _is_identifier(g.column):
        return "<redacted>"
    return _clean(g.value)


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


def render_review_issue(domain: str, runs: list[RunResult]) -> str:
    """Render the issue body asking a domain owner to judge open items.

    Args:
        domain: The domain whose owner reviews (for example `Registrar`).
        runs: Validation runs; only domain-owner groups and anchor findings for
            measures that read `judge the anchor` are kept.

    Returns:
        Markdown in the feature-request structure. Every count is masked and
        student-identifier values are replaced with `<redacted>`.
    """
    group_lines: list[str] = []
    anchor_lines: list[str] = []
    for run in runs:
        for decision, g in run.applied.quiet:
            if decision.call != "domain_owner":
                continue
            line = (
                f"`{g.column}` = `{_shown_value(g)}` in "
                f"{g.comparison_id} of `{run.view}` ({g.bucket}): "
                f"{mask(g.n_rows)} rows, {mask(g.n_students)} students. "
                f"Reason: "
                f"{_safe_reason(decision.reason, [g.value, *decision.group.get('values', [])])}"
            )
            line += f". Task: {decision.task}" if decision.task else "."
            group_lines.append(line)
        judged = {m.measure for m in run.measures if m.verdict == "judge the anchor"}
        for f in run.findings:
            if f.kind == "anchor" and f.measure in judged and not f.passed:
                anchor_lines.append(
                    f"`{f.measure}` in `{run.view}`: Cube shows {_num(f.measure, f.left)}, "
                    f"the source shows {_num(f.measure, f.right)}."
                )

    n = len(group_lines) + len(anchor_lines)
    ids = sorted(
        {d.id for run in runs for d, _ in run.applied.quiet if d.call == "domain_owner"}
    )
    out = [
        "## What and why",
        "",
        f"The {domain} team owns the rule behind {n} items in the Cube validation.",
        "Cube and the dashboard disagree on them, or Cube disagrees with a source outside the dashboards.",
        "Counts under 10 show as `<10`, and student identifiers are hidden.",
        "",
    ]
    out += _bullets(group_lines + anchor_lines, "Nothing needs review.")
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
        f"Groups: {len(group_lines)}. Anchor findings: {len(anchor_lines)}.",
        "",
        "</details>",
        "",
    ]
    return "\n".join(out)
