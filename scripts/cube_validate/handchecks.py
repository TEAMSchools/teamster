"""Hand checks: a short list a person reproduces in Tableau, Cube and the SIS."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cells import NEVER_CUBE, ORDER, PASS, Cell, answer_key


@dataclass
class HandCheck:
    id: str
    kind: str
    title: str
    steps: list[str]
    answer: str = ""  # answer_key of a cell check's Cube query


def row_samples(ws, checks) -> list[dict]:
    """1 row per non-match (base, cause), the first by student and day."""
    s, d = f'"k_{checks.student_key}"', f'"k_{checks.date_key}"'
    pairs = ws.query(
        "select distinct base, cause from rows where base <> 'match' order by 1, 2"
    )
    out = []
    for base, cause in pairs:
        cond = "cause is null" if cause is None else f"cause = '{cause}'"
        # trunk-ignore(bandit/B608): base and cause are values from the rows table this tool built, never user input
        r = ws.dicts(
            f"select * from rows where base = '{base}' and {cond} order by {s}, {d} limit 1"
        )
        out.extend(r)
    return out


def _cell_check(i: int, c: Cell) -> HandCheck:
    where = ", ".join(f"{k} = {v}" for k, v in c.dims.items()) or "the only mark"
    return HandCheck(
        f"C{i}",
        "cell",
        f"{c.verdict}: {c.sheet} / {c.measure} ({where}, cut {c.cut})",
        [
            f"In the review copy, open sheet `{c.sheet}` and set cut `{c.cut}` (see manifest.json).",
            f"Find the mark {where}. Tableau should show `{c.tableau}` for {c.measure}.",
            f"Run the Cube query for `{answer_key(c.cut, c.sheet)}` (below). The captured value was `{c.cube}`.",
            f"The tool says **{c.verdict}**{f' ({c.reason})' if c.reason else ''}. Agree?",
        ],
        answer_key(c.cut, c.sheet),
    )


def _row_check(i: int, r: dict) -> HandCheck:
    keys = {k: v for k, v in r.items() if k.startswith("k_")}
    return HandCheck(
        f"R{i}",
        "row",
        f"{r['base']} / {r['cause']}: {keys}",
        [
            f"Row key {keys}. Dashboard side present: {r.get('in_t')}; Cube side present: {r.get('in_c')}.",
            "Look the day up in PowerSchool (Newark, Camden, Paterson) or Focus (Miami).",
            f"The tool files it as **{r['base']}**, cause **{r['cause']}**. Does the source agree?",
        ],
    )


def pick(
    cells: list[Cell],
    row_samples: list[dict],
    seed: str,
    limit: int = 15,
    passes: int = 3,
) -> list[HandCheck]:
    """Every verdict and bucket the run produced, then random passes, capped."""
    # trunk-ignore(bandit/B311): seeded sampling for repeatable hand checks, not a security use
    rng = random.Random(seed)
    firsts: dict[str, Cell] = {}
    for c in sorted(
        cells, key=lambda c: (c.cut, c.sheet, c.measure, sorted(c.dims.items()))
    ):
        if c.verdict != PASS and c.verdict not in NEVER_CUBE:
            firsts.setdefault(c.verdict, c)
    for c in cells:
        if c.verdict in NEVER_CUBE:
            firsts.setdefault(c.verdict, c)
    head = [firsts[v] for v in ORDER if v in firsts]
    budget = max(limit - passes, 0)
    picked_cells = head[:budget]
    picked_rows = row_samples[: max(budget - len(picked_cells), 0)]
    pool = [c for c in cells if c.verdict == PASS]
    room = min(passes, limit - len(picked_cells) - len(picked_rows))
    picked_cells += rng.sample(pool, min(room, len(pool)))
    out = [_cell_check(i + 1, c) for i, c in enumerate(picked_cells)]
    out += [_row_check(i + 1, r) for i, r in enumerate(picked_rows)]
    return out


def read_results(path: Path) -> dict[str, str]:
    if not Path(path).exists():
        return {}
    return {
        e["id"]: e.get("result") or "pending"
        for e in yaml.safe_load(Path(path).read_text()) or []
    }


def write(
    dir: Path, checks_list: list[HandCheck], review_copy: str, answers: dict
) -> tuple[Path, Path]:
    """Write hand_checks.md (steps) and hand_checks.yml (results to fill in)."""
    dir = Path(dir)
    md, yml = dir / "hand_checks.md", dir / "hand_checks.yml"
    old = read_results(yml)
    lines = [
        "# Hand checks",
        "",
        f"Review copy: `{review_copy}`. Local only: this file names students.",
        "",
    ]
    for h in checks_list:
        lines += [
            f"## {h.id}: {h.title}",
            "",
            *[f"{n}. {s}" for n, s in enumerate(h.steps, 1)],
            "",
        ]
        if h.answer:
            q = (answers.get(h.answer) or {}).get("query")
            if q:
                lines += ["```json", json.dumps(q, indent=2), "```", ""]
    md.write_text("\n".join(lines))
    yml.write_text(
        yaml.safe_dump(
            [
                {"id": h.id, "result": old.get(h.id, "pending"), "note": ""}
                for h in checks_list
            ],
            sort_keys=False,
        )
    )
    return md, yml
