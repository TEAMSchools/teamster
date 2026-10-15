"""Cells layer: compare each exported Tableau number with Cube's, explain by rows."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from .config import Checks, Cut, FieldMap, lit, side_sql

# trunk-ignore(bandit/B105): a verdict label, not a credential
PASS = "pass"
COINCIDENTAL = "coincidental match"
ROW_GAP = "row gap"
FORMULA_GAP = "formula gap"
FILTER_IGNORED = "filter ignored"
UNPROVEN = "mapping unproven"
NO_COUNTERPART = "no Cube counterpart"
NO_ROWS = "no captured rows"
NEVER_CUBE = (FILTER_IGNORED, UNPROVEN, NO_COUNTERPART, NO_ROWS)
ORDER = (ROW_GAP, FORMULA_GAP, COINCIDENTAL, PASS, *NEVER_CUBE)

CUBE_SIDE = ("match", "value_differs", "cube_only")
DASHBOARD_SIDE = ("match", "value_differs", "dashboard_only", "outside_scope")
ALL = "(All)"
NULLS = ("", "Null", "(Blank)", "%null%")
TOTALS = ("Total", "Grand Total")
_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_ISO_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})T00:00:00(\.0+)?Z?$")
_GROUPED_INT = re.compile(r"^-?\d{1,3}(,\d{3})+$")


class MappingGap(KeyError):
    """A filter caption, sheet header or parameter value has no mapping."""


def norm_value(v) -> str | None:
    """A value as both sides store it: ISO dates, plain integers, None for blank."""
    if v is None:
        return None
    s = str(v).strip()
    if s in NULLS:
        return None
    if m := _US_DATE.match(s):
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if m := _ISO_TS.match(s):
        return m.group(1)
    if _GROUPED_INT.match(s):
        return s.replace(",", "")
    return s


@dataclass(frozen=True)
class Display:
    value: float
    decimals: int
    percent: bool


def parse_display(s: str | None) -> Display | None:
    """A number as Tableau exported it, with its decimals and percent sign."""
    if s is None:
        return None
    t = s.strip().replace(",", "")
    if t in NULLS:
        return None
    percent = t.endswith("%")
    t = t.rstrip("%").strip()
    try:
        value = float(t)
    except ValueError:
        return None
    return Display(value, len(t.split(".", 1)[1]) if "." in t else 0, percent)


def display_equal(tableau: str | None, cube: float | None, scale: float = 1.0) -> bool:
    """Cube's value rounded the way Tableau displayed its own (half up)."""
    d = parse_display(tableau)
    if d is None or cube is None:
        return d is None and cube is None
    v = Decimal(repr(cube * scale * (100 if d.percent else 1)))
    shown = float(v.quantize(Decimal(1).scaleb(-d.decimals), rounding=ROUND_HALF_UP))
    return math.isclose(shown, d.value, rel_tol=1e-9, abs_tol=1e-9)


def parse_export(data: bytes) -> list[dict[str, str]]:
    """Rows of a sheet's CSV export, wide, without total rows."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    if rows and "Measure Names" in rows[0] and "Measure Values" in rows[0]:
        dims = [c for c in rows[0] if c not in ("Measure Names", "Measure Values")]
        wide: dict[tuple, dict] = {}
        for r in rows:
            k = tuple(r[d] for d in dims)
            wide.setdefault(k, {d: r[d] for d in dims})[r["Measure Names"]] = r[
                "Measure Values"
            ]
        rows = list(wide.values())
    return [r for r in rows if not any((v or "").strip() in TOTALS for v in r.values())]


def answer_key(cut_id: str, sheet: str) -> str:
    return f"{cut_id}|{sheet}"


def _stored(fm: FieldMap, label: str | None, side: str) -> str | None:
    n = norm_value(label)
    if label is None or n is None:
        return None
    if side == "c" and label in fm.cube_values:
        return fm.cube_values[label]
    return fm.values.get(label, n)


def _pred(fm: FieldMap, label: str | None, side: str) -> str | None:
    """SQL over table `rows` for field = label on one side; None for (All)."""
    if label == ALL:
        return None
    expr = fm.tableau if side == "t" else fm.cube_column
    if not expr:
        raise MappingGap(
            f"{fm.caption}: no {'extract' if side == 't' else 'Cube'} column"
        )
    col = side_sql(expr, f"{side}_")
    v = _stored(fm, label, side)
    return f"({col} is null)" if v is None else f"({col} = {lit(v)})"


def cube_query(
    checks: Checks, sheet: str, cut: Cut, click_filters: dict[str, str]
) -> dict:
    """The aggregate Cube query for one sheet under one cut.

    Raises:
        MappingGap: A filter, click field or parameter value is not mapped.
    """
    sm = checks.sheets[sheet]
    v = sm.view
    measures = sorted(
        {f"{v}.{m.cube}" for m in sm.measures.values() if m.cube}
        | {f"{v}.count_students"}
    )
    dimensions = [f"{v}.{d.cube}" for d in sm.dims.values() if d.cube]
    filters: list[dict] = []
    for caption, label in {**cut.filters, **click_filters}.items():
        if label == ALL:
            continue
        fm = checks.filters.get(caption)
        if fm is None or not fm.cube:
            raise MappingGap(caption)
        stored = _stored(fm, label, "c")
        member = f"{v}.{fm.cube}"
        filters.append(
            {"member": member, "operator": "notSet"}
            if stored is None
            else {"member": member, "operator": "equals", "values": [stored]}
        )
    for caption, value in cut.params.items():
        pv = checks.params.get(caption, {}).get(value)
        if pv is None:
            raise MappingGap(f"{caption} = {value}")
        filters.extend(pv.cube_filters)
    return {
        "measures": measures,
        "dimensions": dimensions,
        "filters": filters,
        "limit": 50000,
    }


def verdict(equal: bool, buckets: list) -> str:
    """The spec's verdict table for a cell whose cut is judgeable."""
    if not buckets:
        return NO_ROWS
    all_match = all(b[0] == "match" for b in buckets)
    if equal:
        return PASS if all_match else COINCIDENTAL
    return FORMULA_GAP if all_match else ROW_GAP


@dataclass
class Cell:
    cut: str
    sheet: str
    dims: dict[str, str]
    measure: str
    tableau: str | None
    cube: float | None
    verdict: str
    reason: str = ""
    buckets: list[tuple] = field(default_factory=list)
    students: tuple[int, int] = (0, 0)


def _cut_preds(checks: Checks, cut: Cut, click: dict[str, str], side: str) -> list[str]:
    out = []
    for caption, label in {**cut.filters, **click}.items():
        fm = checks.filters.get(caption)
        if fm is None:
            raise MappingGap(caption)
        p = _pred(fm, label, side)
        if p:
            out.append(p)
    for caption, value in cut.params.items():
        pv = checks.params.get(caption, {}).get(value)
        if pv is None:
            raise MappingGap(f"{caption} = {value}")
        expr = pv.tableau if side == "t" else pv.cube_column
        if expr:
            out.append(f"({side_sql(expr, f'{side}_')})")
    return out


def _where(preds_t: list[str], preds_c: list[str]) -> str:
    t = " and ".join(["in_t", *preds_t])
    c = " and ".join(["in_c", *preds_c])
    return f"(({t}) or ({c}))"


def _cube_labels(sm, key: tuple) -> dict[str, str | None]:
    """Tableau labels for a Cube mark's dimension values (inverse of the maps)."""
    labels: dict[str, str | None] = {}
    for (h, d), v in zip(
        [(h, d) for h, d in sm.dims.items() if d.cube], key, strict=True
    ):
        if v is None:
            labels[h] = None
            continue
        hit = next((k for k, s in d.cube_values.items() if norm_value(s) == v), None)
        if hit is None:
            hit = next((k for k, s in d.values.items() if norm_value(s) == v), None)
        labels[h] = hit if hit is not None else v
    return labels


def judge(
    ws,
    checks: Checks,
    manifest: dict,
    answers: dict,
    export: Callable[[str, str], bytes | None],
) -> list[Cell]:
    """Every exported number's verdict.

    Args:
        ws: A hyper.Workspace holding table `rows` (Task 5).
        checks: The checks file.
        manifest: The snapshot manifest (click filters per cut).
        answers: Cube answers by answer_key.
        export: Reads a cut's sheet export, or None when it was not exported.

    Returns:
        One Cell per exported number, plus one per Cube mark Tableau did not show.
    """
    student = f'"k_{checks.student_key}"'
    default = checks.cuts[0]
    out: list[Cell] = []
    for cut in checks.cuts:
        meta = (manifest.get("cuts") or {}).get(cut.id, {})
        click = meta.get("click_filters") or {}
        targets = set(meta.get("click_targets") or [])
        exports = {s: export(cut.id, s) for s in checks.sheets}
        try:
            base_t = {
                s: _cut_preds(checks, cut, click if s in targets else {}, "t")
                for s in checks.sheets
            }
            base_c = {
                s: _cut_preds(checks, cut, click if s in targets else {}, "c")
                for s in checks.sheets
            }
            gap = ""
        except MappingGap as e:
            base_t = base_c = {}
            gap = f"not mapped: {e.args[0]}"
        ignored = set()
        if cut.id != default.id and not gap:
            for s, data in exports.items():
                if data is not None and data == export(default.id, s):
                    n_cut = ws.count("rows where " + " and ".join(["in_t", *base_t[s]]))
                    n_def = ws.count("rows where in_t")
                    if n_cut != n_def:
                        ignored.add(s)
        proof = (
            dict.fromkeys(checks.sheets, gap)
            if gap
            else _proof(ws, checks, exports, base_t, student)
        )
        for sheet, data in exports.items():
            if data is None:
                continue
            sm = checks.sheets[sheet]
            ans = answers.get(answer_key(cut.id, sheet)) or {}
            cdims = [h for h, d in sm.dims.items() if d.cube]
            cube_rows = {
                tuple(
                    norm_value(r.get(f"{sm.view}.{sm.dims[h].cube}")) for h in cdims
                ): r
                for r in ans.get("data") or []
            }
            seen = set()
            for row in parse_export(data):
                dims = {h: v for h, v in row.items() if h in sm.dims}
                undeclared = _undeclared(sm, row)
                key = tuple(
                    norm_value(_stored(sm.dims[h], dims.get(h), "c")) for h in cdims
                )
                seen.add(key)
                crow = cube_rows.get(key)
                if undeclared:
                    status, reason, buckets, studs = (
                        NO_COUNTERPART,
                        f"column not mapped: {', '.join(undeclared)}",
                        [],
                        (0, 0),
                    )
                else:
                    status, reason, buckets, studs = _status(
                        ws, checks, sheet, dims, ignored, proof[sheet],
                        base_t, base_c, ans, student,
                    )  # fmt: skip
                for h, v in row.items():
                    if h not in sm.measures:
                        continue
                    m = sm.measures[h]
                    cube_v = (
                        float(crow[f"{sm.view}.{m.cube}"])
                        if (
                            m.cube
                            and crow
                            and crow.get(f"{sm.view}.{m.cube}") is not None
                        )
                        else None
                    )
                    if undeclared:
                        vd, rs = status, reason
                    elif not m.cube:
                        vd, rs = NO_COUNTERPART, "measure not mapped"
                    elif status:
                        vd, rs = status, reason
                    elif crow is None and any(b[0] in CUBE_SIDE for b in buckets):
                        vd, rs = UNPROVEN, "Cube answer has no mark for these labels"
                    else:
                        vd, rs = (
                            verdict(display_equal(v, cube_v, m.scale), buckets),
                            "",
                        )
                    out.append(
                        Cell(cut.id, sheet, dims, h, v, cube_v, vd, rs, buckets, studs)
                    )
            for key, crow in cube_rows.items():
                if key in seen:
                    continue
                labels = _cube_labels(sm, key)
                status, reason, buckets, studs = _status(
                    ws, checks, sheet, labels, ignored, proof[sheet],
                    base_t, base_c, ans, student,
                )  # fmt: skip
                if status:
                    vd, rs = status, reason
                elif any(b[0] in DASHBOARD_SIDE for b in buckets):
                    vd, rs = (
                        UNPROVEN,
                        "Tableau shows no mark for labels the extract has rows for",
                    )
                elif not buckets:
                    vd, rs = NO_ROWS, ""
                else:
                    vd, rs = ROW_GAP, "Cube shows a mark Tableau does not"
                for m in sm.measures.values():
                    raw = crow.get(f"{sm.view}.{m.cube}") if m.cube else None
                    if raw is None:
                        continue
                    out.append(
                        Cell(
                            cut.id, sheet, {k: v or "" for k, v in labels.items()},
                            m.column, None, float(raw), vd, rs, buckets, studs,
                        )
                    )  # fmt: skip
    return out


def _undeclared(sm, row: dict) -> list[str]:
    """Export headers the sheet map does not declare as dim, measure or count."""
    return [
        h for h in row if h not in sm.dims and h not in sm.measures and h != sm.students
    ]


def _proof(
    ws, checks: Checks, exports: dict, base_t: dict, student: str
) -> dict[str, str]:
    """Per sheet: '' when its filters are proven against the extract, else why not.

    A sheet with a student count is proven by its own rows. One without is proven
    only when a proven sheet in the same cut has the same filters.
    """
    own: dict[str, str] = {}
    for sheet, data in exports.items():
        sm = checks.sheets[sheet]
        if data is None or not sm.students:
            continue
        checked = 0
        reason = ""
        try:
            for row in parse_export(data):
                if _undeclared(sm, row):
                    continue
                want = parse_display(row.get(sm.students))
                if want is None:
                    continue
                preds = list(base_t[sheet])
                for h, label in row.items():
                    if h in sm.dims:
                        p = _pred(sm.dims[h], label, "t")
                        if p:
                            preds.append(p)
                got = int(
                    ws.query(
                        # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
                        f"select count(distinct {student}) from rows where "
                        + " and ".join(["in_t", *preds])
                    )[0][0]
                )
                checked += 1
                if got != int(want.value):
                    reason = f"{sheet}: extract has {got} students where Tableau shows {int(want.value)}"
                    break
        except MappingGap as e:
            reason = f"not mapped: {e.args[0]}"
        if checked or reason:
            own[sheet] = reason
    if not own:
        return dict.fromkeys(exports, "no sheet in this cut shows a student count")
    proven = [s for s, r in own.items() if not r]
    out = {}
    for sheet in exports:
        if sheet in own:
            out[sheet] = own[sheet]
        elif any(base_t[sheet] == base_t[p] for p in proven):
            out[sheet] = ""
        else:
            out[sheet] = "no student count proves this sheet's filters"
    return out


def _status(ws, checks, sheet, dims, ignored, proof, base_t, base_c, ans, student):
    """(verdict override, reason, buckets, (students dashboard, students Cube))."""
    if sheet in ignored:
        return FILTER_IGNORED, "export equals the default view's", [], (0, 0)
    if proof:
        return UNPROVEN, proof, [], (0, 0)
    if ans.get("error") or "data" not in ans:
        return (
            UNPROVEN,
            f"no Cube answer: {ans.get('error') or 'not captured'}",
            [],
            (0, 0),
        )
    sm = checks.sheets[sheet]
    for h, d in sm.dims.items():
        if not d.cube:
            return UNPROVEN, f"not mapped: {h}: no Cube member", [], (0, 0)
    pt, pc = list(base_t[sheet]), list(base_c[sheet])
    try:
        for h, label in dims.items():
            for side, acc in (("t", pt), ("c", pc)):
                p = _pred(sm.dims[h], label, side)
                if p:
                    acc.append(p)
    except MappingGap as e:
        return UNPROVEN, f"not mapped: {e.args[0]}", [], (0, 0)
    where = _where(pt, pc)
    buckets = [
        tuple(r)
        for r in ws.query(
            # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
            f"select base, cause, count(*), count(distinct {student}) from rows where {where} "
            "group by base, cause order by base, cause"
        )
    ]
    t_and = " and ".join(["in_t", *pt])
    c_and = " and ".join(["in_c", *pc])
    studs = ws.query(
        # trunk-ignore(bandit/B608): identifiers are quoted and values come from the checks file, never user input
        f"select count(distinct case when {t_and} then {student} end), "
        f"count(distinct case when {c_and} then {student} end) from rows where {where}"
    )[0]
    return "", "", buckets, (int(studs[0]), int(studs[1]))
