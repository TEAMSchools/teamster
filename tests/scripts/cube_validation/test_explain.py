import contextlib
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import (
    compare,
    coverage,
    explain,
    explain_progress,
    formula,
    pipeline,
    reconcile,
    results,
    saved,
    sort,
    trace,
)
from cube_validation.bq import CostCapError

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
from cube_validation.reconcile import CellDiff, Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo, utc_literal
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
EXPLANATION = """
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
        # Each saved table's labels, by table id (`_save`).
        self.labels: dict[str, dict] = {}

    def estimate(self, sql):
        return 0.01

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql, timeout_s=None):
        self.ran.append((sql, timeout_s))
        return self.duck.rows(sql)

    def table(self, dataset, name):
        return TableInfo("TABLE")

    @contextlib.contextmanager
    def budget(self, max_usd):
        yield

    def saved_labels(self, table_id):
        return self.labels.get(table_id)


def _saved_wh(duck, run, cfg=CFG):
    """A warehouse whose scratch dataset holds the run's saved rows."""
    wh = Wh(duck)
    _save(duck, wh, run, cfg)
    return wh


def _save(duck, wh, run, cfg=CFG):
    """What `compare` leaves behind: each comparison's saved rows and labels."""
    for c in cfg.comparisons:
        if c.rows is None:
            continue
        table = saved.table_id(cfg.view, run.moment_of(c.id), c.id)
        try:  # the rows the test's `row_sides` rebuilds, as `compare` reconciled them
            sides = pipeline.row_sides(
                cfg, c, wh=wh, cube=None, build=run.moment_of(c.id), schools=set(),
                fingerprints={},
            )  # fmt: skip
        except explain.CubeError:  # a test whose rebuild fails: the default rows
            sides = SIDES
        duck.rows("DROP TABLE IF EXISTS __joined")
        for statement in compare.save_script(
            cfg, c, sides, saved.table_sql(table), None
        ):
            duck.rows(statement)
        wh.labels[table] = saved.labels(
            cfg.view,
            run.moment_of(c.id),
            c.id,
            pipeline.checkpoint_fingerprint(c, run.fingerprints.get(c.id, {})),
        )


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
    return [sort._as_json(s) for s in sort.suggest(CFG, run, {}, traces={})]


def _explanation(tmp_path, body=EXPLANATION, causes=None):
    directory = tmp_path / "explanations" / "v"
    directory.mkdir(parents=True, exist_ok=True)
    path = explain.explanation_path(directory, "mastery", "cube_only")
    path.write_text(explain.compose(CAUSES if causes is None else causes, body))
    return directory, path


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(explain, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: SIDES)


def _by_id(items):
    return {i["id"]: i for i in items}


def _stored(run, items, directory, wh, cfg=CFG):
    """What every `sort` does: run the stored explanations, then sort by them."""
    _save(wh.duck, wh, run, cfg)
    ran = explain.run_stored(cfg, run, directory, wh=wh, cube=None)
    explain.apply_runs(run, items, ran, cfg)


def _reprove(duck, tmp_path, run, body=EXPLANATION, causes=None, wh=None):
    items = _items(run)
    directory, _ = _explanation(tmp_path, body, causes)
    _stored(run, items, directory, wh or Wh(duck))
    return items


# --- a stored explanation, re-run by every sort -------------------------------


def test_a_proof_reads_the_saved_rows_not_both_sides(duck, tmp_path, offline):
    _tables(duck)
    wh = Wh(duck)

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=wh)

    ((sql, _),) = wh.ran
    assert item["suggestion"] == "cause"
    assert "`cube_validation_scratch`" in sql and "cube_t" not in sql


def test_a_proof_refuses_when_its_saved_rows_are_gone(duck, tmp_path, offline, capsys):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    items = _items(run)
    directory, _ = _explanation(tmp_path)

    ran = explain.run_stored(CFG, run, directory, wh=wh, cube=None)
    explain.apply_runs(run, items, ran, CFG)

    assert items[0]["suggestion"] == "investigate" and wh.ran == []
    assert "no saved rows for the run of" in capsys.readouterr().out


def test_a_proof_refuses_saved_rows_labelled_for_another_run(
    duck, tmp_path, offline, capsys
):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    (table,) = wh.labels
    wh.labels[table] = {**wh.labels[table], "fingerprint": "0" * 32}
    items = _items(run)
    directory, _ = _explanation(tmp_path)

    ran = explain.run_stored(CFG, run, directory, wh=wh, cube=None)
    explain.apply_runs(run, items, ran, CFG)

    assert wh.ran == []
    assert "labelled for another run or SQL (fingerprint)" in capsys.readouterr().out


def test_a_missing_table_past_time_travel_says_to_start_a_new_run(
    duck, tmp_path, offline, monkeypatch
):
    monkeypatch.setattr(explain, "utcnow", lambda: BUILD.end + timedelta(days=9))

    with pytest.raises(
        pipeline.Refusal, match="Run `compare --comparison mastery` at a new moment"
    ):
        explain.require_saved(Wh(duck), CFG, _run([_group(3)]), COMPARISON)


def test_a_missing_table_within_time_travel_says_to_save_it_again(
    duck, tmp_path, offline, monkeypatch
):
    monkeypatch.setattr(explain, "utcnow", lambda: BUILD.end + timedelta(hours=2))

    with pytest.raises(
        pipeline.Refusal,
        match=r"Run `compare --comparison mastery --moment '[^']+'` to save them again",
    ):
        explain.require_saved(Wh(duck), CFG, _run([_group(3)]), COMPARISON)


def test_an_explanation_reads_its_own_comparison_s_moment(duck, tmp_path, offline):
    # The run composed this comparison's result from an earlier compare.
    _tables(duck)
    later = Build(BUILD.start + timedelta(days=2), BUILD.end + timedelta(days=2), "j2")
    run = replace(_run([_group(3)]), moment=later, moments={"mastery": BUILD})
    wh = Wh(duck)

    (item,) = _reprove(duck, tmp_path, run, wh=wh)

    ((sql, _),) = wh.ran
    assert item["suggestion"] == "cause"
    assert saved.table_id("v", BUILD, "mastery").rsplit(".", 1)[1] in sql
    assert saved.table_id("v", later, "mastery").rsplit(".", 1)[1] not in sql
    assert utc_literal(BUILD.start) in sql and utc_literal(later.start) not in sql


def test_a_stored_proof_proves_every_row_of_an_item(duck, tmp_path, offline):
    _tables(duck)
    wh = Wh(duck)

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=wh)

    assert item["suggestion"] == "cause"
    assert item["cause"] == [
        {"side": "dashboard", "step": "C1", "label": CAUSES["C1"][1], "n_rows": 2},
        {"side": "dashboard", "step": "C2", "label": CAUSES["C2"][1], "n_rows": 1},
    ]
    path = tmp_path / "explanations" / "v" / "mastery__cube_only.sql"
    # Recorded relative to the validation file's directory.
    assert item["proof"]["path"] == "explanations/v/mastery__cube_only.sql"
    assert item["proof"]["kind"] == "query"
    assert item["proof"]["fingerprint"] == explain.file_fingerprint(path)
    # The explanation reads its own tables as of the run, under the trace's limit.
    ((sql, timeout),) = wh.ran
    assert "`teamster-332318.d.fact` AS f FOR SYSTEM_TIME AS OF" in sql
    assert timeout == trace.TIMEOUT_S


def test_new_rows_the_proof_does_not_cover_reopen_the_item(duck, tmp_path, offline):
    # A new run: row (4, d) has no fact row, so the explanation calls it UNEXPLAINED.
    _tables(duck, [(1, "a", "X"), (2, "b", "X"), (4, "d", "X")], FACT_ROWS[:2])

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]))

    assert item["suggestion"] == "investigate" and item["cause"] is None
    assert (
        item["evidence"][0]
        == "explanation mastery__cube_only.sql leaves 1 rows unexplained"
    )
    assert item["evidence_posted"][0] == (
        "explanation mastery__cube_only.sql does not explain every row"
    )


def test_a_partly_explained_item_stays_while_a_full_one_moves(
    duck, tmp_path, offline, monkeypatch
):
    # (3, c) passes both filters on the fact, so the explanation leaves it UNEXPLAINED.
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
        "explanation mastery__cube_only.sql leaves 1 rows unexplained"
    )


def test_a_proof_that_cannot_run_notes_why_and_moves_nothing(duck, tmp_path, offline):
    _tables(duck)

    class Failing(Wh):
        def rows(self, sql, timeout_s=None):
            raise BadRequest("value 12345 bad", errors=[{"reason": "invalidQuery"}])

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=Failing(duck))

    assert item["suggestion"] == "investigate"
    assert item["evidence"][0].startswith("explanation mastery__cube_only.sql not run:")
    assert "invalidQuery" in item["evidence"][0] and "12345" not in item["evidence"][0]
    assert item["evidence_posted"][0] == (
        "explanation mastery__cube_only.sql not run; see the terminal"
    )


def test_a_refused_proof_keeps_bigquerys_message_locally(duck, tmp_path, offline):
    _tables(duck)
    said = (
        "Conflicting 'FOR SYSTEM_TIME AS OF' expressions found for table "
        "'teamster-332318.m.t': 2026-10-28 21:34:52.982 UTC vs. 2026-10-28 "
        "21:34:41.073 UTC; for table m.t 12345"
    )

    class Failing(Wh):
        def rows(self, sql, timeout_s=None):
            raise BadRequest(said, errors=[{"reason": "invalidQuery"}])

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=Failing(duck))

    assert "Conflicting 'FOR SYSTEM_TIME AS OF'" in item["evidence"][0]
    assert "for table m.t <n>" in item["evidence"][0]
    assert (
        "'teamster-332318.m.t': 2026-10-28 21:34:52.982 UTC vs." in item["evidence"][0]
    )
    assert item["evidence_posted"][0] == (
        "explanation mastery__cube_only.sql not run; see the terminal"
    )


# An explanation reading the table only the Cube side reads.
CUBE_TABLE_EXPLANATION = EXPLANATION.replace(
    "AND f.item = u.aid",
    "AND f.item = u.aid\nLEFT JOIN `teamster-332318`.`m`.`cube_t` AS c ON c.lea = u.lea",
)


def test_a_proof_reads_a_table_the_cube_side_reads_at_the_build_end(
    duck, tmp_path, offline, monkeypatch
):
    _tables(duck)
    checked = []
    monkeypatch.setattr(
        trace, "changed_between", lambda wh, t, a, b: checked.append(list(t)) or []
    )
    wh = Wh(duck)

    (item,) = _reprove(
        duck, tmp_path, _run([_group(3)]), body=CUBE_TABLE_EXPLANATION, wh=wh
    )

    assert item["suggestion"] == "cause"
    assert checked == [["m.cube_t"]]
    sql = wh.ran[-1][0]
    at = "FOR SYSTEM_TIME AS OF TIMESTAMP"
    assert f"`teamster-332318.m.cube_t` AS c {at} '{utc_literal(BUILD.end)}'" in sql
    # The dashboard's table stays at the build start.
    assert f"`teamster-332318.d.fact` AS f {at} '{utc_literal(BUILD.start)}'" in sql


def test_a_proof_refuses_a_cube_side_table_that_changed_during_the_build(
    duck, tmp_path, offline, monkeypatch
):
    _tables(duck)
    monkeypatch.setattr(trace, "changed_between", lambda wh, t, a, b: list(t))

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), body=CUBE_TABLE_EXPLANATION)

    assert item["suggestion"] == "investigate"
    assert (
        "cannot read in mastery__cube_only.sql m.cube_t: it changed during the build"
        in item["evidence"][0]
    )


def test_a_cube_error_notes_the_items_and_a_comparison_is_rebuilt_once(
    duck, tmp_path, monkeypatch
):
    monkeypatch.setattr(explain, "network_schools", lambda wh: set())
    _tables(duck)
    calls = []

    def failing(*a, **k):
        calls.append(1)
        raise explain.CubeError("Cube answered 502")

    monkeypatch.setattr(pipeline, "row_sides", failing)
    run = _run([_group(3), _group(2, "Y", "dashboard_only")])
    items = _items(run)
    directory, _ = _explanation(tmp_path)
    (directory / "mastery__dashboard_only.sql").write_text(
        explain.compose(CAUSES, EXPLANATION)
    )
    wh = Wh(duck)
    _save(duck, wh, run)
    calls.clear()

    explain.apply_runs(
        run, items, explain.run_stored(CFG, run, directory, wh=wh, cube=None), CFG
    )

    assert {i["suggestion"] for i in items} == {"investigate"}
    assert all("not run: Cube answered 502" in i["evidence"][0] for i in items)
    # A failed rebuild is not cached, so each explanation tries once.
    assert len(calls) == 2


def test_both_buckets_of_a_comparison_share_one_rebuild(duck, tmp_path, offline,
                                                         monkeypatch):  # fmt: skip
    _tables(duck)
    calls = []
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: calls.append(1) or SIDES)
    run = _run([_group(3), _group(2, "Y", "dashboard_only")])
    directory, _ = _explanation(tmp_path)
    (directory / "mastery__dashboard_only.sql").write_text(
        explain.compose(CAUSES, EXPLANATION)
    )

    wh = Wh(duck)
    _save(duck, wh, run)
    calls.clear()

    explain.run_stored(CFG, run, directory, wh=wh, cube=None)

    assert len(calls) == 1


def test_confirm_refreshes_the_decision_marks(duck, tmp_path, monkeypatch, offline):
    _tables(duck)
    run = _run([_group(3)])
    run.fingerprints = {"mastery": {"cube": "c", "dashboard": "d"}}
    triage_json = _saved(tmp_path, monkeypatch, run)
    fp = explain.fingerprint(CAUSES, EXPLANATION)
    decided = [
        Decision(f"d{i}", "mastery", "deliberate", "r",
                 cause={"side": side, "label": words},
                 fingerprints={"cube": "c", "dashboard": "d", "explanation": fp})
        for i, (side, words) in enumerate(CAUSES.values())
    ]  # fmt: skip
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON],
                     decisions=decided)  # fmt: skip
    draft = tmp_path / "draft.sql"
    draft.write_text(EXPLANATION)

    explain.explain(
        cfg,
        tmp_path / "validation" / "v.yml",
        wh=_saved_wh(duck, run, cfg),
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
    body = EXPLANATION.replace("'C2'", "'C9'")

    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), body=body)

    assert "no --cause for C9" in item["evidence"][0]


# --- the checks before an explanation runs -----------------------------------


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
        explain.check_sql(sql, GRAIN, STUDENT)

    for value in ("1234567", "123456", "person@", "S1"):
        assert value not in str(caught.value)


def test_check_sql_lets_a_model_predicate_be_copied_literally():
    assert explain.check_sql(EXPLANATION, GRAIN, STUDENT) == {"UNEXPLAINED", "C1", "C2"}
    # A grain column that names no one may meet a literal; the student column
    # may drive a condition through a join.
    explain.check_sql(
        "SELECT u.__row, CASE WHEN u.response_type = 'overall' THEN 'C1' "
        "WHEN NOT EXISTS (SELECT 1 FROM w WHERE w.student = u.lea) THEN 'C4' "
        "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u",
        GRAIN,
        STUDENT,
    )


def test_check_sql_lets_a_literal_meet_an_id_that_names_no_one():
    # DDI's C3 names one assessment by its id.
    assert explain.check_sql(
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
        "r.student_number = 7",
        "r.employee_number = 7",
        "r.state_studentnumber = 7",
        "r.lea_student_identifier = 7",
        "r.teacher_number = 7",
        "r.home_phone_number = 7",
        "r.guardian_phone_number = 7",
        "r.payroll_file_number = 7",
        "r.worker_number = 7",
        "r.badge_number = 7",
    ],
)
def test_check_sql_refuses_a_literal_on_a_column_that_names_a_person(where):
    with pytest.raises(pipeline.Refusal, match="identifying column with a literal"):
        explain.check_sql(
            f"SELECT u.__row, 'C1' AS cause FROM {{unmatched}} AS u, r WHERE {where}",
            GRAIN,
            STUDENT,
        )


@pytest.mark.parametrize(
    "where",
    [
        "r.performance_band_label_number = 3",
        "r.module_number = 2",
        "r.grade_level_number IN (5, 6)",
        "r.section_number = 4",
        "r.week_number = 12",
    ],
)
def test_check_sql_lets_a_literal_meet_a_category_number(where):
    assert explain.check_sql(
        f"SELECT u.__row, CASE WHEN {where} THEN 'C1' "
        "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
        "LEFT JOIN `teamster-332318`.`ds`.`r` AS r ON r.student = u.lea",
        GRAIN,
        STUDENT,
    ) == {"C1", "UNEXPLAINED"}


@pytest.mark.parametrize(
    ("flag", "why"),
    [
        ("C1:dashboard words", "<bucket>=<side>"),
        ("C1=sheet:words", "side must be"),
        ("UNEXPLAINED=cube:words", "not be UNEXPLAINED"),
        ("C1=cube:student 1234567", "ID-like"),
        ("C1=cube:student 1234 5678", "ID-like"),
        ("C1=cube:student 123 456 789 012", "ID-like"),
    ],
)
def test_a_cause_flag_is_checked(flag, why):
    with pytest.raises(pipeline.Refusal, match=why) as caught:
        explain.parse_cause_flag(flag)

    assert "1234567" not in str(caught.value)


@pytest.mark.parametrize(
    "words",
    [
        "grades 9 10 11 12 differ",
        "school year 2025 2026 rolled over",
        "grades 5 6 7 8",
        "school years 2024 2025 2026",
    ],
)
def test_a_cause_flag_allows_a_grade_list_and_a_school_year(words):
    assert explain.parse_cause_flag(f"C1=cube:{words}")[2] == words


# --- the explanation file ----------------------------------------------------


def test_a_proof_file_opts_out_of_trunk_and_keeps_its_bucket_map():
    text = explain.compose(CAUSES, EXPLANATION)

    assert text.startswith(
        "-- trunk-ignore-all(sqlfluff)\n-- fmt: off\n"
        f"-- cause C1 = dashboard: {CAUSES['C1'][1]}\n"
    )
    assert explain.split_explanation(text) == (CAUSES, {}, EXPLANATION.strip())


def test_a_formatting_only_edit_keeps_the_fingerprint(tmp_path):
    _, path = _explanation(tmp_path)
    before = explain.file_fingerprint(path)

    path.write_text(
        path.read_text().replace("WHEN NOT f.ok1", "when   not F.OK1") + "-- a note\n"
    )
    assert explain.file_fingerprint(path) == before

    path.write_text(path.read_text().replace("NOT f.ok2", "f.ok2"))
    assert explain.file_fingerprint(path) != before


# --- the command -------------------------------------------------------------------


def _saved(tmp_path, monkeypatch, run):
    run_json = tmp_path / "cache" / "v" / "m" / "run.json"
    run_json.parent.mkdir(parents=True)
    monkeypatch.setattr(results, "latest_run", lambda cfg, root: (run, run_json))
    path = run_json.parent / "triage.json"
    path.write_text(
        json.dumps(
            {
                "view": "v",
                "moment": sort._moment(run),
                "decisions_fingerprint": "",
                "open": sort.open_keys(run),
                "items": _items(run),
                "formulas_not_compared": {},
            }
        )
    )
    return path


def _confirm(duck, tmp_path, causes, **kw):
    draft = tmp_path / "draft.sql"
    draft.write_text(EXPLANATION)
    wh = Wh(duck)
    _save(duck, wh, results.latest_run(CFG, tmp_path)[0])
    explain.explain(
        CFG,
        tmp_path / "validation" / "v.yml",
        wh=wh,
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

    stored = tmp_path / "validation" / "explanations" / "v" / "mastery__cube_only.sql"
    assert stored.read_text().startswith("-- trunk-ignore-all(sqlfluff)\n")
    assert explain.read_explanation(stored).causes == CAUSES
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
_SIDE = {"dashboard_only": 2}


def _placed(n, school="X", bucket="cube_only", cut="{}"):
    """A group whose rows sit under `cut` on the side its bucket holds."""
    rows = [cut, 0, 0]
    rows[_SIDE.get(bucket, 1)] = n
    return replace(_group(n, school, bucket), cut_rows=(tuple(rows),))


def _group_ids(run):
    return [i.id for i in sort.open_items(run) if i.kind == "group"]


def _cells(run=None, cfg=CFG, proven: bool | list = True, left=None):
    """Link the run's cell set over its triage items, as every triage does."""
    run = run or _run([_placed(3)], **CELLS_RUN)
    items = _items(run)
    chosen = proven if isinstance(proven, list) else []
    for item in items:
        if item["kind"] == "group" and (proven is True or item["id"] in chosen):
            item.update(suggestion="cause", cause=[{"side": "dashboard",
                        "step": "C1", "label": "fails ok1", "n_rows": 3}])  # fmt: skip
    explain.link_cells(run, items, "mastery", cfg, left)
    return _by_id(items)["mastery:cells"]


def test_cells_confirm_when_every_differing_cell_lies_in_proven_groups():
    cells = _cells()

    assert cells["suggestion"] == "cause"
    assert cells["cause"] == [
        {"side": "dashboard", "step": "C1", "label": "fails ok1", "n_rows": 3}
    ]
    (group_id,) = _group_ids(_run([_placed(3)]))
    assert cells["proof"] == {"kind": "cells", "groups": [group_id], "closed": []}


def test_covered_cells_keep_the_formula_check_s_not_compared_lines():
    run = _run([_placed(3)], **CELLS_RUN)
    items = _items(run)
    for item in items:
        if item["kind"] == "group":
            item.update(suggestion="cause", cause=[{"side": "dashboard",
                        "step": "C1", "label": "fails ok1", "n_rows": 3}])  # fmt: skip
    cells = _by_id(items)["mastery:cells"]
    # As `formula.label` prepends them, exact locally and masked when posted.
    local = f"{formula.NOT_COMPARED}: a reason (3 cells closed by coverage only)"
    posted = f"{formula.NOT_COMPARED}: a reason (<10 cells closed by coverage only)"
    cells["evidence"] = [local, "an earlier line"]
    cells["evidence_posted"] = [posted, "an earlier line"]

    explain.link_cells(run, items, "mastery", CFG)

    assert cells["suggestion"] == "cause"
    assert cells["evidence"][0] == local
    assert cells["evidence_posted"][0] == posted
    assert cells["evidence"][1].startswith(explain._COVERED)
    assert "an earlier line" not in cells["evidence"]


def test_cells_stay_open_with_the_count_left_outside_proven_groups():
    cells = _cells(proven=False)

    assert cells["suggestion"] == "investigate" and cells["proof"] is None
    assert cells["evidence"][0] == "1 of 1 differing cells are not covered"
    # The posted copy masks both counts.
    assert cells["evidence_posted"][0] == "<10 of <10 differing cells are not covered"


def test_cells_link_only_to_groups_under_their_cut():
    by_school = Comparison(
        id="mastery",
        measure="pct",
        dims=[ColumnPair("school", "abbreviation")],
        rows=ROWS,
        filters={"School": ColumnPair("school", "abbreviation")},
    )
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[by_school])
    # The cell sits under the cut School = Y; the only explained group has rows
    # under School = X alone.
    x, y = '{"School": "X"}', '{"School": "Y"}'
    proven = replace(_group(3), cut_rows=((x, 3, 0), (y, 0, 0)))
    run = _run(
        [proven],
        cells=CELLS_RUN["cells"],
        diff_cells=[{**CELLS_RUN["diff_cells"][0], "cut": y}],
    )
    left: dict = {}

    cells = _cells(run=run, cfg=cfg, left=left)

    assert cells["suggestion"] == "investigate"
    ((only,),) = left.values()
    assert only["why"] == "no unmatched row lies in it" and only["groups"] == []


def test_a_cell_the_formula_item_holds_leaves_the_cell_set():
    # Cell X lies in an explained group. Cell Y holds no unmatched row, so the
    # run filed it in the comparison's formula item, not in the cell set.
    cell = {**CELLS_RUN["diff_cells"][0], "kind": "cells"}
    y = {**cell, "key": "abbreviation=Y", "dims": [["abbreviation", "Y"]],
         "kind": "formula"}  # fmt: skip
    formula = CellDiff("mastery", {"differs": 1}, kind="formula")
    run = _run([_placed(3)], cells=[*CELLS_RUN["cells"], formula], diff_cells=[cell, y])
    left: dict = {}

    cells = _cells(run=run, left=left)

    assert cells["suggestion"] == "cause" and left == {}
    assert cells["evidence"][0].endswith(_group_ids(run)[0])


def test_a_cell_with_no_row_stays_open_when_no_formula_item_holds_it():
    # A run saved before cells carried a kind: each reads as the cell set's,
    # even with a formula difference beside it.
    cell = CELLS_RUN["diff_cells"][0]
    y = {**cell, "key": "abbreviation=Y", "dims": [["abbreviation", "Y"]]}
    formula = CellDiff("mastery", {"differs": 1}, kind="formula")
    run = _run([_placed(3)], [*CELLS_RUN["cells"], formula], [cell, y])
    left: dict = {}

    cells = _cells(run=run, left=left)

    assert cells["suggestion"] == "investigate"
    ((only,),) = left.values()
    assert only["cell"]["key"] == "abbreviation=Y"
    assert only["why"] == "no unmatched row lies in it"


def test_a_cell_covered_by_a_decided_group_and_a_proven_one_closes():
    quiet = _placed(4, bucket="dashboard_only")
    decision = Decision("closed-x", "mastery", "fix_cube", "r",
                        group={"column": "abbreviation", "values": ["X"]})  # fmt: skip
    run = _run([_placed(3)], **CELLS_RUN)
    run.applied.quiet.append((decision, quiet))

    cells = _cells(run=run)

    assert cells["suggestion"] == "cause"
    assert cells["proof"] == {
        "kind": "cells",
        "groups": _group_ids(run),
        "closed": [sort._open_key(quiet)],
    }
    assert {"side": "both", "step": "decision", "label": "closed by closed-x",
            "n_rows": 4} in cells["cause"]  # fmt: skip


def test_a_cell_covered_only_by_decided_groups_still_has_a_cause():
    decision = Decision("closed-x", "mastery", "fix_cube", "r",
                        group={"column": "abbreviation", "values": ["X"]})  # fmt: skip
    run = _run([], **CELLS_RUN)
    run.applied.quiet.append((decision, _placed(3)))

    cells = _cells(run=run)

    assert cells["suggestion"] == "cause"
    assert cells["cause"] == [
        {"side": "both", "step": "decision", "label": "closed by closed-x",
         "n_rows": 3}
    ]  # fmt: skip
    assert cells["proof"]["groups"] == []


def test_a_cell_with_one_unproven_group_stays_in_investigate():
    # Cell X holds an explained group and an unexplained one; cell Y an explained one.
    cell = CELLS_RUN["diff_cells"][0]
    run = _run(
        [_placed(3), _placed(2, bucket="dashboard_only"), _placed(5, "Y")],
        cells=CELLS_RUN["cells"],
        diff_cells=[cell, {**cell, "key": "abbreviation=Y",
                           "dims": [["abbreviation", "Y"]]}],
    )  # fmt: skip
    # The unexplained group is cell X's dashboard_only one, the 2nd of its id.
    proven = [i for i in _group_ids(run) if not i.endswith("#2")]
    left: dict = {}

    cells = _cells(run=run, proven=proven, left=left)

    assert cells["suggestion"] == "investigate"
    assert cells["evidence"][0] == "1 of 2 differing cells are not covered"
    ((only,),) = left.values()
    assert only["cell"]["key"] == "abbreviation=X"
    assert only["why"] == "1 of its 2 groups are not in cause"


def test_a_cell_whose_groups_lack_rows_per_cut_stays_open_and_says_why():
    # A run saved before rows per cut were kept: its groups cannot be placed.
    left: dict = {}

    cells = _cells(run=_run([_group(3)], **CELLS_RUN), left=left)

    assert cells["suggestion"] == "investigate"
    ((only,),) = left.values()
    assert only["why"] == f"cannot be placed: {coverage.NOT_RECORDED}"


def test_a_cell_on_a_grain_dim_cannot_be_covered():
    on_grain = replace(COMPARISON, dims=[ColumnPair("student", "lea")])
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[on_grain])
    run = _run(
        [replace(_placed(3), dims=())],
        cells=CELLS_RUN["cells"],
        diff_cells=[{**CELLS_RUN["diff_cells"][0], "dims": [["lea", "1"]]}],
    )
    left: dict = {}

    cells = _cells(run=run, cfg=cfg, left=left)

    assert cells["suggestion"] == "investigate"
    ((only,),) = left.values()
    assert only["why"] == ("cannot be placed: its dims lea are part of the row grain")


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
    directory, proof = _explanation(tmp_path)
    saved = json.loads(path.read_text())
    _stored(run, saved["items"], directory, Wh(duck))
    path.write_text(json.dumps(saved))

    assert sort.checked_sort(run, path.parent / "run.json", base=tmp_path)["items"]

    # Formatting is no change; a changed predicate is.
    proof.write_text(
        proof.read_text().replace("SELECT u.__row", "select   U.__ROW")
        + "\n-- reviewed\n"
    )
    assert sort.checked_sort(run, path.parent / "run.json", base=tmp_path)["items"]
    proof.write_text(proof.read_text().replace("NOT f.ok2", "f.ok2"))
    with pytest.raises(
        pipeline.Refusal, match="explanation file changed since the sort"
    ):
        sort.checked_sort(run, path.parent / "run.json", base=tmp_path)


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
    with pytest.raises(pipeline.Refusal, match="the explanation's cause"):
        explain.check_sql(
            f"SELECT u.__row, {cause} AS cause FROM {{unmatched}} AS u", GRAIN, STUDENT
        )


def test_check_sql_refuses_a_cause_carried_from_a_cte():
    with pytest.raises(pipeline.Refusal, match="quoted cause name"):
        explain.check_sql(
            "WITH c AS (SELECT u.__row, CASE WHEN TRUE THEN 'C1' ELSE 'C9' END "
            "AS cause FROM {unmatched} AS u) SELECT u.__row, CASE WHEN TRUE THEN "
            "c.cause ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
            "JOIN c ON c.__row = u.__row",
            GRAIN,
            STUDENT,
        )


def test_check_sql_warns_of_a_table_read_live(capsys):
    explain.check_sql(
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


def test_a_proof_counts_each_cause_s_students_per_cell_and_cut(duck, tmp_path, offline):
    _tables(duck)
    wh = Wh(duck)
    run = _run([_group(3)])
    _save(duck, wh, run)
    proof = explain.Explanation(
        tmp_path / "mastery__cube_only.sql", "mastery", "cube_only",
        CAUSES, EXPLANATION, {},
    )  # fmt: skip
    students: list[dict] = []

    found = explain.run_explanation(
        wh, COMPARISON, SIDES, proof, [("G1", _group(3))], BUILD, {},
        students, table=explain.require_saved(wh, CFG, run, COMPARISON),
    )  # fmt: skip

    assert found["G1"].counts == {"C1": 2, "C2": 1}
    (cut,) = [label for label, _, _ in pipeline.cut_flags(COMPARISON)]
    assert sorted(students, key=lambda e: e["cause"]) == [
        {"cause": sort.cause_key(*CAUSES["C1"]), "cut": cut,
         "dims": [["abbreviation", "X"]], "n": 2, "bucket": "cube_only"},
        {"cause": sort.cause_key(*CAUSES["C2"]), "cut": cut,
         "dims": [["abbreviation", "X"]], "n": 1, "bucket": "cube_only"},
    ]  # fmt: skip


BY_GRADE = replace(
    COMPARISON,
    filters={"Grade": ColumnPair("grade", "grade")},
    cuts=[{"Grade": "5"}, {"Grade": "6"}],
)


def _prove_saved(duck, bucket, rows, items):
    """Run an explanation that gives every row C1 over hand-made saved rows of
    BY_GRADE: (row, student, Cube's school, the dashboard's or None, moved,
    Cube's and the dashboard's flags for Grade 5 and Grade 6)."""
    duck.table(
        "saved_t",
        "bucket VARCHAR, __row BIGINT, abbreviation VARCHAR, __moved BOOLEAN, "
        "__d_abbreviation VARCHAR, __gc0 BIGINT, __gc1 VARCHAR, __gd0 BIGINT, "
        "__gd1 VARCHAR, __rn BIGINT, __ck0 BOOLEAN, __dk0 BOOLEAN, "
        "__ck1 BOOLEAN, __dk1 BOOLEAN",
        [(bucket, row, school, moved, dash, student, "a", student, "a", 1, *flags)
         for row, student, school, dash, moved, flags in rows],
    )  # fmt: skip
    proof = explain.Explanation(
        Path("p.sql"), "mastery", bucket,
        {"C1": ("dashboard", "the dashboard files it elsewhere")},
        "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u", {},
    )  # fmt: skip
    ctes, select = explain.unmatched_sql(BY_GRADE, bucket, items, "saved_t")
    rows = duck.rows(
        explain.explanation_query(
            ctes, select, proof.body, {"C1"},
            explain._student_count(BY_GRADE, bucket),
        )
    )  # fmt: skip
    counts = {r["item_key"]: r["n"] for r in rows if r["__kind"] == "count"}
    return counts, explain.cause_students(rows, proof, BY_GRADE)


def test_a_row_each_side_files_under_another_cut_counts_in_each_side_s_cell(duck):
    # Cube files student 1 under Grade 5, the dashboard under 6.
    group = Group("mastery", (("abbreviation", "X"), ("d:abbreviation", "X")),
                  "dims_differ", 1, 1)  # fmt: skip

    _, found = _prove_saved(
        duck, "dims_differ", [(7, 1, "X", "X", True, (True, False, False, True))],
        [("G1", group)],
    )  # fmt: skip

    grade_5, grade_6 = [label for label, _, _ in pipeline.cut_flags(BY_GRADE)]
    assert sorted((e["cut"], e["n"]) for e in found) == [(grade_5, 1), (grade_6, 1)]


def test_a_value_differing_row_in_another_cell_is_its_own_group_and_counts_twice(
    duck,
):
    # Student 1's value differs and the dashboard files it under school Y;
    # student 2's value differs in the same cell on both sides.
    same = Group("mastery", (("abbreviation", "X"),), "value_differs", 1, 1)
    moved = Group("mastery", (("abbreviation", "X"), ("d:abbreviation", "Y")),
                  "value_differs", 1, 1)  # fmt: skip
    in_5 = (True, True, False, False)

    counts, found = _prove_saved(
        duck, "value_differs",
        [(7, 1, "X", "Y", True, in_5), (8, 2, "X", None, None, in_5)],
        # The group of the same cell first: a moved row must not land in it.
        [("SAME", same), ("MOVED", moved)],
    )  # fmt: skip

    assert counts == {"SAME": 1, "MOVED": 1}
    grade_5, _ = [label for label, _, _ in pipeline.cut_flags(BY_GRADE)]
    assert sorted((e["dims"][0][1], e["n"]) for e in found) == [("X", 2), ("Y", 1)]
    assert {e["cut"] for e in found} == {grade_5}


def test_a_row_with_no_cube_value_keys_to_its_group_and_counts_in_each_side_s_cell(
    duck,
):
    # Cube files student 1 under no school, the dashboard under Newark: the
    # saved row keys to the reconcile's group, and its students count in
    # Cube's own cell and the dashboard's.
    duck.table(
        "cube_t", "lea BIGINT, aid VARCHAR, abbreviation VARCHAR, grade VARCHAR",
        [(1, "a", None, "5")],
    )  # fmt: skip
    duck.table(
        "dash_t", "student BIGINT, item VARCHAR, school VARCHAR, grade VARCHAR",
        [(1, "a", "Newark", "5")],
    )  # fmt: skip
    sides = (
        "SELECT * FROM `teamster-332318.m.cube_t`",
        "SELECT * FROM `teamster-332318.d.dash_t`",
        BY_GRADE.rows,
        pipeline.group_dims(BY_GRADE),
    )
    cuts = [("c.grade = '5'", "d.grade = '5'"), ("c.grade = '6'", "d.grade = '6'")]
    labels = [label for label, _, _ in pipeline.cut_flags(BY_GRADE)]
    (group,) = reconcile.groups_from(
        "mastery",
        duck.script(reconcile.reconcile_script(*sides, cuts=cuts, table="counted_t")),
        labels,
    )
    duck.rows(
        "CREATE TABLE saved_t AS " + reconcile.unmatched_rows_sql(*sides, cuts=cuts)
    )
    proof = explain.Explanation(
        Path("p.sql"), "mastery", "dims_differ",
        {"C1": ("dashboard", "the dashboard files it elsewhere")},
        "SELECT u.__row, 'C1' AS cause FROM {unmatched} AS u", {},
    )  # fmt: skip
    ctes, select = explain.unmatched_sql(
        BY_GRADE, "dims_differ", [("G1", group)], "saved_t"
    )
    rows = duck.rows(
        explain.explanation_query(
            ctes, select, proof.body, {"C1"},
            explain._student_count(BY_GRADE, "dims_differ"),
        )
    )  # fmt: skip

    assert group.dims == (("abbreviation", ""), ("d:abbreviation", "Newark"))
    assert {r["item_key"]: r["n"] for r in rows if r["__kind"] == "count"} == {"G1": 1}
    found = explain.cause_students(rows, proof, BY_GRADE)
    assert sorted((pipeline.value_key(e["dims"][0][1]), e["n"]) for e in found) == [
        ("", 1),
        ("Newark", 1),
    ]


def test_kept_counts_take_the_larger_of_2_buckets_proofs_on_one_cell():
    loaded: dict = {}
    entry = {"cause": "c: x", "cut": "{}", "dims": [["a", "X"]], "n": 4}
    other = {**entry, "n": 12, "bucket": "value_differs"}

    explain.keep_students(loaded, "m", "cube_only", [{**entry, "bucket": "cube_only"}])
    explain.keep_students(loaded, "m", "value_differs", [other, {**other, "cut": "k"}])

    assert loaded["cause_students"]["m"] == [
        {**entry, "n": 12, "bucket": "cube_only"},
        {**other, "cut": "k"},
    ]


def test_a_re_run_proof_replaces_its_bucket_s_old_counts_even_when_smaller():
    entry = {"cause": "c: x", "cut": "{}", "dims": [["a", "X"]]}
    kept = {**entry, "n": 30, "bucket": "value_differs"}
    loaded = {"cause_students": {"m": [
        {**entry, "n": 14, "bucket": "cube_only"},
        {**entry, "cut": "k", "n": 20},  # saved before counts had a bucket
        kept,
    ]}}  # fmt: skip

    # The revised explanation splits the cause: 4 students keep its words.
    explain.keep_students(
        loaded, "m", "cube_only", [{**entry, "n": 4, "bucket": "cube_only"}]
    )

    assert loaded["cause_students"]["m"] == [{**kept}]
    # The other bucket's 30 is larger, so the cell keeps it; alone, 4 stays 4.
    del loaded["cause_students"]["m"][0]
    explain.keep_students(
        loaded, "m", "cube_only", [{**entry, "n": 4, "bucket": "cube_only"}]
    )
    assert loaded["cause_students"]["m"] == [{**entry, "n": 4, "bucket": "cube_only"}]


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
    items = [sort._as_json(s) for s in sort.suggest(cfg, run, {}, traces={})]
    directory = tmp_path / "explanations" / "v"
    directory.mkdir(parents=True)
    path = explain.explanation_path(directory, "mastery", "value_differs")
    path.write_text(explain.compose({"C1": ("dashboard", "the sheet reads another school")},
        "SELECT u.__row, CASE WHEN u.side = 'both' THEN 'C1' ELSE 'UNEXPLAINED' END "
        "AS cause FROM {unmatched} AS u"))  # fmt: skip

    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: both)

    _stored(run, items, directory, Wh(duck), cfg)

    (item,) = items
    assert item["suggestion"] == "cause", item["evidence"]
    assert item["cause"][0]["n_rows"] == 3


def test_compose_opts_out_of_banned_syntax_only_when_the_proof_uses_it():
    causes = {"C1": ("dashboard", "WPP modules")}
    plain = explain.compose(causes, "select __row, 'C1' as cause from {unmatched}")
    picked = explain.compose(causes, "select * from {unmatched} qualify true")
    assert "sql-banned-syntax" not in plain
    assert "sql-banned-syntax" in picked
    assert explain.split_explanation(picked)[0] == causes


# --- one explanation per row population --------------------------------------

# Same rows as COMPARISON, another measure: its groups are the same rows.
SIBLING = Comparison(
    id="mastery-b",
    measure="pct2",
    dims=[ColumnPair("school", "abbreviation")],
    rows=ROWS,
)
CFG2 = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON, SIBLING])


def test_comparisons_on_one_model_and_grain_share_an_explanation():
    other = replace(
        COMPARISON,
        id="b",
        dims=[ColumnPair("region", "region")],
        filters={"grade": ["5"]},
        defaults={"year": "2026"},
        scope=[{"school": ["X"]}],
        cuts=[{}],
        dashboard_columns={"x": "1"},
    )

    key = explain.explanation_key(COMPARISON)
    assert key is not None and explain.explanation_key(other) == key
    cfg = ViewConfig("v", "m.fct", [COMPARISON, other])
    assert explain.siblings(cfg, COMPARISON) == [other]


def test_another_grain_or_model_does_not_share():
    key = explain.explanation_key(COMPARISON)
    other_values = replace(
        COMPARISON, id="v", rows=replace(ROWS, values=[ColumnPair("x", "y")])
    )
    other_grain = replace(
        COMPARISON, id="g", rows=replace(ROWS, grain=[ColumnPair("student", "lea")])
    )
    other_model = replace(COMPARISON, id="m", dashboard_view="other")

    for c in (other_values, other_grain, other_model):
        assert explain.explanation_key(c) != key
    cfg = ViewConfig("v", "m.fct", [COMPARISON, other_values, other_grain, other_model])
    assert explain.siblings(cfg, COMPARISON) == []
    assert explain.explanation_key(replace(COMPARISON, rows=None)) is None


def test_a_shared_explanation_runs_on_each_comparison_s_own_rows(
    duck, tmp_path, monkeypatch, offline
):
    # The sibling reads another filter's rows: Cube also holds student 9, whom
    # the explanation's join to the dashboard cannot place.
    _tables(duck)
    duck.table(
        "cube_t2",
        "lea BIGINT, aid VARCHAR, abbreviation VARCHAR",
        [*CUBE_ROWS, (9, "z", "X")],
    )
    cube2 = CUBE.replace("cube_t", "cube_t2")
    sides2 = replace(
        SIDES,
        cube=AsOf(cube2, frozenset({"m.cube_t2"}), frozenset()),
        cube_rows_sql=cube2,
    )
    monkeypatch.setattr(
        pipeline,
        "row_sides",
        lambda cfg, c, **k: sides2 if c.id == "mastery-b" else SIDES,
    )
    sibling = replace(SIBLING, filters={"grade": ["5"]})
    cfg = ViewConfig("v", "m.fct", [COMPARISON, sibling])
    run = _run(
        [_group(3), Group("mastery-b", (("abbreviation", "X"),), "cube_only", 4, 4)]
    )
    directory, _ = _explanation(tmp_path)
    wh = Wh(duck)
    _save(duck, wh, run, cfg)

    ran = explain.run_stored(cfg, run, directory, wh=wh, cube=None)

    (own,) = [r for r in ran if r.items[0][1].comparison_id == "mastery"]
    (shared,) = [r for r in ran if r.items[0][1].comparison_id == "mastery-b"]
    assert all(o.explained for o in own.found.values())
    assert shared.found is not None
    assert [o.unexplained for o in shared.found.values()] == [1]
    assert not any(o.explained for o in shared.found.values())


def _items2(run):
    return [sort._as_json(s) for s in sort.suggest(CFG2, run, {}, traces={})]


def _sibling_run():
    sib = Group("mastery-b", (("abbreviation", "X"),), "cube_only", 3, 3)
    return _run([_group(3), sib])


def test_a_stored_proof_also_proves_a_comparison_with_the_same_rows(
    duck, tmp_path, offline
):
    _tables(duck)
    run = _sibling_run()
    items = _items2(run)
    directory, _ = _explanation(tmp_path)

    _stored(run, items, directory, Wh(duck), cfg=CFG2)

    by = {i["comparison"]: i for i in items}
    assert {i["suggestion"] for i in items} == {"cause"}
    assert by["mastery-b"]["proof"]["path"] == by["mastery"]["proof"]["path"]


def test_a_comparison_s_own_proof_wins_over_a_shared_one(duck, tmp_path, offline):
    _tables(duck)
    run = _sibling_run()
    items = _items2(run)
    directory, _ = _explanation(tmp_path)
    own = explain.explanation_path(directory, "mastery-b", "cube_only")
    own.write_text(explain.compose(CAUSES, EXPLANATION))
    wh = Wh(duck)

    _stored(run, items, directory, wh, cfg=CFG2)

    by = {i["comparison"]: i for i in items}
    assert by["mastery-b"]["proof"]["path"].endswith("mastery-b__cube_only.sql")
    assert len(wh.ran) == 2  # each comparison ran once, with its own file


def test_confirm_also_proves_the_comparisons_with_the_same_rows(
    duck, tmp_path, monkeypatch, offline, capsys
):
    _tables(duck)
    run = _sibling_run()
    path = _saved(tmp_path, monkeypatch, run)
    saved = json.loads(path.read_text())
    saved["items"] = _items2(run)
    path.write_text(json.dumps(saved))
    draft = tmp_path / "draft.sql"
    draft.write_text(EXPLANATION)

    explain.explain(
        CFG2,
        tmp_path / "validation" / "v.yml",
        wh=_saved_wh(duck, run, CFG2),
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        bucket="cube_only",
        sql=draft,
        causes=[f"{b}={side}:{words}" for b, (side, words) in CAUSES.items()],
    )

    items = json.loads(path.read_text())["items"]
    assert {i["suggestion"] for i in items} == {"cause"}
    assert "Also mastery-b: 1 of 1 items explained." in capsys.readouterr().out
    proofs = tmp_path / "validation" / "explanations" / "v"
    assert [p.name for p in proofs.iterdir()] == ["mastery__cube_only.sql"]


def test_a_sibling_s_own_failing_proof_shows_its_refusal(duck, tmp_path, offline):
    _tables(duck)
    run = _sibling_run()
    items = _items2(run)
    directory, _ = _explanation(tmp_path)
    explain.explanation_path(directory, "mastery-b", "cube_only").write_text(
        "not a proof"
    )

    _stored(run, items, directory, Wh(duck), cfg=CFG2)

    by = {i["comparison"]: i for i in items}
    assert by["mastery"]["suggestion"] == "cause"
    assert by["mastery-b"]["suggestion"] == "investigate"
    assert by["mastery-b"]["evidence"][0].startswith(
        "explanation mastery-b__cube_only.sql not run"
    )


# --- reproduce queries ---------------------------------------------------------------

REPRODUCE = """SELECT f.school, COUNT(*) AS n_rows
FROM `teamster-332318`.`d`.`fact` AS f
WHERE NOT f.ok1
GROUP BY f.school"""


def test_a_reproduce_query_rides_in_the_header_and_not_the_fingerprint():
    text = explain.compose(CAUSES, EXPLANATION, {"C1": REPRODUCE})

    assert "-- reproduce C1:\n--  SELECT f.school, COUNT(*) AS n_rows\n" in text
    causes, reproduce, body = explain.split_explanation(text)
    assert (causes, reproduce, body) == (CAUSES, {"C1": REPRODUCE}, EXPLANATION.strip())
    assert explain.fingerprint(causes, body) == explain.fingerprint(CAUSES, EXPLANATION)


def test_check_reproduce_takes_counts_by_a_column_that_names_no_one():
    explain.check_reproduce(REPRODUCE, {"student", "lea"}, {"student", "lea"})
    explain.check_reproduce(
        "WITH t AS (SELECT 1 AS x) SELECT COUNT(*) AS n FROM t", {"student"}
    )
    explain.check_reproduce(
        "SELECT school, COUNTIF(NOT ok1) AS n FROM d.fact GROUP BY 1", {"student"}
    )


@pytest.mark.parametrize(
    ("sql", "why"),
    [
        ("SELECT COUNT(*) FROM {unmatched}", "never {unmatched}"),
        (
            "SELECT COUNT(*) FROM `teamster-332318.d.fact` "
            "FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-28 00:00:00+00:00'",
            "FOR SYSTEM_TIME",
        ),
        ("SELECT * FROM d.fact", "selects \\*"),
        ("SELECT school, COUNT(*) FROM d.fact", "not in its GROUP BY"),
        (
            "SELECT student, COUNT(*) FROM d.fact GROUP BY student",
            "grain or identifying",
        ),
        ("SELECT COUNT(*) FROM d.fact GROUP BY student_number", "grain or identifying"),
        ("SELECT school FROM d.fact GROUP BY school", "no aggregate"),
        ("SELECT COUNT(*) OVER () AS n FROM d.fact", "window function"),
        ("SELECT COUNT(*) FROM d.fact WHERE student = 123456", "identifying column"),
        ("SELECT COUNT(*) FROM d.fact WHERE note = '1234567'", "ID-like"),
        ("SELECT 1; SELECT 2", "1 SELECT"),
    ],
)
def test_check_reproduce_refuses_what_could_name_a_row(sql, why):
    with pytest.raises(pipeline.Refusal, match=why):
        explain.check_reproduce(sql, {"student", "lea"}, {"student", "lea"})


def _draft(tmp_path, text):
    draft = tmp_path / "draft.sql"
    draft.write_text(text)
    return draft


def _confirm_text(duck, tmp_path, text, wh=None):
    wh = wh or Wh(duck)
    _save(duck, wh, results.latest_run(CFG, tmp_path)[0])
    explain.explain(
        CFG,
        tmp_path / "validation" / "v.yml",
        wh=wh,
        cube=None,
        max_usd=1.0,
        cache_root=tmp_path,
        comparison="mastery",
        bucket="cube_only",
        sql=_draft(tmp_path, text),
    )


def test_confirm_keeps_a_checked_reproduce_query_with_the_proof(
    duck, tmp_path, monkeypatch, offline, capsys
):
    _tables(duck)
    _saved(tmp_path, monkeypatch, _run([_group(3)]))

    _confirm_text(
        duck, tmp_path, explain.compose(CAUSES, EXPLANATION, {"C1": REPRODUCE})
    )

    stored = tmp_path / "validation" / "explanations" / "v" / "mastery__cube_only.sql"
    assert explain.read_explanation(stored).reproduce == {"C1": REPRODUCE}
    assert "Reproduce C1: dry run OK" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("reproduce", "why"),
    [
        ({"C9": REPRODUCE}, "no cause C9"),
        (
            {"C1": "SELECT * FROM d.fact"},
            "-- reproduce C1: the reproduce query selects",
        ),
    ],
)
def test_confirm_refuses_a_bad_reproduce_query_before_any_query(
    duck, tmp_path, monkeypatch, offline, reproduce, why
):
    _tables(duck)
    _saved(tmp_path, monkeypatch, _run([_group(3)]))
    wh = Wh(duck)

    with pytest.raises(pipeline.Refusal, match=why):
        _confirm_text(
            duck, tmp_path, explain.compose(CAUSES, EXPLANATION, reproduce), wh
        )

    assert wh.ran == [] and not (tmp_path / "validation").exists()


def test_explain_refuses_a_triage_written_before_the_formula_check(
    duck, tmp_path, monkeypatch, offline
):
    _tables(duck)
    path = _saved(tmp_path, monkeypatch, _run([_group(3)]))
    old = json.loads(path.read_text())
    del old["formulas_not_compared"]
    path.write_text(json.dumps(old))

    with pytest.raises(
        pipeline.Refusal, match="the triage predates the formula check; run `sort`"
    ):
        _confirm_text(duck, tmp_path, EXPLANATION)

    assert json.loads(path.read_text()) == old


def test_confirm_refuses_a_reproduce_query_bigquery_refuses(
    duck, tmp_path, monkeypatch, offline
):
    _tables(duck)
    _saved(tmp_path, monkeypatch, _run([_group(3)]))

    class Refusing(Wh):
        def estimate(self, sql):
            if "n_rows" in sql and "{unmatched}" not in sql and "__row" not in sql:
                raise BadRequest(
                    "Unrecognized name: ok3", errors=[{"reason": "invalidQuery"}]
                )
            return 0.01

    with pytest.raises(pipeline.Refusal, match="reproduce C1: BigQuery refused it"):
        _confirm_text(
            duck,
            tmp_path,
            explain.compose(CAUSES, EXPLANATION, {"C1": REPRODUCE}),
            Refusing(duck),
        )
    assert not (tmp_path / "validation").exists()


# --- cells left open; rows that sit in another cell ---------------------------------


def test_open_cell_lines_name_each_open_cell_and_why():
    # Cell Y holds no unmatched row; cell X's explained group covers it.
    cell = CELLS_RUN["diff_cells"][0]
    run = _run(
        [_placed(3)],
        cells=CELLS_RUN["cells"],
        diff_cells=[cell, {**cell, "key": "abbreviation=Y",
                           "dims": [["abbreviation", "Y"]], "cube": 0.2}],
    )  # fmt: skip
    left: dict = {}

    _cells(run=run, left=left)

    out = "\n".join(explain.open_cell_lines(left["mastery:cells"]))
    assert "- abbreviation=Y | cut {} | Cube 0.2, dashboard 1" in out
    assert "abbreviation=X" not in out
    assert "open: no unmatched row lies in it" in out


def test_open_cell_lines_name_an_unproven_group():
    left: dict = {}

    _cells(proven=False, left=left)

    out = "\n".join(explain.open_cell_lines(left["mastery:cells"]))
    assert "cube_only (investigate)" in out
    assert "open: 1 of its 1 groups are not in cause" in out


def test_a_cell_links_to_rows_the_dashboard_files_in_it_and_cube_elsewhere():
    moved = Group(
        "mastery",
        (("abbreviation", "Y"), ("d:abbreviation", "X")),
        "dims_differ",
        3,
        3,
        cut_rows=(("{}", 3, 3),),
    )
    # In cell X the dashboard holds 3 rows Cube files under Y: Cube shows 3 fewer.
    run = _run(
        [moved],
        cells=CELLS_RUN["cells"],
        diff_cells=[{**CELLS_RUN["diff_cells"][0], "cube": 1.0, "dashboard": 4.0}],
    )

    cells = _cells(run=run)

    assert cells["suggestion"] == "cause"


def test_a_proof_classifies_rows_that_sit_in_another_cell(duck, tmp_path, offline):
    # Synthetic: Cube files the row under school X, the dashboard under Y.
    _tables(duck, cube_rows=[(1, "a", "X")], fact_rows=[(1, "a", "Y", True, True)])
    moved = Group(
        "mastery", (("abbreviation", "X"), ("d:abbreviation", "Y")), "dims_differ", 1, 1
    )
    run = _run([moved])
    items = _items(run)
    directory = tmp_path / "explanations" / "v"
    directory.mkdir(parents=True)
    explain.explanation_path(directory, "mastery", "dims_differ").write_text(
        explain.compose(
            {"C1": ("dashboard", "the dashboard files the row under another school")},
            "SELECT u.__row, CASE WHEN u.side = 'both' THEN 'C1' "
            "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u",
        )
    )

    _stored(run, items, directory, Wh(duck))

    (item,) = items
    assert item["suggestion"] == "cause"
    assert item["cause"][0]["n_rows"] == 1


BY_TYPE = Comparison(
    id="mastery",
    measure="pct",
    dims=[ColumnPair("school", "abbreviation")],
    rows=RowSpec(
        grain=[*ROWS.grain, ColumnPair("rtype", "rtype")],
        values=[ColumnPair("ok", "ok")],
    ),
    decimals=2,
    filters={
        "Response Type": ColumnPair("rtype", "rtype"),
        "Academic Year": ColumnPair("year", "year"),
    },
    defaults={"Academic Year": 2026},
    cuts=[{"Response Type": "overall"}, {"Response Type": "standard"}],
)


def test_cut_flags_skip_a_caption_every_cut_shares():
    flags = pipeline.cut_flags(BY_TYPE)

    assert [label for label, _, _ in flags] == [
        '{"Response Type": "overall"}',
        '{"Response Type": "standard"}',
    ]
    _, cube, dash = flags[1]
    assert "c.rtype" in cube and "'standard'" in cube and "year" not in cube
    assert "d.rtype" in dash


def test_a_varying_cut_caption_becomes_a_row_column_on_both_sides():

    by_region = replace(
        BY_TYPE,
        cuts=[{"Region": "A"}, {"Region": "B"}],
        filters={**BY_TYPE.filters, "Region": ColumnPair("region", "region")},
    )

    flags = pipeline.cut_flags(by_region)

    assert [label for label, _, _ in flags] == ['{"Region": "A"}', '{"Region": "B"}']
    assert "c.region" in flags[1][1] and "d.region" in flags[1][2]
    assert ColumnPair("region", "region") in pipeline.row_pairs(by_region)
    # A caption every cut shares stays out of the rows.
    assert ColumnPair("year", "year") not in pipeline.row_pairs(by_region)


EXISTS_REPRODUCE = """SELECT r.school, COUNT(*) AS n_rows
FROM d.fact AS r
WHERE EXISTS (
  SELECT 1 FROM d.enrollments AS e
  WHERE e.student_number = r.student_number AND e.academic_year = {year}
)
GROUP BY r.school"""


def test_check_reproduce_tests_each_comparison_inside_exists_on_its_own():
    # The literal and the identifying join sit in different comparisons.
    explain.check_reproduce(EXISTS_REPRODUCE.format(year="2026"), {"student"})

    with pytest.raises(pipeline.Refusal, match="identifying column"):
        explain.check_reproduce(
            EXISTS_REPRODUCE.replace("= r.student_number", "= 123").format(year="2026"),
            {"student"},
        )


# --- a sort keeps its finished explanations and prices them first ------------


def test_a_second_triage_reuses_a_finished_proof_and_runs_no_query(
    duck, tmp_path, offline
):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _explanation(tmp_path)

    first = explain.run_stored(
        CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path
    )
    again = explain.run_stored(
        CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path
    )

    assert len(wh.ran) == 1
    assert again[0].found == first[0].found
    assert again[0].students == first[0].students


def test_an_edited_proof_or_a_new_group_runs_again(duck, tmp_path, offline):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _explanation(tmp_path)
    explain.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)

    _explanation(tmp_path, causes={"C1": CAUSES["C2"], "C2": CAUSES["C1"]})
    explain.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    bigger = _run([_group(4)])
    explain.run_stored(CFG, bigger, directory, wh=wh, cube=None, progress_dir=tmp_path)

    assert len(wh.ran) == 3


def test_proofs_refuse_before_any_runs_when_their_estimate_passes_a_cap(
    duck, tmp_path, offline
):
    class Capped(Wh):
        def refuse_past_caps(self, usd):
            if usd > 0.015:
                raise CostCapError(f"these queries (${usd:.2f}) would pass the cap")

    _tables(duck)
    run, wh = _sibling_run(), Capped(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _explanation(tmp_path)

    with pytest.raises(CostCapError, match=r"\(\$0\.02\)"):
        explain.run_stored(CFG2, run, directory, wh=wh, cube=None)

    assert wh.ran == []


def test_a_triage_stopped_partway_keeps_the_proofs_it_finished(duck, tmp_path, offline):
    class StopsOnSecond(Wh):
        def rows(self, sql, timeout_s=None):
            if len(self.ran) == 1:
                raise CostCapError("nothing is left under --max-usd")
            return super().rows(sql, timeout_s)

    _tables(duck)
    run, wh = _sibling_run(), StopsOnSecond(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _explanation(tmp_path)

    first = explain.run_stored(
        CFG2, run, directory, wh=wh, cube=None, progress_dir=tmp_path
    )

    assert [r.found is not None for r in first] == [True, False]
    assert len(explain_progress.load(tmp_path)) == 1

    wh = Wh(duck)
    _save(duck, wh, run, cfg=CFG2)
    explain.run_stored(CFG2, run, directory, wh=wh, cube=None, progress_dir=tmp_path)

    assert len(wh.ran) == 1  # only the explanation the first triage did not finish


def test_triage_of_one_comparison_reuses_the_others_and_runs_only_its_own(
    duck, tmp_path, offline
):
    _tables(duck)
    run, wh = _sibling_run(), Wh(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _explanation(tmp_path)
    kept, empty = tmp_path / "kept", tmp_path / "empty"
    explain.run_stored(CFG2, run, directory, wh=wh, cube=None, progress_dir=kept)
    wh.ran.clear()

    reused = explain.run_stored(
        CFG2, run, directory, wh=wh, cube=None, progress_dir=kept,
        comparisons={"mastery-b"},
    )  # fmt: skip

    assert wh.ran == [] and all(r.found is not None for r in reused)

    alone = explain.run_stored(
        CFG2, run, directory, wh=wh, cube=None, progress_dir=empty,
        comparisons={"mastery-b"},
    )  # fmt: skip

    assert len(wh.ran) == 1
    by = {explain._comparison_of(r): r for r in alone}
    assert by["mastery"].why == (
        "explanation mastery__cube_only.sql not run: outside --comparison"
    )
    assert by["mastery-b"].found is not None


def test_a_kept_outcome_is_not_reused_when_the_sql_no_longer_matches_the_run(
    duck, tmp_path, offline, monkeypatch
):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _explanation(tmp_path)
    explain.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)

    def changed(*a, **k):
        raise pipeline.Refusal("the cube SQL is not the SQL the run reconciled")

    monkeypatch.setattr(pipeline, "row_sides", changed)
    (again,) = explain.run_stored(
        CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path
    )

    assert again.found is None
    assert "not the SQL the run reconciled" in again.why


def test_a_kept_outcome_is_not_reused_when_its_saved_rows_are_gone(
    duck, tmp_path, offline
):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _explanation(tmp_path)
    explain.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    wh.labels.clear()

    (again,) = explain.run_stored(
        CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path
    )

    assert again.found is None and "no saved rows" in again.why


def test_proofs_outside_the_comparisons_are_counted_in_one_line(
    duck, tmp_path, offline, capsys
):
    _tables(duck)
    run, wh = _sibling_run(), Wh(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _explanation(tmp_path)

    explain.run_stored(
        CFG2, run, directory, wh=wh, cube=None, progress_dir=tmp_path,
        comparisons={"mastery-b"},
    )  # fmt: skip

    out = capsys.readouterr().out
    assert "not run: outside --comparison" not in out
    assert "1 explanation outside --comparison not run (no kept outcome)." in out


def test_each_explanation_run_prints_a_progress_line(duck, tmp_path, offline):
    _tables(duck)
    run = _run([_group(3)])
    wh = _saved_wh(duck, run)
    wh.spent = 0.25
    directory, path = _explanation(tmp_path)
    said = []

    class Ticks:
        def say(self, step, comparison, spent):
            said.append((step, comparison, spent))

    explain.run_stored(CFG, run, directory, wh=wh, cube=None, ticker=Ticks())

    assert said == [("sort explain", path.name, 0.25)]


def test_an_old_proofs_folder_is_refused_with_its_new_name(tmp_path):
    view_file = tmp_path / "v.yml"
    (tmp_path / "proofs" / "v").mkdir(parents=True)

    with pytest.raises(pipeline.Refusal) as caught:
        explain.explanations_dir(view_file, "v")

    old, new = tmp_path / "proofs" / "v", tmp_path / "explanations" / "v"
    assert str(caught.value) == (
        f"rename {old} to {new} (git mv); stored explanations moved"
    )


def test_the_explanations_folder_sits_beside_the_validation_file(tmp_path):
    view_file = tmp_path / "v.yml"
    (tmp_path / "proofs" / "v").mkdir(parents=True)
    (tmp_path / "explanations" / "v").mkdir(parents=True)

    found = explain.explanations_dir(view_file, "v")

    assert found == tmp_path / "explanations" / "v"


def test_unmatched_carries_moved_and_the_dashboard_cell(duck):
    # Row 1 sits in school X for Cube and Y for the dashboard; row 2 in X on both.
    duck.table(
        "saved_t",
        "bucket VARCHAR, __row BIGINT, abbreviation VARCHAR, __moved BOOLEAN, "
        "__d_abbreviation VARCHAR, __gc0 BIGINT, __gc1 VARCHAR, __gd0 BIGINT, "
        "__gd1 VARCHAR, __rn BIGINT, __ck0 BOOLEAN, __dk0 BOOLEAN",
        [("dims_differ", 1, "X", True, "Y", 1, "a", 1, "a", 1, True, True),
         ("dims_differ", 2, "X", False, None, 2, "b", 2, "b", 1, True, True)],
    )  # fmt: skip
    ctes, select = explain.unmatched_sql(COMPARISON, "dims_differ", [], "saved_t")
    assert "__moved" in select and "__d_abbreviation" in select

    rows = duck.rows(
        f"{ctes}\nSELECT u.__row AS r, u.__moved AS moved, "
        "COALESCE(u.__d_abbreviation, u.abbreviation) AS d "
        f"FROM ({select}) AS u ORDER BY u.__row"
    )

    assert [(r["r"], bool(r["moved"]), r["d"]) for r in rows] == [
        (1, True, "Y"),
        (2, False, "X"),
    ]


def test_unmatched_without_group_by_dims_has_no_moved_or_dashboard_cell(duck):
    ungrouped = replace(COMPARISON, dims=[])
    duck.table(
        "saved_t",
        "bucket VARCHAR, __row BIGINT, __gc0 BIGINT, __gc1 VARCHAR, __gd0 BIGINT, "
        "__gd1 VARCHAR, __rn BIGINT, __ck0 BOOLEAN, __dk0 BOOLEAN",
        [("cube_only", 1, 1, "a", 1, "a", 1, True, True)],
    )  # fmt: skip

    _, select = explain.unmatched_sql(ungrouped, "cube_only", [], "saved_t")

    assert "__moved" not in select and "__d_" not in select
