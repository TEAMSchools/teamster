"""Draft the Cube `ai_context` text that says why a measure differs from a dashboard.

A difference decided `deliberate` (by the analyst, or by the domain owner
through `record-answers`) is one an MCP user may still ask about: "why does
Cube's number not match the dashboard?". `describe` lists those decisions per
measure and drafts a sentence for the measure's `meta.ai_context`. It writes
nothing: where the sentence goes (the member, or the view) follows
`.claude/rules/cube-authoring.md`, and the YAML edit is a separate Cube PR.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Decision, ViewConfig, mask_digits

# Cube truncates `ai_context` past this for its hosted agent; the schema test
# in `tests/cube/test_cube_schema.py` enforces it.
AI_CONTEXT_CAP = 2000


@dataclass
class MeasureNote:
    """One measure's deliberate differences from its dashboards."""

    view: str
    measure: str
    dashboards: list[str] = field(default_factory=list)
    # (what differs, the decision's reason, the decision ids)
    lines: list[tuple[str, str, list[str]]] = field(default_factory=list)

    def draft(self) -> str:
        """The proposed `ai_context` sentence, for the analyst to reword."""
        where = " and ".join(self.dashboards) or "its Tableau dashboard"
        what = "; ".join(text for text, _, _ in self.lines)
        return f"Differs from {where} on purpose: {what}."


def _what(d: Decision) -> str:
    """What a decision says differs, in words with no row's values."""
    if d.cause:
        return f"{d.cause.get('label')} ({d.cause.get('side')} side)"
    if d.missing_cut or d.missing_filter:
        kind, caption = (
            ("cut", d.missing_cut) if d.missing_cut else ("filter", d.missing_filter)
        )
        return f"the dashboard's sheet {kind} `{caption}` has no Cube member"
    # A row-group or cell decision names no rule but its reason; its group's
    # values never reach the draft.
    return _reason(d)


def _reason(d: Decision) -> str:
    return " ".join(d.reason.split())


def notes(cfg: ViewConfig) -> list[MeasureNote]:
    """Each measure's deliberate decisions, in the file's order.

    A missing cut or filter covers the whole view, so it is listed under every
    measure of the view's comparisons.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    out: dict[str, MeasureNote] = {}

    def note_for(measure: str) -> MeasureNote:
        return out.setdefault(measure, MeasureNote(cfg.view, measure))

    for d in cfg.decisions:
        if d.call != "deliberate":
            continue
        comparisons = (
            [by_id[d.comparison]] if d.comparison in by_id else list(by_id.values())
        )
        for c in comparisons:
            n = note_for(c.measure)
            if c.workbook and c.workbook not in n.dashboards:
                n.dashboards.append(c.workbook)
            text = mask_digits(_what(d))
            existing = next((x for x in n.lines if x[0] == text), None)
            if existing:
                if d.id not in existing[2]:
                    existing[2].append(d.id)
                continue
            n.lines.append((text, mask_digits(_reason(d)), [d.id]))
    return list(out.values())


def render(configs: list[ViewConfig]) -> str:
    """The draft for each view's measures, or a line saying there is none."""
    blocks = []
    for cfg in configs:
        for n in notes(cfg):
            member = n.measure if "." in n.measure else f"{cfg.view}.{n.measure}"
            draft = n.draft()
            lines = [f"## `{member}`", "", "Deliberate differences:", ""]
            for text, reason, ids in n.lines:
                lines.append(f"- {text}. Decided in {', '.join(ids)}: {reason}")
            lines += ["", "Draft `meta.ai_context` sentence:", "", f"> {draft}", ""]
            if len(draft) > AI_CONTEXT_CAP:
                lines += [
                    f"The draft is {len(draft):,} characters; Cube truncates "
                    f"`ai_context` past {AI_CONTEXT_CAP:,}. Shorten it.",
                    "",
                ]
            blocks.append("\n".join(lines))
    if not blocks:
        return "No `deliberate` decisions: nothing to describe."
    head = (
        "Where it goes: the member's `meta.ai_context` (or the view's, for a note "
        "on reading the view's answers), added to any text already there; "
        "`.claude/rules/cube-authoring.md` has the rules, including view "
        "overrides. `description:` only when the sentence is a definition true "
        "of the raw column."
    )
    return "\n\n".join([head, *blocks])
