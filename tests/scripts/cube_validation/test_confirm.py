import contextlib
import json
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import confirm, pipeline, triage

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf
from google.api_core.exceptions import BadRequest

BUILD = Build(
    datetime(2026, 10, 28, 21, 34, tzinfo=timezone.utc),
    datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc),
    "job",
)
ROWS = RowSpec(
    grain=[ColumnPair("student", "lea"), ColumnPair("item", "aid")], values=[]
)
COMPARISON = Comparison(
    id="mastery",
    measure="pct",
    dims=[ColumnPair("school", "abbreviation")],
    rows=ROWS,
)
CFG = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON])
CUBE = (
    "SELECT lea AS `v__lea`, aid AS `v__aid`, abbreviation AS `v__abbreviation` "
    "FROM `teamster-332318.m.cube_t` AS c"
)
DASH = (
    "SELECT f.student, f.item, f.school FROM `teamster-332318.d.fact` AS f "
    "WHERE f.ok1 AND f.ok2"
)
SIDES = pipeline.RowSides(
    cube=AsOf(CUBE, frozenset({"m.cube_t"}), frozenset()),
    dashboard=AsOf(DASH, frozenset(), frozenset()),
    cube_rows_sql=CUBE,
    columns=["lea", "aid", "abbreviation"],
)
PROOF = """
SELECT u.item_key,
  CASE WHEN NOT f.ok1 THEN 'C1' WHEN NOT f.ok2 THEN 'C2' ELSE 'UNEXPLAINED' END
    AS cause,
  COUNT(*) AS n
FROM {unmatched} AS u
JOIN `teamster-332318.d.fact` AS f ON f.student = u.lea AND f.item = u.aid
GROUP BY 1, 2
"""
CAUSES = {
    "C1": ("dashboard", "the dashboard drops rows that fail ok1"),
    "C2": ("dashboard", "the dashboard drops rows that fail ok2"),
}


class Wh:
    """A warehouse on DuckDB toy tables; prices every query at $0.01."""

    def __init__(self, duck):
        self.duck = duck
        self.priced: list[str] = []

    def estimate(self, sql):
        self.priced.append(sql)
        return 0.01

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql, timeout_s=None):
        return self.duck.rows(sql)

    @contextlib.contextmanager
    def budget(self, max_usd):
        yield


def _tables(duck, cube_rows, fact_rows):
    duck.table("cube_t", "lea BIGINT, aid VARCHAR, abbreviation VARCHAR", cube_rows)
    duck.table(
        "fact",
        "student BIGINT, item VARCHAR, school VARCHAR, ok1 BOOLEAN, ok2 BOOLEAN",
        fact_rows,
    )


def _group(n, school="X", bucket="cube_only"):
    return Group("mastery", (("abbreviation", school),), bucket, n, n)


def _run(groups, cells=(), diff_cells=()):
    return RunResult(
        view="v",
        moment=BUILD,
        measures=[],
        applied=Applied(open=list(groups), open_cells=list(cells)),
        diff_cells=list(diff_cells),
    )


def _items(run):
    return [triage._as_json(s) for s in triage.suggest(CFG, run, {}, traces={})]


def _proof(tmp_path, body=PROOF, causes=None):
    directory = tmp_path / "proofs" / "v"
    directory.mkdir(parents=True, exist_ok=True)
    path = confirm.proof_path(directory, "mastery", "cube_only")
    # Hand-written: extra blank lines the tool would not compose.
    path.write_text(
        confirm.compose(CAUSES if causes is None else causes, body) + "\n\n"
    )
    return directory, path


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(confirm, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: SIDES)


def _by_id(items):
    return {i["id"]: i for i in items}


# --- a stored proof, re-run by every triage -----------------------------------------


def test_a_stored_proof_proves_every_row_of_an_item(duck, tmp_path, offline):
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")],
        [(1, "a", "X", False, True), (2, "b", "X", True, False),
         (3, "c", "X", False, False)],
    )  # fmt: skip
    run = _run([_group(3)])
    items = _items(run)
    directory, path = _proof(tmp_path)

    confirm.reprove(CFG, run, items, directory, wh=Wh(duck), cube=None)

    (item,) = items
    assert item["suggestion"] == "cause"
    assert item["cause"] == [
        {"side": "dashboard", "step": "C1", "label": CAUSES["C1"][1], "n_rows": 2},
        {"side": "dashboard", "step": "C2", "label": CAUSES["C2"][1], "n_rows": 1},
    ]
    assert item["proof"] == {
        "path": str(path),
        "fingerprint": confirm.fingerprint(path.read_text()),
    }


def test_new_rows_the_proof_does_not_cover_reopen_the_item(duck, tmp_path, offline):
    # A new run: row (4, d) has no fact row, so the proof's join drops it.
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "X"), (4, "d", "X")],
        [(1, "a", "X", False, True), (2, "b", "X", True, False)],
    )
    run = _run([_group(3)])
    items = _items(run)
    directory, _ = _proof(tmp_path)

    confirm.reprove(CFG, run, items, directory, wh=Wh(duck), cube=None)

    (item,) = items
    assert item["suggestion"] == "investigate" and item["cause"] is None
    assert (
        item["evidence"][0] == "proof mastery__cube_only.sql leaves 1 rows unexplained"
    )
    assert item["evidence_posted"][0] == (
        "proof mastery__cube_only.sql leaves <10 rows unexplained"
    )


def test_a_partly_explained_item_stays_while_a_full_one_moves(
    duck, tmp_path, offline, monkeypatch
):
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "Y"), (3, "c", "Y")],
        [(1, "a", "X", False, True), (2, "b", "Y", True, False),
         (3, "c", "Y", True, True)],
    )  # fmt: skip
    # (3, c) passes both filters on the fact but is Cube-only: UNEXPLAINED.
    run = _run([_group(1, "X"), _group(2, "Y")])
    items = _items(run)
    directory, _ = _proof(tmp_path)
    dash_without_3 = pipeline.RowSides(
        cube=SIDES.cube,
        dashboard=AsOf(DASH + " AND f.student <> 3", frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=SIDES.columns,
    )
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: dash_without_3)

    confirm.reprove(CFG, run, items, directory, wh=Wh(duck), cube=None)

    by_id = _by_id(items)
    assert by_id["mastery:abbreviation=<redacted>"]["suggestion"] == "cause"
    partly = by_id["mastery:abbreviation=<redacted>#2"]
    assert partly["suggestion"] == "investigate"
    assert partly["evidence"][0] == (
        "proof mastery__cube_only.sql leaves 1 rows unexplained"
    )


def test_a_proof_that_cannot_run_notes_why_and_moves_nothing(duck, tmp_path, offline):
    _tables(duck, [(1, "a", "X")], [(1, "a", "X", False, True)])
    run = _run([_group(1)])
    items = _items(run)
    directory, _ = _proof(tmp_path)

    class Failing(Wh):
        def rows(self, sql, timeout_s=None):
            exc = BadRequest("value 12345 bad", errors=[{"reason": "invalidQuery"}])
            raise exc

    confirm.reprove(CFG, run, items, directory, wh=Failing(duck), cube=None)

    (item,) = items
    assert item["suggestion"] == "investigate"
    assert item["evidence"][0].startswith("proof mastery__cube_only.sql not run:")
    assert "invalidQuery" in item["evidence"][0] and "12345" not in item["evidence"][0]


# --- the checks ------------------------------------------------------------------


GRAIN = {"lea", "aid", "student", "item"}


@pytest.mark.parametrize(
    ("sql", "why"),
    [
        ("SELECT item_key, cause, n FROM t", "never reads"),
        (
            "SELECT u.item_key, 'C1' AS cause, COUNT(*) AS n, u.abbreviation "
            "FROM {unmatched} AS u GROUP BY 1, 2, 4",
            "returns item_key, cause, n, abbreviation",
        ),
        (
            "SELECT u.item_key, CAST(u.lea AS STRING) AS cause, COUNT(*) AS n "
            "FROM {unmatched} AS u GROUP BY 1, 2",
            "grain column lea",
        ),
        (
            "SELECT u.item_key, CASE WHEN TRUE THEN u.aid END AS cause, "
            "COUNT(*) AS n FROM {unmatched} AS u GROUP BY 1, 2",
            "grain column aid",
        ),
        ("SELECT * FROM {unmatched}", "selects *"),
        (
            "SELECT u.item_key, 'C1' AS cause, COUNT(*) AS n FROM {unmatched} AS u "
            "WHERE u.lea = 12345 GROUP BY 1, 2",
            "compares a grain column with a literal",
        ),
    ],
)
def test_check_sql_refuses_what_could_return_or_name_a_row(sql, why):
    with pytest.raises(pipeline.Refusal, match=why):
        confirm.check_sql(sql, GRAIN)


def test_check_sql_lets_a_grain_column_drive_a_condition():
    confirm.check_sql(PROOF, GRAIN)
    confirm.check_sql(
        "SELECT u.item_key, CASE WHEN NOT EXISTS (SELECT 1 FROM w "
        "WHERE w.student = u.lea) THEN 'C4' ELSE 'UNEXPLAINED' END AS cause, "
        "COUNT(*) AS n FROM {unmatched} AS u GROUP BY 1, 2",
        GRAIN,
    )


def _outcome(rows, causes=None):
    proof = confirm.Proof(
        confirm.proof_path(confirm.Path("p"), "mastery", "cube_only"),
        "mastery",
        "cube_only",
        CAUSES if causes is None else causes,
        PROOF,
    )
    return confirm.outcomes(rows, proof, [("i", _group(3))])


def test_a_complete_proof_explains_its_item():
    (found,) = _outcome(
        [
            {"item_key": "i", "cause": "C1", "n": 2},
            {"item_key": "i", "cause": "C2", "n": 1},
        ]
    ).values()

    assert found.explained


@pytest.mark.parametrize(
    "rows",
    [
        # UNEXPLAINED above 0
        [{"item_key": "i", "cause": "C1", "n": 2},
         {"item_key": "i", "cause": "UNEXPLAINED", "n": 1}],
        # a short count
        [{"item_key": "i", "cause": "C1", "n": 2}],
        # more rows than the item holds
        [{"item_key": "i", "cause": "C1", "n": 4}],
    ],
)  # fmt: skip
def test_an_incomplete_proof_never_explains_its_item(rows):
    (found,) = _outcome(rows).values()

    assert not found.explained


@pytest.mark.parametrize(
    ("rows", "why"),
    [
        ([{"item_key": "i", "cause": "C1", "n": 3, "lea": 1}], "returned"),
        ([{"item_key": "i", "cause": "C9", "n": 3}], "no --cause for C9"),
        ([{"item_key": "i", "cause": "x 123456", "n": 3}], "not bucket names"),
        ([{"item_key": "other", "cause": "C1", "n": 3}], "no open item"),
        (
            [{"item_key": "i", "cause": "C1", "n": 1},
             {"item_key": "i", "cause": "C1", "n": 2}],
            "2 rows for one item",
        ),
    ],
)  # fmt: skip
def test_a_result_that_is_not_counts_refuses(rows, why):
    with pytest.raises(pipeline.Refusal, match=why) as caught:
        _outcome(rows)

    assert "123456" not in str(caught.value)


@pytest.mark.parametrize(
    ("flag", "why"),
    [
        ("C1:dashboard words", "write <bucket>=<side>"),
        ("C1=sheet:words", "side must be"),
        ("UNEXPLAINED=cube:words", "not UNEXPLAINED"),
        ("C1=cube:student 1234567", "ID-like"),
    ],
)
def test_a_cause_flag_is_checked(flag, why):
    with pytest.raises(pipeline.Refusal, match=why):
        confirm.parse_cause_flag(flag)


def test_a_proof_file_keeps_its_bucket_map_in_its_leading_block():
    text = confirm.compose(CAUSES, PROOF)

    assert text.startswith(f"-- cause C1 = dashboard: {CAUSES['C1'][1]}\n")
    assert confirm.split_block(text) == (CAUSES, PROOF.strip())


# --- the command -------------------------------------------------------------------


def _saved(tmp_path, monkeypatch, run):
    run_json = tmp_path / "cache" / "v" / "m" / "run.json"
    run_json.parent.mkdir(parents=True)
    monkeypatch.setattr(pipeline, "latest_run", lambda cfg, root: (run, run_json))
    path = run_json.parent / "triage.json"
    path.write_text(
        json.dumps(
            {
                "view": "v",
                "moment": triage._moment(run),
                "decisions_fingerprint": "",
                "open": triage.open_keys(run),
                "items": _items(run),
            }
        )
    )
    return path


def test_confirm_saves_the_proof_and_re_sorts_the_triage(
    duck, tmp_path, monkeypatch, offline, capsys
):
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")],
        [(1, "a", "X", False, True), (2, "b", "X", True, False),
         (3, "c", "X", False, False)],
    )  # fmt: skip
    run = _run([_group(3)])
    triage_json = _saved(tmp_path, monkeypatch, run)
    draft = tmp_path / "draft.sql"
    draft.write_text(PROOF)
    view_file = tmp_path / "validation" / "v.yml"

    confirm.run_confirm(
        CFG,
        view_file,
        wh=Wh(duck),
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        bucket="cube_only",
        sql=draft,
        causes=[f"{b}={side}:{words}" for b, (side, words) in CAUSES.items()],
    )

    stored = tmp_path / "validation" / "proofs" / "v" / "mastery__cube_only.sql"
    assert confirm.read_proof(stored).causes == CAUSES
    (item,) = json.loads(triage_json.read_text())["items"]
    assert item["suggestion"] == "cause"
    out = capsys.readouterr().out
    # The terminal shows exact counts; only the posted copy masks them.
    assert f"{CAUSES['C1'][1]}: 2 rows" in out and "<10" not in out
    assert item["evidence_posted"][0].endswith(": <10 rows")


def test_confirm_refuses_a_bucket_it_cannot_map(duck, tmp_path, monkeypatch, offline):
    _tables(duck, [(1, "a", "X")], [(1, "a", "X", False, True)])
    run = _run([_group(1)])
    _saved(tmp_path, monkeypatch, run)
    draft = tmp_path / "draft.sql"
    draft.write_text(PROOF)

    with pytest.raises(pipeline.Refusal, match="no --cause for C1"):
        confirm.run_confirm(
            CFG,
            tmp_path / "v.yml",
            wh=Wh(duck),
            cube=None,
            max_usd=1.0,
            cache_root=tmp_path,
            comparison="mastery",
            bucket="cube_only",
            sql=draft,
            causes=["C2=dashboard:fails ok2"],
        )

    assert not (tmp_path / "proofs").exists()


CELLS_RUN = dict(
    cells=[CellDiff("mastery", {"differs": 1})],
    diff_cells=[
        {"comparison": "mastery", "cut": "{}", "key": "abbreviation=X",
         "dims": [["abbreviation", "X"]], "dashboard": 1.0, "cube": 2.0,
         "n_students": 3},
    ],
)  # fmt: skip


def test_cells_confirm_when_every_differing_cell_lies_in_proven_groups(
    tmp_path, monkeypatch
):
    run = _run([_group(3)], **CELLS_RUN)
    path = _saved(tmp_path, monkeypatch, run)
    saved = json.loads(path.read_text())
    for item in saved["items"]:
        if item["kind"] == "group":
            item.update(suggestion="cause", cause=[{"side": "dashboard",
                        "step": "C1", "label": "fails ok1", "n_rows": 3}])  # fmt: skip
    path.write_text(json.dumps(saved))

    confirm.run_confirm(
        CFG,
        tmp_path / "v.yml",
        wh=None,
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        cells=True,
    )

    cells = _by_id(json.loads(path.read_text())["items"])["mastery:cells"]
    assert cells["suggestion"] == "cause"
    assert cells["cause"] == [
        {"side": "dashboard", "step": "C1", "label": "fails ok1", "n_rows": 3}
    ]


def test_cells_refuse_with_the_count_left_outside_proven_groups(tmp_path, monkeypatch):
    run = _run([_group(3)], **CELLS_RUN)
    _saved(tmp_path, monkeypatch, run)

    with pytest.raises(pipeline.Refusal, match="1 of 1 differing cells"):
        confirm.run_confirm(
            CFG,
            tmp_path / "v.yml",
            wh=None,
            cube=None,
            max_usd=1.0,
            cache_root=tmp_path,
            comparison="mastery",
            cells=True,
        )


# --- the gate ----------------------------------------------------------------------


def test_the_gate_accepts_proven_items_until_their_proof_changes(
    duck, tmp_path, monkeypatch, offline
):
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")],
        [(1, "a", "X", False, True), (2, "b", "X", True, False),
         (3, "c", "X", False, False)],
    )  # fmt: skip
    run = _run([_group(3)])
    path = _saved(tmp_path, monkeypatch, run)
    directory, proof = _proof(tmp_path)
    saved = json.loads(path.read_text())
    confirm.reprove(CFG, run, saved["items"], directory, wh=Wh(duck), cube=None)
    path.write_text(json.dumps(saved))

    assert triage.proven_triage(run, path.parent / "run.json")["items"]
    # A hand-formatted file is fingerprinted as it stands, not as composed.
    assert confirm.read_proof(proof).fingerprint == confirm.fingerprint(
        proof.read_text()
    )

    proof.write_text(proof.read_text() + "\n-- edited\n")
    with pytest.raises(pipeline.Refusal, match="proof file changed since triage"):
        triage.proven_triage(run, path.parent / "run.json")
