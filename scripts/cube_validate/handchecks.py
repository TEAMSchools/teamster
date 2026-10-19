"""Hand checks: a short list a person reproduces in Tableau, Cube and the SIS."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from .cells import NEVER_CUBE, ORDER, PASS, Cell, answer_key, shown
from .config import lit


@dataclass
class HandCheck:
    id: str
    kind: str
    title: str
    steps: list[str]
    answer: str = ""  # answer_key of a cell check's Cube query
    covers: str = ""  # the verdict, or "base / cause", this check stands for


RESULTS = ("agree", "disagree", "pending")


def _id(prefix: str, title: str) -> str:
    """An id from the check's content, so a result never moves to another check."""
    digest = hashlib.sha1(title.encode(), usedforsecurity=False).hexdigest()
    return f"{prefix}-{digest[:8]}"


def row_samples(ws, checks) -> list[dict]:
    """1 row per non-match (base, cause), the first by student and day."""
    s, d = f'"k_{checks.student_key}"', f'"k_{checks.date_key}"'
    pairs = ws.query(
        "select distinct base, cause from rows where base <> 'match' order by 1, 2"
    )
    out = []
    for base, cause in pairs:
        cond = "cause is null" if cause is None else f"cause = {lit(cause)}"
        r = ws.dicts(
            # trunk-ignore(bandit/B608): base and cause are values from the rows table this tool built, quoted by lit
            f"select * from rows where base = {lit(base)} and {cond} order by {s}, {d} limit 1"
        )
        out.extend(r)
    return out


def _cell_check(c: Cell, answers: dict) -> HandCheck:
    where = ", ".join(f"{k} = {v}" for k, v in c.dims.items()) or "the only mark"
    title = f"{c.verdict}: {c.sheet} / {c.measure} ({where}, cut {c.cut})"
    key = answer_key(c.cut, c.sheet)
    at = (answers.get(key) or {}).get("last_refresh") or "an unrecorded time"
    return HandCheck(
        _id("C", title),
        "cell",
        title,
        [
            f"In the review copy, open sheet `{c.sheet}` and set cut `{c.cut}` (see manifest.json).",
            f"Find the mark {where}. Tableau should show `{shown(c.tableau, c.fmt)}` for {c.measure}.",
            f"Run the Cube query for `{key}` (below). The captured value was `{shown(None if c.cube is None else c.cube * c.scale, c.fmt)}`.",
            f"Cube's answer was captured at {at}; compare against that, not today's Cube.",
            f"The tool says **{c.verdict}**{f' ({c.reason})' if c.reason else ''}. Agree?",
        ],
        key,
        c.verdict,
    )


def _row_check(r: dict) -> HandCheck:
    keys = {k: v for k, v in r.items() if k.startswith("k_")}
    title = f"{r['base']} / {r['cause']}: {keys}"
    return HandCheck(
        _id("R", title),
        "row",
        title,
        [
            f"Row key {keys}. Dashboard side present: {r.get('in_t')}; Cube side present: {r.get('in_c')}.",
            "Look the day up in PowerSchool (Newark, Camden, Paterson) or Focus (Miami).",
            f"The tool files it as **{r['base']}**, cause **{r['cause']}**. Does the source agree?",
        ],
        covers=f"{r['base']} / {r['cause']}",
    )


def pick(
    cells: list[Cell],
    row_samples: list[dict],
    seed: str,
    answers: dict | None = None,
    limit: int = 15,
    passes: int = 3,
) -> list[HandCheck]:
    """Every verdict and bucket the run produced, then random passes, capped.

    Args:
        cells: Every judged cell.
        row_samples: 1 row per non-match bucket (row_samples).
        seed: Seeds the random passes, so a snapshot always picks the same ones.
        answers: Cube answers by answer_key, for each answer's capture time.
        limit: The most checks to pick.
        passes: How many random passes to add.

    Returns:
        The checks, cells first. Ids come from each check's content.
    """
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
    out = [_cell_check(c, answers or {}) for c in picked_cells]
    out += [_row_check(r) for r in picked_rows]
    return list({h.id: h for h in out}.values())


def uncovered(
    cells: list[Cell], row_samples: list[dict], picked: list[HandCheck]
) -> list[str]:
    """Each verdict and (base, cause) bucket the cap left without a hand check."""
    have = {h.covers for h in picked}
    verdicts = {c.verdict for c in cells}
    out = [v for v in ORDER if v in verdicts and v not in have]
    out += [
        f"{r['base']} / {r['cause']}"
        for r in row_samples
        if f"{r['base']} / {r['cause']}" not in have
    ]
    return out


def read_results(path: Path) -> dict[str, str]:
    """The analyst's result per check id.

    Raises:
        ValueError: A result is not exactly agree, disagree or pending; names
            each such id and value.
    """
    if not Path(path).exists():
        return {}
    got = {
        e["id"]: e.get("result") for e in yaml.safe_load(Path(path).read_text()) or []
    }
    bad = [f"{k}: {v}" for k, v in got.items() if v not in RESULTS]
    if bad:
        raise ValueError(
            f"hand_checks.yml results must be exactly {', '.join(RESULTS)}; "
            f"fix {'; '.join(bad)}"
        )
    return got


def write(
    dir: Path,
    checks_list: list[HandCheck],
    review_copy: str,
    answers: dict,
    uncovered: list[str],
) -> tuple[Path, Path]:
    """Write hand_checks.md (steps) and hand_checks.yml (results to fill in).

    Args:
        dir: The analysis folder.
        checks_list: The picked hand checks.
        review_copy: The review copy's name.
        answers: Cube answers by answer_key.
        uncovered: Verdicts and buckets the cap left without a hand check; the
            file ends by naming them so the cap never hides a gap.
    """
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
    lines.append(
        "Not covered by a hand check: " + "; ".join(uncovered)
        if uncovered
        else "Every verdict and bucket has a hand check."
    )
    md.write_text("\n".join(lines) + "\n")
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
