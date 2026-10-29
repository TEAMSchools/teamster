import contextlib
import json
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import confirm, pipeline, trace, triage

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import CellDiff, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import (
    ColumnPair,
    Comparison,
    Decision,
    RowSpec,
    ViewConfig,
)

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo
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
# A row the join misses is UNEXPLAINED, never a cause.
PROOF = """
SELECT u.__row,
  CASE
    WHEN f.student IS NULL THEN 'UNEXPLAINED'
    WHEN NOT f.ok1 THEN 'C1'
    WHEN NOT f.ok2 THEN 'C2'
    ELSE 'UNEXPLAINED'
  END AS cause
FROM {unmatched} AS u
LEFT JOIN `teamster-332318`.`d`.`fact` AS f ON f.student = u.lea AND f.item = u.aid
"""
CAUSES = {
    "C1": ("dashboard", "the dashboard drops rows that fail ok1"),
    "C2": ("dashboard", "the dashboard drops rows that fail ok2"),
}
FACT_ROWS = [(1, "a", "X", False, True), (2, "b", "X", True, False),
             (3, "c", "X", False, False)]  # fmt: skip
CUBE_ROWS = [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")]


class Wh:
    """A warehouse on DuckDB toy tables; prices every query at $0.01."""

    def __init__(self, duck):
        self.duck = duck
        self.ran: list[tuple[str, float | None]] = []

    def estimate(self, sql):
        return 0.01

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql, timeout_s=None):
        self.ran.append((sql, timeout_s))
        return self.duck.rows(sql)

    def table(self, dataset, name):
        return TableInfo("TABLE", None)

    @contextlib.contextmanager
    def budget(self, max_usd):
        yield


def _tables(duck, cube_rows=CUBE_ROWS, fact_rows=FACT_ROWS):
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
    path.write_text(confirm.compose(CAUSES if causes is None else causes, body))
    return directory, path


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(confirm, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: SIDES)


def _by_id(items):
    return {i["id"]: i for i in items}


def _stored(run, items, directory, wh, cfg=CFG):
    """What every `triage` does: run the stored proofs, then sort by them."""
    ran = confirm.run_stored(cfg, run, directory, wh=wh, cube=None)
    confirm.apply_runs(run, items, ran, cfg)


def _reprove(duck, tmp_path, run, body=PROOF, causes=None, wh=None):
    items = _items(run)
    directory, _ = _proof(tmp_path, body, causes)
    _stored(run, items, directory, wh or Wh(duck))
    return items


# --- a stored proof, re-run by every triage -----------------------------------------


def test_a_stored_proof_proves_every_row_of_an_item(duck, tmp_path, offline):
    _tables(duck)
    wh = Wh(duck)

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=wh)

    assert item["suggestion"] == "cause"
    assert item["cause"] == [
        {"side": "dashboard", "step": "C1", "label": CAUSES["C1"][1], "n_rows": 2},
        {"side": "dashboard", "step": "C2", "label": CAUSES["C2"][1], "n_rows": 1},
    ]
    path = tmp_path / "proofs" / "v" / "mastery__cube_only.sql"
    # Recorded relative to the validation file's directory.
    assert item["proof"]["path"] == "proofs/v/mastery__cube_only.sql"
    assert item["proof"]["kind"] == "query"
    assert item["proof"]["fingerprint"] == confirm.file_fingerprint(path)
    # The proof reads its own tables as of the run, under the trace's limit.
    ((sql, timeout),) = wh.ran
    assert "`teamster-332318.d.fact` AS f FOR SYSTEM_TIME AS OF" in sql
    assert timeout == trace.TIMEOUT_S


def test_new_rows_the_proof_does_not_cover_reopen_the_item(duck, tmp_path, offline):
    # A new run: row (4, d) has no fact row, so the proof calls it UNEXPLAINED.
    _tables(duck, [(1, "a", "X"), (2, "b", "X"), (4, "d", "X")], FACT_ROWS[:2])

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]))

    assert item["suggestion"] == "investigate" and item["cause"] is None
    assert (
        item["evidence"][0] == "proof mastery__cube_only.sql leaves 1 rows unexplained"
    )
    assert item["evidence_posted"][0] == (
        "proof mastery__cube_only.sql does not explain every row"
    )


def test_a_partly_explained_item_stays_while_a_full_one_moves(
    duck, tmp_path, offline, monkeypatch
):
    # (3, c) passes both filters on the fact, so the proof leaves it UNEXPLAINED.
    _tables(
        duck,
        [(1, "a", "X"), (2, "b", "Y"), (3, "c", "Y")],
        [(1, "a", "X", False, True), (2, "b", "Y", True, False),
         (3, "c", "Y", True, True)],
    )  # fmt: skip
    without_3 = pipeline.RowSides(
        cube=SIDES.cube,
        dashboard=AsOf(DASH + " AND f.student <> 3", frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=SIDES.columns,
    )
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: without_3)

    items = _reprove(duck, tmp_path, _run([_group(1, "X"), _group(2, "Y")]))

    by_id = _by_id(items)
    assert by_id["mastery:abbreviation=<redacted>"]["suggestion"] == "cause"
    partly = by_id["mastery:abbreviation=<redacted>#2"]
    assert partly["suggestion"] == "investigate"
    assert partly["evidence"][0] == (
        "proof mastery__cube_only.sql leaves 1 rows unexplained"
    )


def test_a_proof_that_cannot_run_notes_why_and_moves_nothing(duck, tmp_path, offline):
    _tables(duck)

    class Failing(Wh):
        def rows(self, sql, timeout_s=None):
            raise BadRequest("value 12345 bad", errors=[{"reason": "invalidQuery"}])

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=Failing(duck))

    assert item["suggestion"] == "investigate"
    assert item["evidence"][0].startswith("proof mastery__cube_only.sql not run:")
    assert "invalidQuery" in item["evidence"][0] and "12345" not in item["evidence"][0]
    assert item["evidence_posted"][0] == (
        "proof mastery__cube_only.sql not run; see the terminal"
    )


def test_a_cube_error_notes_the_items_and_a_comparison_is_rebuilt_once(
    duck, tmp_path, monkeypatch
):
    monkeypatch.setattr(confirm, "network_schools", lambda wh: set())
    calls = []

    def failing(*a, **k):
        calls.append(1)
        raise confirm.CubeError("Cube answered 502")

    monkeypatch.setattr(pipeline, "row_sides", failing)
    run = _run([_group(3), _group(2, "Y", "dashboard_only")])
    items = _items(run)
    directory, _ = _proof(tmp_path)
    (directory / "mastery__dashboard_only.sql").write_text(
        confirm.compose(CAUSES, PROOF)
    )

    _stored(run, items, directory, Wh(duck))

    assert {i["suggestion"] for i in items} == {"investigate"}
    assert all("not run: Cube answered 502" in i["evidence"][0] for i in items)
    # A failed rebuild is not cached, so each proof tries once.
    assert len(calls) == 2


def test_both_buckets_of_a_comparison_share_one_rebuild(duck, tmp_path, offline,
                                                         monkeypatch):  # fmt: skip
    _tables(duck)
    calls = []
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: calls.append(1) or SIDES)
    run = _run([_group(3), _group(2, "Y", "dashboard_only")])
    directory, _ = _proof(tmp_path)
    (directory / "mastery__dashboard_only.sql").write_text(
        confirm.compose(CAUSES, PROOF)
    )

    _stored(run, _items(run), directory, Wh(duck))

    assert len(calls) == 1


def test_confirm_refreshes_the_decision_marks(duck, tmp_path, monkeypatch, offline):
    _tables(duck)
    run = _run([_group(3)])
    run.fingerprints = {"mastery": {"cube": "c", "dashboard": "d"}}
    triage_json = _saved(tmp_path, monkeypatch, run)
    fp = confirm.fingerprint(CAUSES, PROOF)
    decided = [
        Decision(f"d{i}", "mastery", "deliberate", "r",
                 cause={"side": side, "label": words},
                 fingerprints={"cube": "c", "dashboard": "d", "proof": fp})
        for i, (side, words) in enumerate(CAUSES.values())
    ]  # fmt: skip
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON],
                     decisions=decided)  # fmt: skip
    draft = tmp_path / "draft.sql"
    draft.write_text(PROOF)

    confirm.run_confirm(
        cfg,
        tmp_path / "validation" / "v.yml",
        wh=Wh(duck),
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        bucket="cube_only",
        sql=draft,
        causes=[f"{b}={side}:{words}" for b, (side, words) in CAUSES.items()],
    )

    (item,) = json.loads(triage_json.read_text())["items"]
    assert item["decided"] is True
    assert set(item["decisions"].values()) == {"d0", "d1"}


# --- the tool counts: rows dropped, repeated or named by a value refuse --------------


@pytest.mark.parametrize(
    ("body", "why"),
    [
        # An INNER JOIN drops (3, c), whose fact row is gone.
        (
            "SELECT u.__row, CASE WHEN NOT f.ok1 THEN 'C1' WHEN f.ok1 THEN 'C2' "
            "ELSE 'UNEXPLAINED' END AS cause "
            "FROM {unmatched} AS u JOIN `teamster-332318`.`d`.`fact` AS f "
            "ON f.student = u.lea AND f.item = u.aid AND (f.ok1 OR f.ok2)",
            "1 unmatched rows have no row in its output",
        ),
        # A join to a finer table repeats every row.
        (
            "SELECT u.__row, CASE WHEN TRUE THEN 'C1' ELSE 'UNEXPLAINED' END AS cause "
            "FROM {unmatched} AS u "
            "CROSS JOIN (SELECT 'C1' AS x UNION ALL SELECT 'C2') AS t",
            "3 unmatched rows appear more than once",
        ),
        # A cause computed from data, not written as a literal: refused before
        # it runs.
        (
            "SELECT u.__row, CASE WHEN TRUE THEN CAST(f.ok1 AS STRING) "
            "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
            "LEFT JOIN `teamster-332318`.`d`.`fact` AS f ON f.student = u.lea "
            "WHERE 'C1' = 'C1'",
            "must be a quoted cause name",
        ),
    ],
)
def test_the_tool_counts_and_refuses_what_is_not_one_cause_per_row(
    duck, tmp_path, offline, body, why
):
    _tables(duck)

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), body=body)

    assert item["suggestion"] == "investigate"
    assert why in item["evidence"][0]
    assert "true" not in item["evidence"][0] and "false" not in item["evidence"][0]


def test_a_cause_literal_without_a_cause_flag_refuses_by_name(duck, tmp_path, offline):
    _tables(duck)
    body = PROOF.replace("'C2'", "'C9'")

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), body=body)

    assert "no --cause for C9" in item["evidence"][0]


# --- the checks before a proof runs --------------------------------------------------


GRAIN = {"lea", "aid", "student", "item", "response_type"}
STUDENT = {"lea", "student"}


@pytest.mark.parametrize(
    ("sql", "why"),
    [
        ("SELECT __row, 'C1' AS cause FROM t", "never reads"),
        (
            "SELECT u.__row, 'C1' AS cause, u.abbreviation FROM {unmatched} AS u",
            "other than __row and cause",
        ),
        ("SELECT 1 AS __row, 'C1' AS cause FROM {unmatched} AS u", "own __row"),
        (
            "SELECT u.__row, CAST(u.lea AS STRING) AS cause FROM {unmatched} AS u "
            "WHERE 'a' = 'a'",
            "selects a grain or identifying column",
        ),
        (
            "SELECT u.__row, CASE WHEN TRUE THEN r.local_student_id END AS cause "
            "FROM {unmatched} AS u WHERE 'a' = 'a'",
            "selects a grain or identifying column",
        ),
        ("SELECT * FROM {unmatched}", "selects \\*"),
        ("SELECT u.__row, u.side AS cause FROM {unmatched} AS u", "no string literal"),
        # A literal compared with the student column, at any depth.
        (
            "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u WHERE u.lea = 7",
            "compares an identifying column with a literal",
        ),
        (
            "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u WHERE u.lea + 0 = 7",
            "compares an identifying column with a literal",
        ),
        (
            "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u "
            "WHERE u.lea IN UNNEST([7])",
            "compares an identifying column with a literal",
        ),
        (
            "SELECT u.__row, CASE WHEN r.local_student_id = 'S1' THEN 'C1' END "
            "AS cause FROM {unmatched} AS u",
            "compares an identifying column with a literal",
        ),
        # ID-like values and emails in comments and strings.
        (
            "SELECT u.__row, 'C1' AS cause -- 1234567 enrolled late\n"
            "FROM {unmatched} AS u",
            "ID-like number",
        ),
        (
            "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u "
            "WHERE u.lea = CAST('123456' AS INT64)",
            "ID-like number",
        ),
        (
            "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u "
            "/* a.person@example.org */",
            "email",
        ),
    ],
)
def test_check_sql_refuses_what_could_return_or_name_a_row(sql, why):
    with pytest.raises(pipeline.Refusal, match=why) as caught:
        confirm.check_sql(sql, GRAIN, STUDENT)

    for value in ("1234567", "123456", "person@", "S1"):
        assert value not in str(caught.value)


def test_check_sql_lets_a_model_predicate_be_copied_literally():
    assert confirm.check_sql(PROOF, GRAIN, STUDENT) == {"UNEXPLAINED", "C1", "C2"}
    # A grain column that names no one may meet a literal; the student column
    # may drive a condition through a join.
    confirm.check_sql(
        "SELECT u.__row, CASE WHEN u.response_type = 'overall' THEN 'C1' "
        "WHEN NOT EXISTS (SELECT 1 FROM w WHERE w.student = u.lea) THEN 'C4' "
        "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u",
        GRAIN,
        STUDENT,
    )


def test_check_sql_lets_a_literal_meet_an_id_that_names_no_one():
    # DDI's C3 names one assessment by its id.
    assert confirm.check_sql(
        "SELECT u.__row, CASE WHEN r.assessment_id = 189131 THEN 'C3' "
        "WHEN r.assessment_id IN (189132, 189133) THEN 'C4' "
        "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
        "LEFT JOIN `teamster-332318`.`ds`.`r` AS r ON r.student = u.lea",
        GRAIN,
        STUDENT,
    ) == {"C3", "C4", "UNEXPLAINED"}


@pytest.mark.parametrize(
    "where",
    [
        "r.staff_number = 7",
        "r.teacher_name = 'C1'",
        "r.contact_email = 'C1'",
        "r.student_key = 7",
        "r.powerschool_student_id = 7",
    ],
)
def test_check_sql_refuses_a_literal_on_a_column_that_names_a_person(where):
    with pytest.raises(pipeline.Refusal, match="identifying column with a literal"):
        confirm.check_sql(
            f"SELECT u.__row, 'C1' AS cause FROM {{unmatched}} AS u, r WHERE {where}",
            GRAIN,
            STUDENT,
        )


@pytest.mark.parametrize(
    ("flag", "why"),
    [
        ("C1:dashboard words", "<bucket>=<side>"),
        ("C1=sheet:words", "side must be"),
        ("UNEXPLAINED=cube:words", "not be UNEXPLAINED"),
        ("C1=cube:student 1234567", "ID-like"),
    ],
)
def test_a_cause_flag_is_checked(flag, why):
    with pytest.raises(pipeline.Refusal, match=why) as caught:
        confirm.parse_cause_flag(flag)

    assert "1234567" not in str(caught.value)


# --- the proof file ------------------------------------------------------------------


def test_a_proof_file_opts_out_of_trunk_and_keeps_its_bucket_map():
    text = confirm.compose(CAUSES, PROOF)

    assert text.startswith(
        "-- trunk-ignore-all(sqlfluff)\n-- fmt: off\n"
        f"-- cause C1 = dashboard: {CAUSES['C1'][1]}\n"
    )
    assert confirm.split_block(text) == (CAUSES, PROOF.strip())


def test_a_formatting_only_edit_keeps_the_fingerprint(tmp_path):
    _, path = _proof(tmp_path)
    before = confirm.file_fingerprint(path)

    path.write_text(
        path.read_text().replace("WHEN NOT f.ok1", "when   not F.OK1") + "-- a note\n"
    )
    assert confirm.file_fingerprint(path) == before

    path.write_text(path.read_text().replace("NOT f.ok2", "f.ok2"))
    assert confirm.file_fingerprint(path) != before


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


def _confirm(duck, tmp_path, causes, **kw):
    draft = tmp_path / "draft.sql"
    draft.write_text(PROOF)
    confirm.run_confirm(
        CFG,
        tmp_path / "validation" / "v.yml",
        wh=Wh(duck),
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        bucket="cube_only",
        sql=draft,
        causes=causes,
        **kw,
    )


def test_confirm_saves_the_proof_and_re_sorts_the_triage(
    duck, tmp_path, monkeypatch, offline, capsys
):
    _tables(duck)
    triage_json = _saved(tmp_path, monkeypatch, _run([_group(3)]))

    _confirm(
        duck,
        tmp_path,
        [f"{b}={side}:{words}" for b, (side, words) in CAUSES.items()],
    )

    stored = tmp_path / "validation" / "proofs" / "v" / "mastery__cube_only.sql"
    assert stored.read_text().startswith("-- trunk-ignore-all(sqlfluff)\n")
    assert confirm.read_proof(stored).causes == CAUSES
    (item,) = json.loads(triage_json.read_text())["items"]
    assert item["suggestion"] == "cause"
    out = capsys.readouterr().out
    # The terminal shows exact counts; only the posted copy masks them.
    assert f"{CAUSES['C1'][1]}: 2 rows" in out and "<10" not in out
    assert item["evidence_posted"][0].endswith(": <10 rows")


def test_confirm_refuses_a_bucket_it_cannot_map(duck, tmp_path, monkeypatch, offline):
    _tables(duck)
    _saved(tmp_path, monkeypatch, _run([_group(3)]))

    with pytest.raises(pipeline.Refusal, match="no --cause for C1"):
        _confirm(duck, tmp_path, ["C2=dashboard:fails ok2"])

    assert not (tmp_path / "validation").exists()


CELLS_RUN = dict(
    cells=[CellDiff("mastery", {"differs": 1})],
    diff_cells=[
        {"comparison": "mastery", "cut": "{}", "key": "abbreviation=X",
         "dims": [["abbreviation", "X"]], "dashboard": 1.0, "cube": 4.0,
         "n_students": 3},
    ],
)  # fmt: skip


def _cells(tmp_path, monkeypatch, proven=True, run=None, cfg=CFG):
    run = run or _run([_group(3)], **CELLS_RUN)
    path = _saved(tmp_path, monkeypatch, run)
    saved = json.loads(path.read_text())
    for item in saved["items"]:
        if item["kind"] == "group" and proven:
            item.update(suggestion="cause", cause=[{"side": "dashboard",
                        "step": "C1", "label": "fails ok1", "n_rows": 3}])  # fmt: skip
    path.write_text(json.dumps(saved))
    confirm.run_confirm(
        cfg,
        tmp_path / "v.yml",
        wh=None,
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        cells=True,
    )
    return _by_id(json.loads(path.read_text())["items"])["mastery:cells"]


def test_cells_confirm_when_every_differing_cell_lies_in_proven_groups(
    tmp_path, monkeypatch
):
    cells = _cells(tmp_path, monkeypatch)

    assert cells["suggestion"] == "cause"
    assert cells["cause"] == [
        {"side": "dashboard", "step": "C1", "label": "fails ok1", "n_rows": 3}
    ]


def test_cells_refuse_with_the_count_left_outside_proven_groups(tmp_path, monkeypatch):
    with pytest.raises(pipeline.Refusal, match="1 of 1 differing cells"):
        _cells(tmp_path, monkeypatch, proven=False)


def test_cells_refuse_when_the_difference_is_not_the_proven_rows(tmp_path, monkeypatch):
    # Cube shows 2 more than the dashboard, but the proven group holds 3 rows.
    run = _run(
        [_group(3)],
        cells=CELLS_RUN["cells"],
        diff_cells=[{**CELLS_RUN["diff_cells"][0], "cube": 3.0}],
    )

    with pytest.raises(pipeline.Refusal, match="exceed the proven rows by 1"):
        _cells(tmp_path, monkeypatch, run=run)


def test_cells_link_only_to_groups_under_their_cut(tmp_path, monkeypatch):
    by_school = Comparison(
        id="mastery",
        measure="pct",
        dims=[ColumnPair("school", "abbreviation")],
        rows=ROWS,
        filters={"School": ColumnPair("school", "abbreviation")},
    )
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[by_school])
    # The cell sits under the cut School = Y; the only proven group is X.
    run = _run(
        [_group(3)],
        cells=CELLS_RUN["cells"],
        diff_cells=[{**CELLS_RUN["diff_cells"][0], "cut": '{"School": "Y"}',
                     "dims": []}],
    )  # fmt: skip

    with pytest.raises(pipeline.Refusal, match="1 of 1 differing cells"):
        _cells(tmp_path, monkeypatch, run=run, cfg=cfg)


def test_a_null_group_and_an_empty_string_group_are_proven_apart(
    duck, tmp_path, offline
):
    _tables(
        duck,
        [(1, "a", None), (2, "b", ""), (3, "c", "")],
        [(1, "a", None, False, True), (2, "b", "", False, True),
         (3, "c", "", True, False)],
    )  # fmt: skip
    null = Group("mastery", (("abbreviation", ""),), "cube_only", 1, 1,
                 nulls=("abbreviation",))  # fmt: skip
    empty = Group("mastery", (("abbreviation", ""),), "cube_only", 2, 2)

    items = _reprove(duck, tmp_path, _run([null, empty]))

    assert [i["suggestion"] for i in items] == ["cause", "cause"]
    assert sorted(sum(c["n_rows"] for c in i["cause"]) for i in items) == [1, 2]


# --- the gate ----------------------------------------------------------------------


def test_the_gate_accepts_proven_items_until_their_proof_changes(
    duck, tmp_path, monkeypatch, offline
):
    _tables(duck)
    run = _run([_group(3)])
    path = _saved(tmp_path, monkeypatch, run)
    directory, proof = _proof(tmp_path)
    saved = json.loads(path.read_text())
    _stored(run, saved["items"], directory, Wh(duck))
    path.write_text(json.dumps(saved))

    assert triage.proven_triage(run, path.parent / "run.json", base=tmp_path)["items"]

    # Formatting is no change; a changed predicate is.
    proof.write_text(
        proof.read_text().replace("SELECT u.__row", "select   U.__ROW")
        + "\n-- reviewed\n"
    )
    assert triage.proven_triage(run, path.parent / "run.json", base=tmp_path)["items"]
    proof.write_text(proof.read_text().replace("NOT f.ok2", "f.ok2"))
    with pytest.raises(pipeline.Refusal, match="proof file changed since triage"):
        triage.proven_triage(run, path.parent / "run.json", base=tmp_path)


# --- the cause's default, unpinned tables, value differences ---------------------------


@pytest.mark.parametrize(
    "cause",
    [
        "'C1'",
        "CASE WHEN TRUE THEN 'C1' END",
        "CASE WHEN TRUE THEN 'C1' ELSE 'C2' END",
        "CASE WHEN TRUE THEN CASE WHEN FALSE THEN 'C1' ELSE 'C2' END "
        "ELSE 'UNEXPLAINED' END",
        "CASE WHEN TRUE THEN IF(u.aid = 1, 'C1', 'C2') ELSE 'UNEXPLAINED' END",
        "CASE WHEN TRUE THEN COALESCE(u.aid, 'C1') ELSE 'UNEXPLAINED' END",
        "CASE u.aid WHEN 1 THEN 'C1' ELSE 'UNEXPLAINED' END",
        "IF(TRUE, 'C1', 'UNEXPLAINED')",
    ],
)
def test_check_sql_refuses_a_cause_that_can_file_a_new_row_under_an_old_cause(cause):
    with pytest.raises(pipeline.Refusal, match="the proof's cause"):
        confirm.check_sql(
            f"SELECT u.__row, {cause} AS cause FROM {{unmatched}} AS u", GRAIN, STUDENT
        )


def test_check_sql_refuses_a_cause_carried_from_a_cte():
    with pytest.raises(pipeline.Refusal, match="quoted cause name"):
        confirm.check_sql(
            "WITH c AS (SELECT u.__row, CASE WHEN TRUE THEN 'C1' ELSE 'C9' END "
            "AS cause FROM {unmatched} AS u) SELECT u.__row, CASE WHEN TRUE THEN "
            "c.cause ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
            "JOIN c ON c.__row = u.__row",
            GRAIN,
            STUDENT,
        )


def test_check_sql_warns_of_a_table_read_live(capsys):
    confirm.check_sql(
        "WITH w AS (SELECT 1 AS k) SELECT u.__row, CASE WHEN r.k IS NULL THEN "
        "'C1' ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
        "LEFT JOIN kipptaf_marts.dim_x AS r ON r.k = u.aid "
        "LEFT JOIN `teamster-332318`.`d`.`fact` AS f ON f.item = u.aid "
        "LEFT JOIN w ON w.k = 1",
        GRAIN,
        STUDENT,
    )

    out = capsys.readouterr().out
    assert "kipptaf_marts.dim_x" in out and "not as of the run" in out
    assert "fact" not in out and " w " not in out


def test_a_proof_classifies_value_differing_rows(duck, tmp_path, offline, monkeypatch):
    # Both sides hold every row; the dashboard's school differs for all 3.
    _tables(duck, fact_rows=[(1, "a", "Y", False, True), (2, "b", "Y", True, False),
                             (3, "c", "Y", False, False)])  # fmt: skip
    dash = "SELECT f.student, f.item, f.school FROM `teamster-332318.d.fact` AS f"
    both = pipeline.RowSides(
        cube=SIDES.cube,
        dashboard=AsOf(dash, frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=SIDES.columns,
    )
    values = RowSpec(grain=ROWS.grain, values=[ColumnPair("school", "abbreviation")])
    comparison = Comparison(id="mastery", measure="pct", dims=[], rows=values)
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[comparison])
    group = Group("mastery", (), "value_differs", 3, 3)
    run = _run([group])
    items = [triage._as_json(s) for s in triage.suggest(cfg, run, {}, traces={})]
    directory = tmp_path / "proofs" / "v"
    directory.mkdir(parents=True)
    path = confirm.proof_path(directory, "mastery", "value_differs")
    path.write_text(confirm.compose({"C1": ("dashboard", "the sheet reads another school")},
        "SELECT u.__row, CASE WHEN u.side = 'both' THEN 'C1' ELSE 'UNEXPLAINED' END "
        "AS cause FROM {unmatched} AS u"))  # fmt: skip

    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: both)

    _stored(run, items, directory, Wh(duck), cfg)

    (item,) = items
    assert item["suggestion"] == "cause", item["evidence"]
    assert item["cause"][0]["n_rows"] == 3


def test_compose_opts_out_of_banned_syntax_only_when_the_proof_uses_it():
    causes = {"C1": ("dashboard", "WPP modules")}
    plain = confirm.compose(causes, "select __row, 'C1' as cause from {unmatched}")
    picked = confirm.compose(causes, "select * from {unmatched} qualify true")
    assert "sql-banned-syntax" not in plain
    assert "sql-banned-syntax" in picked
    assert confirm.split_block(picked)[0] == causes
