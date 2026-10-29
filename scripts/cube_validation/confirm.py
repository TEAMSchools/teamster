"""Prove row groups with stored classification queries: `triage confirm`.

The trace only leads. A person proves causes with ONE classification query per
comparison and bucket: a `CASE` in lineage order that names each unmatched
row's first failing model predicate, with an `UNEXPLAINED` else-bucket. It is
stored as SQL only, with no data, at
`<validation dir>/proofs/<view>/<comparison>__<bucket>.sql`, under a leading
comment block that maps each bucket to its side and plain words:

    -- cause C1 = dashboard: WPP assessments are left off the dashboard

The query reads the run's unmatched rows of its comparison and bucket through
the placeholder `{unmatched}`, which the tool fills from the run's reconcile:
`item_key`, the grain under its Cube names, and the group-by columns. It
returns only `item_key, cause, n`. Every `triage` re-runs every stored proof on
the current run's rows; an item whose rows a proof fully explains (no
`UNEXPLAINED` row, and the counts sum to its rows) goes to `cause`. A cell set
goes to `cause` when every differing cell's rows lie in groups in `cause`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import sqlglot
from google.api_core.exceptions import GoogleAPIError
from sqlglot import exp
from sqlglot.errors import SqlglotError

from . import compare, pipeline, triage
from .bq import CostCapError, ViewHistoryError, Warehouse
from .compare import Group
from .config import Comparison, ViewConfig
from .cube_client import Cube, network_schools
from .report import RunResult, shown_counts
from .trace import TRACED, _failure

PLACEHOLDER = "{unmatched}"
UNEXPLAINED = "UNEXPLAINED"
COLUMNS = ("item_key", "cause", "n")
SIDES = ("cube", "dashboard")
_BUCKET = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}")
_BLOCK = re.compile(
    r"--\s*cause\s+(?P<bucket>\S+)\s*=\s*(?P<side>\S+?)\s*:\s*(?P<words>.*\S)\s*"
)
# A committed proof names no person: no email, no ID-like number.
_ID_LIKE = re.compile(r"\d{5,}|@")


def proofs_dir(view_file: Path, view: str) -> Path:
    """Where a view's proofs live: beside its validation file."""
    return view_file.parent / "proofs" / view


def proof_path(directory: Path, comparison: str, bucket: str) -> Path:
    return directory / f"{comparison}__{bucket}.sql"


@dataclass(frozen=True)
class Proof:
    """One stored proof: its bucket map and its SQL."""

    path: Path
    comparison: str
    bucket: str
    causes: dict[str, tuple[str, str]]
    body: str
    # The file's own text, when read from disk: its fingerprint is of that.
    raw: str = ""

    @property
    def text(self) -> str:
        return self.raw or compose(self.causes, self.body)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.text)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def compose(causes: dict[str, tuple[str, str]], body: str) -> str:
    """The proof file: its bucket map as a comment block, then the SQL."""
    block = [f"-- cause {b} = {side}: {words}" for b, (side, words) in causes.items()]
    return "\n".join(block) + ("\n\n" if block else "") + body.strip() + "\n"


def split_block(text: str) -> tuple[dict[str, tuple[str, str]], str]:
    """A proof's leading `-- cause` block and the SQL after it.

    Raises:
        pipeline.Refusal: A line of the block names no side or no words.
    """
    causes: dict[str, tuple[str, str]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].strip().startswith("-- cause"):
        bucket, side, words = _cause(lines[i].strip())
        causes[bucket] = (side, words)
        i += 1
    return causes, "\n".join(lines[i:]).strip()


def _cause(line: str) -> tuple[str, str, str]:
    m = _BLOCK.fullmatch(line)
    if not m:
        raise pipeline.Refusal(
            f"cannot read {line!r}: write `-- cause <bucket> = <side>: <plain words>`"
        )
    return _checked(m["bucket"], m["side"], m["words"])


def _checked(bucket: str, side: str, words: str) -> tuple[str, str, str]:
    if not _BUCKET.fullmatch(bucket) or bucket == UNEXPLAINED:
        raise pipeline.Refusal(
            f"bucket {bucket!r}: use letters, digits and _, starting with a "
            f"letter, and not {UNEXPLAINED}"
        )
    if side not in SIDES:
        raise pipeline.Refusal(f"bucket {bucket}: side must be cube or dashboard")
    words = " ".join(words.split())
    if not words:
        raise pipeline.Refusal(f"bucket {bucket}: say what the cause is in words")
    if _ID_LIKE.search(words):
        raise pipeline.Refusal(
            f"bucket {bucket}: the words hold an email or an ID-like number; "
            "a proof is committed, so name no student or staff member"
        )
    return bucket, side, words


def parse_cause_flag(flag: str) -> tuple[str, str, str]:
    """`<bucket>=<side>:<plain words>`, checked."""
    bucket, eq, rest = flag.partition("=")
    side, colon, words = rest.partition(":")
    if not eq or not colon:
        raise pipeline.Refusal(f"--cause {flag!r}: write <bucket>=<side>:<plain words>")
    return _checked(bucket.strip(), side.strip(), words)


def read_proof(path: Path) -> Proof:
    """A stored proof, named `<comparison>__<bucket>.sql`."""
    comparison, sep, bucket = path.stem.rpartition("__")
    if not sep or bucket not in TRACED:
        raise pipeline.Refusal(
            f"{path.name}: name a proof <comparison>__<cube_only|dashboard_only>.sql"
        )
    raw = path.read_text()
    causes, body = split_block(raw)
    return Proof(path, comparison, bucket, causes, body, raw)


# --- the checks -------------------------------------------------------------------


def grain_names(comparison: Comparison) -> set[str]:
    """Every name a grain column goes by, lowercased."""
    grain = comparison.rows.grain if comparison.rows else []
    return {n.lower() for p in grain for n in (p.cube, p.dashboard)}


_STOP = (exp.Predicate, exp.Connector, exp.Not, exp.Subquery, exp.AggFunc, exp.Exists)


def _selected(node: exp.Expression):
    """The columns whose values a projection returns, not those it only tests."""
    if isinstance(node, _STOP):
        return
    if isinstance(node, exp.Column):
        yield node.name.lower()
        return
    if isinstance(node, exp.Case):
        for branch in node.args.get("ifs") or []:
            yield from _selected(branch.args.get("true"))
        if node.args.get("default") is not None:
            yield from _selected(node.args["default"])
        return
    if isinstance(node, exp.If):
        yield from _selected(node.args.get("true"))
        if node.args.get("false") is not None:
            yield from _selected(node.args["false"])
        return
    for child in node.iter_expressions():
        yield from _selected(child)


def _outer_selects(node: exp.Expression):
    if isinstance(node, exp.SetOperation):
        yield from _outer_selects(node.left)
        yield from _outer_selects(node.right)
    elif isinstance(node, exp.Subquery):
        yield from _outer_selects(node.this)
    elif isinstance(node, exp.Select):
        yield node


def check_sql(body: str, grain: set[str]) -> None:
    """Refuse a proof that could return or name a row, before it runs.

    Raises:
        pipeline.Refusal: No `{unmatched}`; SQL that does not parse; an
            outer SELECT returning `*`, a column other than `item_key`,
            `cause` and `n`, or a grain column's value; or a grain column
            compared with a literal (a row named by its value).
    """
    if PLACEHOLDER not in body:
        raise pipeline.Refusal(f"the proof never reads {PLACEHOLDER}")
    try:
        tree = sqlglot.parse_one(
            body.replace(PLACEHOLDER, "(SELECT 1 AS item_key)"), read="bigquery"
        )
    except SqlglotError as exc:
        raise pipeline.Refusal(
            f"the proof does not parse as BigQuery SQL: {type(exc).__name__}"
        ) from exc
    selects = list(_outer_selects(tree))
    if not selects:
        raise pipeline.Refusal("the proof is not a SELECT")
    for select in selects:
        names = []
        for projection in select.expressions:
            if isinstance(projection, exp.Star) or (
                isinstance(projection, exp.Column)
                and isinstance(projection.this, exp.Star)
            ):
                raise pipeline.Refusal(
                    "the proof selects *; return only item_key, cause, n"
                )
            names.append(projection.alias_or_name.lower())
            if hit := sorted(set(_selected(projection.unalias())) & grain):
                raise pipeline.Refusal(
                    f"the proof selects the grain column {', '.join(hit)}; "
                    "return counts only"
                )
        if sorted(names) != sorted(COLUMNS):
            raise pipeline.Refusal(
                f"the proof returns {', '.join(names) or 'nothing'}; return only "
                "item_key, cause, n"
            )
    for node in tree.find_all(exp.Predicate):
        children = list(node.iter_expressions())
        named = any(
            isinstance(c, exp.Column) and c.name.lower() in grain for c in children
        )
        literal = any(isinstance(c, exp.Literal) for c in children)
        if named and literal:
            raise pipeline.Refusal(
                "the proof compares a grain column with a literal: never name a row "
                "by its value"
            )


# --- the rows it reads ------------------------------------------------------------


def unmatched_sql(
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    bucket: str,
    items: list[tuple[str, Group]],
) -> str:
    """Every unmatched row of the bucket, as the run's reconcile finds them.

    Returns `item_key` (the triage item id of the row's group, NULL for a row
    no open group holds), the grain under its Cube names (as the side holding
    the row types it), and the group-by columns as text.
    """
    if comparison.rows is None:
        raise pipeline.Refusal(f"comparison {comparison.id!r} has no rows to prove")
    side = "c" if bucket == "cube_only" else "d"
    grain = comparison.rows.grain
    extra = [
        f"{side}.{p.cube if side == 'c' else p.dashboard} AS __g{i}"
        for i, p in enumerate(grain)
    ]
    dims = pipeline.group_dims(comparison)
    ctes, _ = compare._joined(
        pipeline.wrap_cube(
            sides.cube_rows_sql,
            cfg.view,
            sides.columns,
            pipeline._date_cubes(cfg),
            None,
        ),
        sides.dashboard.sql,
        comparison.rows,
        dims,
        pipeline._filter_flags(comparison),
        extra=extra,
    )
    whens = []
    for item_id, g in items:
        test = " AND ".join(
            f"IFNULL({column}, '') = {pipeline._lit(value)}" for column, value in g.dims
        )
        whens.append(f"WHEN {test or 'TRUE'} THEN {pipeline._lit(item_id)}")
    key = f"CASE {' '.join(whens)} END" if whens else "CAST(NULL AS STRING)"
    columns = [f"{key} AS item_key"]
    columns += [f"__g{i} AS {p.cube}" for i, p in enumerate(grain)]
    columns += [p.cube for p in dims]
    return (
        ctes
        # trunk-ignore(bandit/B608): identifiers are validated in config.py; values are bound literals
        + f"\nSELECT {', '.join(columns)}\nFROM joined WHERE bucket = '{bucket}'"
    )


# --- one proof's outcome -----------------------------------------------------------


@dataclass
class Outcome:
    """What one proof found for one item."""

    n_rows: int
    counts: Counter
    unexplained: int = 0

    @property
    def counted(self) -> int:
        return sum(self.counts.values())

    @property
    def explained(self) -> bool:
        return self.n_rows > 0 and not self.unexplained and self.counted == self.n_rows

    def gap_line(self, name: str) -> str:
        """Why the proof does not prove the item, with exact counts."""
        if self.counted > self.n_rows:
            return (
                f"proof {name} counts {self.counted} rows, more than its {self.n_rows}"
            )
        return f"proof {name} leaves {self.n_rows - self.counted} rows unexplained"


def outcomes(
    rows: list[dict], proof: Proof, items: list[tuple[str, Group]]
) -> dict[str, Outcome]:
    """Read a proof's result per item, refusing a result that is not counts.

    Raises:
        pipeline.Refusal: A row has a column other than `item_key`, `cause`
            and `n`; an `item_key` that is no open item of the bucket; a
            `cause` the bucket map lacks; `n` that is not a count; or 2 rows
            for one item and cause.
    """
    out = {item_id: Outcome(g.n_rows, Counter()) for item_id, g in items}
    seen: set[tuple[str, str]] = set()
    unmapped: set[str] = set()
    for r in rows:
        if set(r) != set(COLUMNS):
            raise pipeline.Refusal(
                f"{proof.path.name} returned {', '.join(sorted(r))}; return only "
                "item_key, cause, n"
            )
        key, cause, n = r["item_key"], r["cause"], r["n"]
        if key is None:
            continue
        if key not in out:
            raise pipeline.Refusal(
                f"{proof.path.name} returned an item_key that is no open item of "
                f"{proof.comparison} {proof.bucket}; return {PLACEHOLDER}'s item_key"
            )
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise pipeline.Refusal(f"{proof.path.name}: `n` must be a row count")
        cause = "" if cause is None else str(cause)
        if (key, cause) in seen:
            raise pipeline.Refusal(
                f"{proof.path.name} returned 2 rows for one item and cause; group "
                "by item_key and cause"
            )
        seen.add((key, cause))
        if cause == UNEXPLAINED:
            out[key].unexplained += n
        elif cause in proof.causes:
            out[key].counts[cause] += n
        else:
            unmapped.add(cause)
    if unmapped:
        named = sorted(b for b in unmapped if _BUCKET.fullmatch(b))
        other = len(unmapped) - len(named)
        what = ", ".join(named) + (
            f"{', ' if named else ''}{other} value(s) that are not bucket names"
            if other
            else ""
        )
        raise pipeline.Refusal(
            f"{proof.path.name}: no --cause for {what}; map every bucket "
            "(`--cause <bucket>=<side>:<plain words>`)"
        )
    return out


def run_proof(
    wh: Warehouse,
    cfg: ViewConfig,
    comparison: Comparison,
    sides: pipeline.RowSides,
    proof: Proof,
    items: list[tuple[str, Group]],
) -> dict[str, Outcome]:
    """Check, price and run a proof on the run's rows. Call inside `wh.budget`.

    Raises:
        pipeline.Refusal: The proof fails a check (see `check_sql` and
            `outcomes`) or BigQuery refuses it; only its job id and reason
            are kept.
        CostCapError: It would pass the run's or the day's cap.
    """
    check_sql(proof.body, grain_names(comparison))
    rows_sql = unmatched_sql(cfg, comparison, sides, proof.bucket, items)
    sql = proof.body.replace(PLACEHOLDER, f"(\n{rows_sql}\n)")
    try:
        usd = wh.estimate(sql)
        wh.refuse_past_caps(usd)
        print(f"Proof {proof.path.name}: ${usd:.2f} (dry run).")
        rows = wh.rows(sql)
    except GoogleAPIError as exc:
        raise pipeline.Refusal(
            f"{proof.path.name}: BigQuery refused it ({_failure(exc)})"
        ) from exc
    return outcomes(rows, proof, items)


# --- re-sorting triage items -------------------------------------------------------


def _proof_lines(proof: Proof, outcome: Outcome, posted: bool) -> list[str]:
    ranked = outcome.counts.most_common()
    _, texts = shown_counts(outcome.n_rows, [n for _, n in ranked], posted)
    return [
        f"proof {proof.path.name}: {proof.causes[b][1]}: {t} rows"
        for (b, _), t in zip(ranked, texts, strict=True)
    ]


def _kept(lines: list[str]) -> list[str]:
    """An item's evidence without any earlier proof's lines."""
    return [line for line in lines if not line.startswith("proof ")]


def apply_outcomes(items: list[dict], proof: Proof, found: dict[str, Outcome]) -> None:
    """Move each fully explained item to `cause`; note the rest in place."""
    for item in items:
        outcome = found.get(item["id"])
        if outcome is None:
            continue
        evidence = _kept(item.get("evidence") or [])
        posted = _kept(item.get("evidence_posted") or item.get("evidence") or [])
        if outcome.explained:
            also = [line for line in evidence if line.startswith("also covers: ")]
            item.update(
                suggestion="cause",
                cause=[
                    {
                        "side": proof.causes[b][0],
                        "step": b,
                        "label": proof.causes[b][1],
                        "n_rows": n,
                    }
                    for b, n in outcome.counts.most_common()
                ],
                proof={"path": str(proof.path), "fingerprint": proof.fingerprint},
                evidence=_proof_lines(proof, outcome, False) + also,
                evidence_posted=_proof_lines(proof, outcome, True) + also,
            )
            continue
        # A bucket's groups reach `cause` only through its proof.
        item.update(suggestion="investigate", cause=None, proof=None)
        item["evidence"] = [outcome.gap_line(proof.path.name), *evidence]
        if outcome.counted > outcome.n_rows:
            shown = f"proof {proof.path.name} counts more rows than the item holds"
        else:
            masked = shown_counts(outcome.n_rows - outcome.counted, [], True)[0]
            shown = f"proof {proof.path.name} leaves {masked} rows unexplained"
        item["evidence_posted"] = [shown, *posted]


def note(items: list[dict], ids: set[str], line: str) -> None:
    """Add a line to each listed item's evidence."""
    for item in items:
        if item["id"] in ids:
            evidence = item.get("evidence") or []
            posted = item.get("evidence_posted") or evidence
            item["evidence"] = [line, *evidence]
            item["evidence_posted"] = [line, *posted]


def _bucket_items(run: RunResult, comparison: str, bucket: str):
    return [
        (item.id, g)
        for item, g in triage._entries(run)
        if isinstance(g, Group) and g.comparison_id == comparison and g.bucket == bucket
    ]


def link_cells(
    run: RunResult, items: list[dict], comparison: str | None = None
) -> dict[str, tuple[int, int]]:
    """Move each cell set whose differing cells' rows all lie in proven groups.

    A cell's rows lie in the open groups of its comparison whose columns agree
    with the cell's. A cell no open group agrees with, or one a group outside
    `cause` agrees with, is not linked.

    Returns:
        Per cell-set item id, the differing cells not linked and all of them.
    """
    entries = triage._entries(run)
    by_id = {i["id"]: i for i in items}
    out = {}
    for item, source in entries:
        if item.kind != "cells" or (comparison and item.comparison != comparison):
            continue
        groups = [
            (i.id, g)
            for i, g in entries
            if isinstance(g, Group) and g.comparison_id == item.comparison
        ]
        cells = [c for c in run.diff_cells if c["comparison"] == item.comparison]
        unlinked, used = 0, {}
        for cell in cells:
            match = [
                (gid, g)
                for gid, g in groups
                if all(
                    g.value_of(col) is None
                    or pipeline._key(g.value_of(col)) == pipeline._key(value)
                    for col, value in cell["dims"]
                )
            ]
            proven = [gid for gid, _ in match if by_id[gid]["suggestion"] == "cause"]
            if not match or len(proven) < len(match):
                unlinked += 1
            else:
                used |= dict.fromkeys(proven)
        out[item.id] = (unlinked, len(cells))
        target = by_id[item.id]
        if cells and not unlinked:
            merged: dict[tuple, dict] = {}
            for gid in used:
                for c in by_id[gid]["cause"] or []:
                    k = (c["side"], c["step"], c["label"])
                    entry = merged.setdefault(k, {**c, "n_rows": 0})
                    entry["n_rows"] += c["n_rows"] or 0
            line = (
                f"every differing cell's rows lie in proven groups: {', '.join(used)}"
            )
            target.update(
                suggestion="cause",
                cause=list(merged.values()),
                proof={"groups": list(used)},
                evidence=[line],
                evidence_posted=[line],
            )
        else:
            if target.get("suggestion") == "cause":
                target.update(suggestion="investigate", cause=None, proof=None)
            line = (
                f"{unlinked} of {len(cells)} differing cells have rows outside "
                "proven groups"
                if cells
                else "the run lists no differing cells to link; `run` again"
            )
            target["evidence"] = [line, *_unlinked(target.get("evidence"))]
            target["evidence_posted"] = [
                line,
                *_unlinked(target.get("evidence_posted")),
            ]
    return out


def _unlinked(lines: list[str] | None) -> list[str]:
    """Evidence without an earlier link line."""
    return [
        e
        for e in lines or []
        if "differing cells have rows" not in e and "no differing cells" not in e
    ]


def reprove(
    cfg: ViewConfig,
    run: RunResult,
    items: list[dict],
    directory: Path,
    *,
    wh: Warehouse,
    cube: Cube,
) -> None:
    """Re-run every stored proof of the view on the run's rows, then link cells.

    A proof that cannot run (a failed check, a cap, a BigQuery error, its SQL
    no longer the run's) notes why on its items and moves none of them.
    Call inside `wh.budget`.
    """
    by_id = {c.id: c for c in cfg.comparisons}
    schools: set[str] | None = None
    for path in sorted(directory.glob("*__*.sql")) if directory.is_dir() else []:
        try:
            proof = read_proof(path)
        except pipeline.Refusal as exc:
            print(f"Proof {path.name} skipped: {exc}")
            continue
        comparison = by_id.get(proof.comparison)
        bucket_items = _bucket_items(run, proof.comparison, proof.bucket)
        if comparison is None or not bucket_items:
            continue
        ids = {i for i, _ in bucket_items}
        try:
            if schools is None:
                schools = network_schools(wh)
            sides = pipeline.row_sides(
                cfg,
                comparison,
                wh=wh,
                cube=cube,
                build=run.moment,
                schools=schools,
                fingerprints=run.fingerprints.get(comparison.id, {}),
            )
            found = run_proof(wh, cfg, comparison, sides, proof, bucket_items)
        except (pipeline.Refusal, CostCapError, ViewHistoryError) as exc:
            note(items, ids, f"proof {path.name} not run: {exc}")
            continue
        except GoogleAPIError as exc:
            note(items, ids, f"proof {path.name} not run ({_failure(exc)})")
            continue
        apply_outcomes(items, proof, found)
    link_cells(run, items)


# --- the command -------------------------------------------------------------------


def _load_triage(run: RunResult, run_json: Path) -> tuple[Path, dict]:
    found = run_json.parent / "triage.json"
    again = f"run `triage` for {run.moment.start:%Y-%m-%d %H:%M} UTC first"
    if not found.exists():
        raise pipeline.Refusal(f"{run.view}: no triage of the latest run; {again}")
    try:
        loaded = json.loads(found.read_text())
    except json.JSONDecodeError as exc:
        raise pipeline.Refusal(
            f"{run.view}: triage.json is unreadable; {again}"
        ) from exc
    if not isinstance(loaded, dict) or loaded.get("moment") != triage._moment(run):
        raise pipeline.Refusal(f"{run.view}: triage.json is of another moment; {again}")
    if set(triage.open_keys(run)) - set(loaded.get("open") or []):
        raise pipeline.Refusal(
            f"{run.view}: the latest run has open items its triage lacks; {again}"
        )
    return found, loaded


def _save_triage(path: Path, loaded: dict, items: list[dict]) -> None:
    loaded["items"] = sorted(
        items, key=lambda i: triage.SUGGESTIONS.index(i["suggestion"])
    )
    path.write_text(json.dumps(loaded, indent=1))


def _report(items: list[dict], wanted: set[str] | None) -> None:
    for item in items:
        if wanted and item["id"] not in wanted:
            continue
        print(f"- {item['id']}: {item['suggestion']}")
        for line in item.get("evidence") or []:
            print(f"    {line}")


def run_confirm(
    cfg: ViewConfig,
    view_file: Path,
    *,
    wh: Warehouse,
    cube: Cube,
    max_usd: float,
    cache_root: Path,
    comparison: str,
    bucket: str | None = None,
    sql: Path | None = None,
    causes: list[str] | None = None,
    items: list[str] | None = None,
    cells: bool = False,
) -> int:
    """Run a new or edited proof once, save it, and re-sort the triage.

    With `cells`, runs no query: confirms the comparison's cell set when every
    differing cell's rows lie in groups in `cause`.

    Args:
        cfg: The view's config.
        view_file: Its validation file; proofs are saved beside it.
        wh: The warehouse.
        cube: Cube, to rebuild the run's row SQL.
        max_usd: The cap for this command.
        cache_root: The local cache holding the run and its triage.
        comparison: The comparison the proof covers.
        bucket: `cube_only` or `dashboard_only`.
        sql: The proof's SQL; it may carry a `-- cause` block. Defaults to
            the stored proof, to re-run it after an edit.
        causes: `<bucket>=<side>:<plain words>` per bucket, added to (and
            replacing entries of) the SQL's own block.
        items: Triage item ids to print; every item of the bucket is proven
            either way.
        cells: Confirm the comparison's cell set instead.

    Returns:
        0.

    Raises:
        pipeline.Refusal: No triage of the latest run; an unknown comparison
            or bucket; a proof that fails a check; or, with `cells`, a
            differing cell whose rows are not all in proven groups.
        CostCapError: The proof would pass a cap.
    """
    run, run_json = pipeline.latest_run(cfg, cache_root)
    path, loaded = _load_triage(run, run_json)
    all_items = loaded.get("items", [])
    target = next((c for c in cfg.comparisons if c.id == comparison), None)
    if target is None:
        raise pipeline.Refusal(f"{cfg.view}: no comparison {comparison!r}")
    wanted = set(items or []) or None

    if cells:
        linked = link_cells(run, all_items, comparison)
        if not linked:
            raise pipeline.Refusal(f"{comparison}: no open cell set to confirm")
        for item_id, (unlinked, total) in linked.items():
            if unlinked:
                raise pipeline.Refusal(
                    f"{item_id}: {unlinked} of {total} differing cells have rows "
                    "outside groups in `cause`; prove those groups first"
                )
        _save_triage(path, loaded, all_items)
        _report(all_items, set(linked))
        print(f"Saved {path}")
        return 0

    if bucket not in TRACED:
        raise pipeline.Refusal(f"--bucket must be one of {', '.join(TRACED)}")
    stored = proof_path(proofs_dir(view_file, cfg.view), comparison, bucket)
    source = sql or stored
    if not source.is_file():
        raise pipeline.Refusal(f"{source}: no such proof; pass --sql <file>")
    block, body = split_block(source.read_text())
    for flag in causes or []:
        b, side, words = parse_cause_flag(flag)
        block[b] = (side, words)
    proof = Proof(stored, comparison, bucket, block, body)
    bucket_items = _bucket_items(run, comparison, bucket)
    if not bucket_items:
        raise pipeline.Refusal(f"{comparison} {bucket}: no open row group to prove")
    if wanted and (unknown := wanted - {i for i, _ in bucket_items}):
        raise pipeline.Refusal(
            f"--items: {len(unknown)} id(s) are no open item of {comparison} {bucket}"
        )

    with wh.budget(max_usd):
        sides = pipeline.row_sides(
            cfg,
            target,
            wh=wh,
            cube=cube,
            build=run.moment,
            schools=network_schools(wh),
            fingerprints=run.fingerprints.get(comparison, {}),
        )
        found = run_proof(wh, cfg, target, sides, proof, bucket_items)

    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_text(proof.text)
    apply_outcomes(all_items, proof, found)
    link_cells(run, all_items, comparison)
    _save_triage(path, loaded, all_items)
    moved = sum(1 for o in found.values() if o.explained)
    print(f"Saved {stored}: {moved} of {len(found)} items proven.")
    _report(all_items, wanted or set(found))
    print(f"Saved {path}")
    return 0
