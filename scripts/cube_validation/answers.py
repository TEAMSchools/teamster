"""The owner's questions out, and the decisions that answer them back in.

Out: pick the example cell an owner checks by hand and pin each side's SQL to
it. The owner pastes these queries into the BigQuery console under their own
access, and the texts go into a GitHub issue, so the example is never one
person's row: every dimension is a reviewed column and at least `MASK_BELOW`
students stand behind it.

In: turn an approved triage batch, or the owner's answers comment, into
decisions. Their reasons are committed to git, so a note naming a person by
email or number is refused. This module runs no queries and writes no files;
it selects and formats saved data.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from .config import _TASK, CALLS, Decision, ViewConfig
from .cube_client import _literal
from .report import (
    _SEPARATED_DIGITS,
    MASK_BELOW,
    RunResult,
    _is_identifier,
    _questions,
    _safe_reason,
    defined_comparisons,
    definition_text,
    question_reason,
)

# BigQuery keeps table history this long, so an as-of query stops working then.
TIME_TRAVEL_DAYS = 7

NO_EXAMPLE = (
    "no group cell with 10+ students differs; find an example under your own access"
)


@dataclass(frozen=True)
class HandCheck:
    comparison: str
    cut: str
    dims: tuple[tuple[str, str], ...]
    dashboard: float | None
    cube: float | None
    dashboard_sql: str
    cube_sql: str
    dashboard_usd: float
    cube_usd: float
    expires: datetime
    expired: bool


def example_cell(run: RunResult, comparison: str) -> dict | None:
    """Pick the differing cell an owner can check without seeing a person.

    Args:
        run: The saved run.
        comparison: The comparison id.

    Returns:
        The cell with the largest absolute difference whose dims are all
        reviewed columns and whose `n_students` is at least `MASK_BELOW`; ties
        go to the lowest `key`. None when no cell qualifies.
    """
    ok = [
        c
        for c in run.diff_cells
        if c["comparison"] == comparison
        and not any(_is_identifier(column) for column, _ in c["dims"])
        and c["n_students"] is not None
        and c["n_students"] >= MASK_BELOW
        and c["dashboard"] is not None
        and c["cube"] is not None
    ]
    if not ok:
        return None
    return min(ok, key=lambda c: (-abs(c["dashboard"] - c["cube"]), c["key"]))


def _predicate(column: str, key: str) -> str:
    """Match a column against the text `pipeline._key` made of its value.

    `_key` writes NULL as '', numbers as plain decimals and booleans as
    True/False, so a bare `column = '7'` fails on a number and `= ''` misses a
    NULL. A date or text key compares as a string literal, which BigQuery
    coerces against a DATE or TIMESTAMP column.
    """
    if key == "":
        return f"{column} IS NULL"
    if key.lower() in ("true", "false"):
        return f"LOWER(CAST({column} AS STRING)) = {_literal(key.lower())}"
    try:
        number = Decimal(key)
    except InvalidOperation:
        number = None
    if number is not None and number.is_finite():
        return f"SAFE_CAST({column} AS NUMERIC) = {format(number.normalize(), 'f')}"
    return f"{column} = {_literal(key)}"


def _pinned(sql: str, pairs: list[tuple[str, str]]) -> str:
    """Wrap `sql` to the cell; unchanged for a total cell with no dims."""
    if not pairs:
        return sql
    where = " AND ".join(_predicate(name, value) for name, value in pairs)
    # trunk-ignore(bandit/B608): names come from validated config and values are literal-escaped
    return f"SELECT * FROM (\n{sql}\n) WHERE {where}"


def hand_check(
    run: RunResult, cfg: ViewConfig, comparison: str, now: datetime
) -> HandCheck | None:
    """Wrap each side's saved as-of SQL to return just the example cell.

    The Cube side outputs Cube member names; the dashboard side outputs the
    dashboard column names, which `cfg` maps from the member names.

    Args:
        run: The saved run.
        cfg: The view's config, for the dashboard column names.
        comparison: The comparison id.
        now: The current time, to decide whether the as-of SQL still runs.

    Returns:
        None when there is no example cell, no saved SQL or `cell_sql_usd`
        entry for its cut, or a dim the comparison does not map.
    """
    cell = example_cell(run, comparison)
    cmp = next((c for c in cfg.comparisons if c.id == comparison), None)
    sql = run.cell_sql.get(comparison, {}).get(cell["cut"]) if cell else None
    usd = run.cell_sql_usd.get(comparison, {}).get(cell["cut"]) if cell else None
    if not (cell and cmp and sql and usd):
        return None
    names = {d.cube: d.dashboard for d in cmp.dims}
    if any(member not in names for member, _ in cell["dims"]):
        return None
    cube_pairs = [(member, value) for member, value in cell["dims"]]
    dash_pairs = [(names[member], value) for member, value in cell["dims"]]
    expires = run.moment.start + timedelta(days=TIME_TRAVEL_DAYS)
    return HandCheck(
        comparison=comparison,
        cut=cell["cut"],
        dims=tuple(cube_pairs),
        dashboard=cell["dashboard"],
        cube=cell["cube"],
        dashboard_sql=_pinned(sql[0], dash_pairs),
        cube_sql=_pinned(sql[1], cube_pairs),
        dashboard_usd=usd[0],
        cube_usd=usd[1],
        expires=expires,
        expired=now >= expires,
    )


def _covers(d: Decision, stub: dict) -> bool:
    """True when a triage item's stub is the item `d` covers, by its key fields."""
    if d.missing_cut or d.missing_filter:
        return (d.missing_cut, d.missing_filter) == (
            stub.get("missing_cut", ""),
            stub.get("missing_filter", ""),
        )
    if stub.get("comparison") != d.comparison:
        return False
    if d.cells:
        return stub.get("cells") is True
    group = stub.get("group") or {}
    return group.get("column") == (d.group.get("column") or "") and bool(
        {str(v) for v in group.get("values", [])}
        & {str(v) for v in d.group.get("values", [])}
    )


def _shown_number(x: float | None) -> str | None:
    """Mask a whole number under `MASK_BELOW`, whatever the measure is called.

    A measure's name does not say whether it counts people, so any whole value
    under 10 reads `<10`; a rate or other fraction prints as it is.
    """
    if x is None:
        return None
    if float(x).is_integer() and x < MASK_BELOW:
        return "<10"
    return f"{x:g}"


def _check_json(view: str, check: HandCheck) -> dict:
    """A hand check as JSON, its two numbers masked like the issue's counts."""
    return {
        "view": view,
        **asdict(check),
        "dims": [list(pair) for pair in check.dims],
        "dashboard": _shown_number(check.dashboard),
        "cube": _shown_number(check.cube),
        "expires": check.expires.isoformat(),
    }


def questions_json(
    runs: list[RunResult],
    configs: list[ViewConfig],
    definitions: dict,
    triage: dict[str, dict],
    now: datetime,
) -> list[dict]:
    """List the review issue's questions for the owner's Claude session.

    Every string is text the issue's markdown shows, masked the same way:
    counts, the reason and definitions come from `report`, and triage evidence
    is scrubbed like the reason. A triage item's `stub` holds real values, so
    it is read here only to match items to decisions and never copied.

    Args:
        runs: The runs the issue renders.
        configs: Their views' configs, for each hand check's column names.
        definitions: Per view, per comparison id, `dashboard` and `cube` text.
        triage: Per view, its `triage.json`; a view without one has no
            evidence.
        now: The current time, to say whether the pinned SQL still runs.

    Returns:
        One dict per question in the issue's order: `id` (`Q1`, ...),
        `reason`, `decisions` (ids), `views`, `definitions` (`dashboard` and
        `cube`, one `<comparison> in <view>: <text>` line each), `evidence`,
        `counts` (the masked parts of its bullet), `hand_checks` (one per
        comparison, or `none` saying to find an example locally), and the
        earliest `moment` among its views with when its pinned SQL `expires`
        and whether it has `expired`.
    """
    by_run = {r.view: r for r in runs}
    by_cfg = {c.view: c for c in configs}
    out = []
    for n, q in enumerate(_questions(runs), start=1):
        views = list(dict.fromkeys(view for view, _ in q["decisions"]))

        defs: dict[str, list[str]] = {"dashboard": [], "cube": []}
        for view in views:
            shown = defined_comparisons([q], view)
            for cid, sides in sorted(definitions.get(view, {}).items()):
                if cid in shown:
                    for side in defs:
                        defs[side].append(
                            f"`{cid}` in `{view}`: {definition_text(sides[side])}"
                        )

        items = [
            item
            for view, d in q["decisions"]
            for item in triage.get(view, {}).get("items", [])
            if _covers(d, item.get("stub") or {})
        ]
        evidence = list(
            dict.fromkeys(
                _safe_reason(line, q["hidden"])
                for item in items
                for line in item.get("evidence", [])
            )
        )

        checks = []
        for view, cid, _ in q["comparisons"]:
            cfg = by_cfg.get(view)
            check = hand_check(by_run[view], cfg, cid, now) if cfg else None
            if check:
                checks.append(_check_json(view, check))
            else:
                checks.append({"view": view, "comparison": cid, "none": NO_EXAMPLE})

        moment = min((by_run[v].moment for v in views), key=lambda m: m.start)
        expires = moment.start + timedelta(days=TIME_TRAVEL_DAYS)
        out.append(
            {
                "id": f"Q{n}",
                "reason": question_reason(q),
                "decisions": [d.id for _, d in q["decisions"]],
                "views": views,
                "definitions": defs,
                "evidence": evidence,
                "counts": list(q["parts"]),
                "hand_checks": checks,
                "moment": {
                    "start": moment.start.isoformat(),
                    "end": moment.end.isoformat(),
                    "job_id": moment.job_id,
                },
                "expires": expires.isoformat(),
                "expired": now >= expires,
            }
        )
    return out


# --- decisions in ------------------------------------------------------------


class AnswerError(Exception):
    """An approved batch or an answers comment cannot be written as decisions.

    Raised before anything is written, so nothing from that batch or comment
    lands in any file.
    """


@dataclass(frozen=True)
class Answer:
    """One answer in the owner's comment, to the question with id `question`.

    `call` is one of `config.CALLS`; `domain_owner` is a free-text answer.
    `task` is the issue the owner's session opened for `fix_source`.
    """

    question: str
    decisions: tuple[str, ...]
    call: str
    note: str
    task: str = ""


_JSON_BLOCK = re.compile(r"^```json[ \t]*\n(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# What a note cannot carry into a committed reason. A date is removed first, so
# an owner may cite one. A person's name cannot be told from other words by
# code; both skills check for names before anything is posted or written.
NOTE_REFUSALS = (
    ("an email address", re.compile(r"\S+@\S+\.\w+")),
    ("a run of 5 or more digits", re.compile(r"\d{5,}")),
    ("a run of 5 or more digits", _SEPARATED_DIGITS),
)


def note_refusal(note: str) -> str | None:
    """Name what `note` carries that `NOTE_REFUSALS` keeps out, else None."""
    text = _ISO_DATE.sub("", note)
    return next((what for what, pattern in NOTE_REFUSALS if pattern.search(text)), None)


def _text(entry: dict, key: str, where: str, *, required: bool = True) -> str:
    value = entry.get(key, "")
    if not isinstance(value, str) or (required and not value.strip()):
        raise AnswerError(f"{where}: `{key}` must be non-empty text")
    return value.strip()


def parse_answers(body: str) -> list[Answer]:
    """Read the answers from the one fenced `json` block of an answers comment.

    The block is a list of `{"question": "Q<n>", "decisions": [<id>, ...],
    "call": <call>, "note": <text>, "task": <link>}`; `task` is needed only for
    `fix_source` and refused on any other call.

    Raises:
        AnswerError: The comment has no or several `json` blocks, the block is
            not a non-empty list of answers, a call is not in `config.CALLS`,
            or a task is missing, misplaced, or not an https:// link or
            #<issue>.
    """
    blocks = _JSON_BLOCK.findall(body)
    if len(blocks) != 1:
        raise AnswerError(
            f"the comment needs exactly 1 fenced json block; it has {len(blocks)}"
        )
    try:
        data = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise AnswerError(f"the json block is not JSON ({exc})") from exc
    if not isinstance(data, list) or not data:
        raise AnswerError("the json block must be a list of at least 1 answer")

    out = []
    for i, entry in enumerate(data):
        where = f"answer {i + 1}"
        if not isinstance(entry, dict):
            raise AnswerError(f"{where}: must be an object")
        question = where = _text(entry, "question", where)
        decisions = entry.get("decisions")
        if (
            not isinstance(decisions, list)
            or not decisions
            or not all(isinstance(d, str) and d for d in decisions)
        ):
            raise AnswerError(f"{where}: `decisions` must list at least 1 decision id")
        call = _text(entry, "call", where)
        if call not in CALLS:
            raise AnswerError(
                f"{where}: call must be one of {', '.join(CALLS)}; got {call!r}"
            )
        task = _text(entry, "task", where, required=False)
        if call == "fix_source" and not task:
            raise AnswerError(f"{where}: fix_source needs a task")
        if task and call != "fix_source":
            raise AnswerError(f"{where}: only fix_source takes a task; got {call}")
        if task and not _TASK.fullmatch(task):
            raise AnswerError(
                f"{where}: task must be an https:// link or #<issue>; got {task!r}"
            )
        out.append(
            Answer(
                question=question,
                decisions=tuple(decisions),
                call=call,
                note=_text(entry, "note", where, required=False),
                task=task,
            )
        )
    return out


@dataclass(frozen=True)
class Change:
    """What one answer does to one decision in the file at `path`."""

    path: str
    decision: str
    question: str
    call: tuple[str, str]
    task: tuple[str, str]
    reason: tuple[str, str]


def answer_changes(
    answers: list[Answer], configs: list[tuple[str, ViewConfig]]
) -> list[Change]:
    """Match each answer to its decisions and say what it changes.

    The new reason is `<old reason> Owner: <note>`. The new task is the file's
    `tasks.cube_fix` for `fix_cube`, `tasks.dashboard_fix` for
    `fix_dashboard`, the answer's own task for `fix_source`, and unchanged for
    the others. A free-text (`domain_owner`) answer keeps its call.

    Args:
        answers: The parsed comment.
        configs: Each validation file's path and config.

    Raises:
        AnswerError: Any answer does not fit, which refuses the whole comment:
            a decision id is in none of the files or in several, is not a
            `domain_owner` decision, or is answered twice; a note carries what
            `NOTE_REFUSALS` keeps out; a free-text answer has no note; or a fix
            call's file has no `tasks:` entry for it.
    """
    out = []
    seen: set[str] = set()
    for a in answers:
        if what := note_refusal(a.note):
            raise AnswerError(
                f"{a.question}: the note has {what}; ask the owner to reword it"
            )
        if a.call == "domain_owner" and not a.note:
            raise AnswerError(f"{a.question}: a free-text answer needs its note")
        for decision_id in a.decisions:
            if decision_id in seen:
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is answered twice"
                )
            seen.add(decision_id)
            found = [
                (path, cfg, d)
                for path, cfg in configs
                for d in cfg.decisions
                if d.id == decision_id
            ]
            if not found:
                raise AnswerError(
                    f"{a.question}: no decision {decision_id!r} in the files given"
                )
            if len(found) > 1:
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is in "
                    f"{', '.join(path for path, _, _ in found)}; which is meant "
                    "is unclear"
                )
            ((path, cfg, d),) = found
            if d.call != "domain_owner":
                raise AnswerError(
                    f"{a.question}: decision {decision_id!r} is {d.call}, not "
                    "domain_owner; it no longer matches the question"
                )
            task = d.task
            key = {"fix_cube": "cube_fix", "fix_dashboard": "dashboard_fix"}.get(a.call)
            if key:
                if key not in cfg.tasks:
                    raise AnswerError(
                        f"{a.question}: {path} has no `tasks.{key}` for {a.call}; "
                        "add it first"
                    )
                task = cfg.tasks[key]
            elif a.call == "fix_source":
                task = a.task
            reason = f"{d.reason.rstrip()} Owner: {a.note}" if a.note else d.reason
            out.append(
                Change(
                    path=path,
                    decision=decision_id,
                    question=a.question,
                    call=(d.call, a.call),
                    task=(d.task, task),
                    reason=(d.reason, reason),
                )
            )
    return out


_STUB_KEYS = ("comparison", "group", "cells", "missing_cut", "missing_filter")


def approved_decisions(
    approved: list, triage: dict, fingerprints: dict[str, dict[str, str]]
) -> list[dict]:
    """Turn an approved triage batch into decisions, in the file's key order.

    Each decision takes its key fields from the triage item's `stub`, which
    holds the group's real values, and the comparison's `{cube, dashboard}`
    from the run's fingerprints. A missing cut or filter covers the view, so
    it takes neither a comparison nor fingerprints.

    Args:
        approved: `[{"id", "call", "reason", "task", "item"}]`; `item` is a
            triage item id and `task` may be empty.
        triage: The view's `triage.json`.
        fingerprints: The latest run's fingerprints per comparison id.

    Raises:
        AnswerError: An entry is malformed, repeats an id, names an item the
            triage does not list, or names a comparison the run has no
            fingerprints for.
    """
    stubs = {item.get("id"): item.get("stub") or {} for item in triage.get("items", [])}
    out = []
    ids: set[str] = set()
    for i, entry in enumerate(approved):
        if not isinstance(entry, dict):
            raise AnswerError(f"approved entry {i + 1}: must be an object")
        where = f"approved entry {i + 1}"
        decision_id = _text(entry, "id", where)
        if decision_id in ids:
            raise AnswerError(f"{where}: id {decision_id!r} repeats")
        ids.add(decision_id)
        item = _text(entry, "item", where)
        if item not in stubs:
            raise AnswerError(f"{where}: triage lists no item {item!r}")
        stub = stubs[item]
        decision: dict = {"id": decision_id}
        decision.update({k: stub[k] for k in _STUB_KEYS if k in stub})
        decision["call"] = _text(entry, "call", where)
        decision["reason"] = _text(entry, "reason", where)
        if task := _text(entry, "task", where, required=False):
            decision["task"] = task
        if comparison := stub.get("comparison"):
            fp = fingerprints.get(comparison) or {}
            if not (fp.get("cube") and fp.get("dashboard")):
                raise AnswerError(
                    f"{where}: the run has no fingerprints for {comparison!r}"
                )
            decision["fingerprints"] = {
                "cube": fp["cube"],
                "dashboard": fp["dashboard"],
            }
        out.append(decision)
    return out
