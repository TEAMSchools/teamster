import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import pipeline, trace

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import JOB_ID, Warehouse

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.decisions import Applied

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.report import RunResult

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo
from google.api_core.exceptions import BadRequest

START = datetime(2026, 10, 28, 21, 34, tzinfo=timezone.utc)
END = datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc)
BUILD = Build(START, END, "job")
TIB = 2**40

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


def _group(n, school="X"):
    return Group("mastery", (("abbreviation", school),), "cube_only", n, n)


def _side(dash):
    sides = pipeline.RowSides(
        cube=AsOf(CUBE, frozenset({"m.cube_t"}), frozenset()),
        dashboard=AsOf(dash, frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=["lea", "aid", "abbreviation"],
    )
    return trace._Side(CFG, COMPARISON, sides, BUILD, "cube_only")


class DuckWarehouse:
    """A warehouse whose queries run on DuckDB toy tables; prices nothing."""

    def __init__(self, duck):
        self.duck = duck
        self.ran = duck.ran

    def estimate(self, sql):
        return 0.0

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql, timeout_s=None):
        return self.duck.rows(sql)

    def table(self, dataset, name):
        return TableInfo("TABLE", None)


def _manifest(tmp_path, models):
    """A manifest of table models: `{name: (compiled_code, [parent names])}`."""
    nodes = {
        f"model.kipptaf.{name}": {
            "name": name,
            "database": "teamster-332318",
            "schema": "d",
            "alias": name,
            "config": {"materialized": "table"},
            "depends_on": {"nodes": [f"model.kipptaf.{p}" for p in parents]},
            "compiled_code": code,
        }
        for name, (code, parents) in models.items()
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"nodes": nodes}))
    return trace.Manifest(path)


def _trace(duck, dash, groups, *, levels=0, manifest=None, wh=None):
    bucket = trace._Bucket(
        _side(dash),
        groups,
        wh=wh or DuckWarehouse(duck),
        manifest=manifest,
        levels=levels,
        end_tables=set(),
        moved={},
        meter=trace._Meter(None),
    )
    return bucket.run()


def _cube_rows(duck, rows):
    duck.table("cube_t", "lea BIGINT, aid VARCHAR, abbreviation VARCHAR", rows)


# --- attribution, run end to end on DuckDB ---------------------------------------

FLAT = (
    "SELECT f.student, f.item, f.school FROM `teamster-332318.d.fact` AS f "
    "WHERE f.ok1 AND f.ok2"
)
FACT = "student BIGINT, item VARCHAR, school VARCHAR, ok1 BOOLEAN, ok2 BOOLEAN"


def test_one_step_two_steps_and_none_row_by_row(duck):
    _cube_rows(duck, [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")])
    duck.table(
        "fact",
        FACT,
        # 1 fails ok1 only; 2 fails both; 3 is not there at all.
        [
            (1, "a", "X", False, True),
            (2, "b", "X", False, False),
            (9, "z", "X", True, True),
        ],
    )

    found = _trace(duck, FLAT, [_group(3)])[trace.item_key(_group(3))]

    assert found.steps == {
        "dashboard:main:1": 1,
        "dashboard:main:1+dashboard:main:2": 1,
    }
    assert (
        found.labels["dashboard:main:1+dashboard:main:2"] == "main: f.ok1 + main: f.ok2"
    )
    assert found.none == 1 and not found.proven and found.consistent


def test_rows_present_but_dropped_by_two_steps_never_descend(duck, tmp_path):
    # D4: the row is in the table; two steps of the side drop it, and the
    # table's build has another row of the same grain a relaxed step would
    # bring in. The pair is the cause, never the build's step.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "raw",
        f"{FACT}, keep BOOLEAN",
        [(1, "a", "X", False, False, True), (1, "a", "X", True, True, False)],
    )
    duck.table("fact", FACT, [(1, "a", "X", False, False)])
    manifest = _manifest(
        tmp_path,
        {
            "fact": (
                "select student, item, school, ok1, ok2 "
                "from `teamster-332318`.`d`.`raw` where keep",
                [],
            )
        },
    )

    found = _trace(duck, FLAT, [_group(1)], levels=1, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert found.proven
    assert [c["label"] for c in found.cause()] == ["main: f.ok1 + main: f.ok2"]
    assert not any("fact/" in s for s in found.steps)


def test_a_row_missing_from_a_table_descends_to_the_step_that_drops_it(duck, tmp_path):
    _cube_rows(duck, [(3, "c", "X")])
    duck.table("raw", f"{FACT}, keep BOOLEAN", [(3, "c", "X", True, True, False)])
    duck.table("fact", FACT, [])
    manifest = _manifest(
        tmp_path,
        {
            "fact": (
                "select student, item, school, ok1, ok2 "
                "from `teamster-332318`.`d`.`raw` where keep",
                [],
            )
        },
    )

    found = _trace(duck, FLAT, [_group(1)], levels=1, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert found.proven
    assert found.cause() == [
        {
            "side": "dashboard",
            "step": "dashboard:fact/main:1",
            "label": "fact/main: keep",
            "n_rows": 1,
        }
    ]


def test_rows_left_at_the_deepest_level_are_below_its_tables(duck, tmp_path):
    _cube_rows(duck, [(3, "c", "X")])
    duck.table("raw", f"{FACT}, keep BOOLEAN", [])
    duck.table("fact", FACT, [])
    manifest = _manifest(
        tmp_path,
        {
            "fact": (
                "select student, item, school, ok1, ok2 "
                "from `teamster-332318`.`d`.`raw` where keep",
                ["raw"],
            ),
            "raw": ("select 1", []),
        },
    )

    found = _trace(duck, FLAT, [_group(1)], levels=0, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    # Missing from `fact`, and the trace may not go below the side.
    assert found.below == ("fact",)
    assert "recovered by no step (below fact)" in found.evidence()[-1]


UNION = (
    "SELECT u.student, u.item, u.school FROM ("
    "SELECT student, item, school FROM `teamster-332318.d.subj` WHERE covers "
    "UNION ALL "
    "SELECT student, item, school FROM `teamster-332318.d.home` WHERE covers"
    ") AS u"
)
SPLIT = (
    "WITH a AS (SELECT student, item, school FROM `teamster-332318.d.subj` "
    "WHERE covers), b AS (SELECT student, item, school FROM "
    "`teamster-332318.d.home` WHERE covers) "
    "SELECT student, item, school FROM a UNION ALL "
    "SELECT student, item, school FROM b"
)


def test_steps_of_one_scope_each_recovering_a_row_are_one_cause(duck):
    _cube_rows(duck, [(1, "a", "X")])
    cols = "student BIGINT, item VARCHAR, school VARCHAR, covers BOOLEAN"
    duck.table("subj", cols, [(1, "a", "X", False)])
    duck.table("home", cols, [(1, "a", "X", False)])

    one = _trace(duck, UNION, [_group(1)])[trace.item_key(_group(1))]
    two = _trace(duck, SPLIT, [_group(1)])[trace.item_key(_group(1))]

    assert one.proven
    assert [c["label"] for c in one.cause()] == ["u: covers / u: covers"]
    # Across scopes the same rows stay unattributed.
    assert not two.proven and two.many == 1
    assert "recovered by steps in 2 or more scopes" in two.evidence()[-1]


def test_a_grain_the_other_side_holds_twice_is_never_attributed(duck):
    _cube_rows(duck, [(1, "a", "X"), (1, "a", "X")])
    duck.table("fact", FACT, [(1, "a", "X", True, True)])

    found = _trace(duck, FLAT, [_group(1)])[trace.item_key(_group(1))]

    assert found.duplicates == 1 and not found.proven
    assert "duplicate grain on the other side" in found.evidence()[-1]


def test_the_split_path_counts_as_the_combined_query_does(duck, monkeypatch):
    # Row 1 fails ok1, row 2 both, row 3 ok2: one item, so the steps that
    # share it are counted again together.
    _cube_rows(duck, [(1, "a", "X"), (2, "b", "X"), (3, "c", "X")])
    duck.table(
        "fact",
        FACT,
        [
            (1, "a", "X", False, True),
            (2, "b", "X", False, False),
            (3, "c", "X", True, False),
        ],
    )
    whole = _trace(duck, FLAT, [_group(3)])[trace.item_key(_group(3))]
    side = _side(FLAT)
    q = trace.Query(FLAT, frozenset(side.grain()), side.grain()[0])
    one, two = q.steps("dashboard")
    pair = [(s.id, q.relaxed(s)) for s in (one, two)]
    # Room for the 2 steps together, not for the unrelaxed SQL besides.
    monkeypatch.setattr(trace, "MAX_QUERY_CHARS", len(side.query(pair, [], True)) + 10)
    duck.ran.clear()

    split = _trace(duck, FLAT, [_group(3)])[trace.item_key(_group(3))]

    assert split.steps == whole.steps and split.consistent
    assert any(
        "UNION ALL SELECT bucket, abbreviation, '' AS step_id" in s for s in duck.ran
    )
    assert any("per_row" in s and "'!dashboard'" not in s for s in duck.ran)


def test_rows_the_unrelaxed_sql_already_returns_are_never_attributed(duck):
    # The dashboard rows the run reconciled lack row 1; the SQL now has it.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table("fact", FACT, [(1, "a", "X", True, True)])
    side = _side(FLAT)
    side.sides = pipeline.RowSides(
        cube=side.sides.cube,
        dashboard=AsOf(f"{FLAT} AND f.student <> 1", frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=side.sides.columns,
    )
    bucket = trace._Bucket(
        side,
        [_group(1)],
        wh=DuckWarehouse(duck),
        manifest=None,
        levels=0,
        end_tables=set(),
        moved={},
        meter=trace._Meter(None),
    )
    bucket.root = trace._Frame(
        trace.Query(FLAT, frozenset(side.grain()), side.grain()[0])
    )

    found = bucket.run()[trace.item_key(_group(1))]

    assert found.unreproduced == {"dashboard": 1} and not found.proven


# --- refusals, caps, stops and failures ----------------------------------------


class FakeWarehouse:
    """Answers each trace query from `answer(sql)`; prices nothing."""

    def __init__(self, answer):
        self.answer = answer
        self.ran: list[str] = []

    def estimate(self, sql):
        return 0.0

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql, timeout_s=None):
        self.ran.append(sql)
        return self.answer(sql)

    def table(self, dataset, name):
        return TableInfo("TABLE", None)


class _DryClient:
    def __init__(self, nbytes):
        self.nbytes = nbytes
        self.queries: list[tuple[str, bool]] = []

    def query(self, sql, job_config=None):
        dry = bool(job_config and job_config.dry_run)
        self.queries.append((sql, dry))
        return type("Job", (), {"total_bytes_processed": self.nbytes, "result": list})()


def _canned(sql=None, *, wh, levels=0, manifest=None):
    return trace._Bucket(
        _side(FLAT),
        [_group(5)],
        wh=wh,
        manifest=manifest,
        levels=levels,
        end_tables=set(),
        moved={},
        meter=trace._Meter(None),
    )


def test_a_level_past_the_cap_stops_and_keeps_what_was_found():
    wh = Warehouse(client=_DryClient(nbytes=TIB))

    with wh.budget(1.0), pytest.raises(trace.Stopped) as caught:
        _canned(wh=wh).run()

    found = caught.value.found[trace.item_key(_group(5))]
    assert "would pass the $1.00 cap" in caught.value.reason
    assert found.unknown == 5 and found.stopped and not found.proven
    assert "trace stopped: " in found.evidence()[-1]


def test_the_time_limit_stops_the_trace():
    bucket = _canned(wh=FakeWarehouse(lambda sql: pytest.fail("ran")))
    bucket.runner.meter = trace._Meter(0.0)

    with pytest.raises(trace.Stopped, match="time limit"):
        bucket.run()


def test_a_query_failure_keeps_its_job_and_reason_but_not_its_message():
    class Failing(FakeWarehouse):
        def rows(self, sql, timeout_s=None):
            self.ran.append(sql)
            exc = BadRequest(
                "Bad int64 value: 12345", errors=[{"reason": "invalidQuery"}]
            )
            setattr(exc, JOB_ID, "job-9")
            raise exc

    found = _canned(wh=Failing(None)).run()[trace.item_key(_group(5))]

    assert found.unknown == 5 and not found.proven
    assert found.failed == ("the side's own SQL: job job-9, invalidQuery",)
    assert "12345" not in " ".join(found.evidence())


def test_counts_that_do_not_add_up_never_prove_an_item():
    found = trace.ItemTrace("dashboard", 10)
    found.steps["s"] = 10
    found.labels["s"] = "main: s"
    found.none = 2

    assert not found.consistent and not found.proven
    assert "trace counts do not add up; trace it by hand" in found.evidence()


def test_evidence_masks_a_part_its_total_would_give_away():
    found = trace.ItemTrace("dashboard", 25)
    found.steps["s"] = 18
    found.labels["s"] = "main: s"
    found.none = 7

    assert found.shown_total() == "25"
    assert found.evidence() == (
        "main: s: masked rows",
        "<10 rows unattributed: <10 recovered by no step",
    )


def test_missing_compiled_sql_refuses_with_one_command_for_every_model(tmp_path):
    manifest = _manifest(tmp_path, {"fact": ("", ["raw"]), "raw": ("select 1", [])})
    roots = trace.Query(FLAT, frozenset({"student"}), "student").tables()

    with pytest.raises(pipeline.Refusal) as caught:
        manifest.require_compiled(roots, 2)

    # A compile drops every model's compiled SQL it did not select, so the
    # command names all of them, not only the missing one.
    assert "no compiled SQL for fact;" in str(caught.value)
    assert str(caught.value).endswith(
        "uv run dbt deps --project-dir src/dbt/kipptaf && uv run dbt compile "
        "--project-dir src/dbt/kipptaf --profiles-dir src/dbt/kipptaf --target prod "
        "--target-path target/prod --select fact raw"
    )


def test_a_missing_manifest_refuses_with_the_command_that_makes_one(tmp_path):
    roots = trace.Query(FLAT, frozenset({"student"}), "student").tables()

    with pytest.raises(pipeline.Refusal) as caught:
        trace.Manifest.load(tmp_path / "nope.json", roots)

    assert str(caught.value).endswith("--target-path target/prod --select +fact")


def test_a_table_whose_compiled_sql_does_not_run_is_skipped_and_named(tmp_path):
    class Stale(FakeWarehouse):
        def estimate(self, sql):
            if "raw" in sql and "'?'" not in sql and "!" not in sql:
                raise BadRequest("Unrecognized name: quarter")
            return 0.0

    def answer(sql):
        if "AS step_id" in sql and "'#0'" in sql:
            return [_answer_row("", 5)]
        return [_answer_row("", 5)]

    manifest = _manifest(
        tmp_path,
        {"fact": ("select * from `teamster-332318`.`d`.`raw`", [])},
    )

    found = _canned(wh=Stale(answer), levels=1, manifest=manifest).run()[
        trace.item_key(_group(5))
    ]

    assert found.below == ("fact",)


def _answer_row(step_id, n):
    return {"bucket": "cube_only", "abbreviation": "X", "step_id": step_id, "n_rows": n}


def test_a_dashboard_only_filter_group_is_proven_by_the_reconcile():
    filtered = Comparison(
        id="mastery",
        measure="pct",
        dashboard_filters=[
            {"dashboard": "administered_at", "operator": "lte", "days_from_week_end": 0}
        ],
    )
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[filtered])
    group = Group(
        "mastery",
        (("dashboard_filter", "administered_at"), ("abbreviation", "BOLD")),
        "dashboard_filtered",
        12,
        9,
    )

    (found,) = trace._filter_traces(cfg, [group]).values()

    assert found.proven
    assert found.cause()[0]["label"].startswith("dashboard filter administered_at <= ")
    assert found.cause()[0]["n_rows"] == 12


@pytest.mark.parametrize("first", ["trace", "sqlsteps", "triage", "pipeline", "cli"])
def test_each_module_imports_first(first):
    scripts = Path(trace.__file__).resolve().parents[1]
    done = subprocess.run(
        [sys.executable, "-c", f"import cube_validation.{first}"],
        cwd=scripts,
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr[-500:]


def test_every_refusal_comes_before_the_first_trace_query(tmp_path, monkeypatch):
    side = _side(FLAT)
    monkeypatch.setattr(trace, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: side.sides)
    run = RunResult(
        view="v", moment=BUILD, measures=[], applied=Applied(open=[_group(5)])
    )
    wh = FakeWarehouse(lambda sql: pytest.fail("a trace query ran"))

    with pytest.raises(pipeline.Refusal, match="no dbt manifest"):
        trace.trace_run(CFG, run, wh=wh, cube=None, manifest_path=tmp_path / "x.json")

    manifest = _manifest(tmp_path, {"fact": ("", [])})
    with pytest.raises(pipeline.Refusal, match="no compiled SQL for fact"):
        trace.trace_run(CFG, run, wh=wh, cube=None, manifest_path=manifest.path)
    assert wh.ran == []


# --- fix round 2 ------------------------------------------------------------------

RAW_COLS = "student BIGINT, item VARCHAR, school VARCHAR, ok1 BOOLEAN"


def test_a_row_two_levels_drop_never_descends_to_a_stand_in(duck, tmp_path):
    # N1: the row is in `mid`; `fact`'s `keep` and the side's `ok1` both drop
    # it. `raw` holds a junk row of its grain behind `good`.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "raw",
        f"{RAW_COLS}, keep BOOLEAN, good BOOLEAN",
        [(1, "a", "X", False, False, True), (1, "a", "X", True, True, False)],
    )
    duck.table("mid", f"{RAW_COLS}, keep BOOLEAN", [(1, "a", "X", False, False)])
    duck.table("fact", RAW_COLS, [])
    manifest = _manifest(
        tmp_path,
        {
            "fact": (
                "select student, item, school, ok1 "
                "from `teamster-332318`.`d`.`mid` where keep",
                ["mid"],
            ),
            "mid": (
                "select student, item, school, ok1, keep "
                "from `teamster-332318`.`d`.`raw` where good",
                [],
            ),
        },
    )
    dash = (
        "SELECT f.student, f.item, f.school FROM `teamster-332318.d.fact` AS f "
        "WHERE f.ok1"
    )

    found = _trace(duck, dash, [_group(1)], levels=2, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert not found.proven and not found.steps
    assert found.needs_more and not found.none


def test_a_row_a_row_pick_drops_never_descends_to_a_stand_in(duck, tmp_path):
    # N2: the side picks item b for student 1; `raw2` holds a later junk (1, a)
    # behind `keep` that would win the pick.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "raw2",
        "student BIGINT, item VARCHAR, school VARCHAR, d BIGINT, keep BOOLEAN",
        [(1, "a", "X", 1, True), (1, "b", "X", 2, True), (1, "a", "X", 3, False)],
    )
    duck.table(
        "fact2",
        "student BIGINT, item VARCHAR, school VARCHAR, d BIGINT",
        [(1, "a", "X", 1), (1, "b", "X", 2)],
    )
    manifest = _manifest(
        tmp_path,
        {
            "fact2": (
                "select student, item, school, d "
                "from `teamster-332318`.`d`.`raw2` where keep",
                [],
            )
        },
    )
    dash = (
        "WITH r AS (SELECT student, item, school, ROW_NUMBER() OVER "
        "(PARTITION BY student ORDER BY d DESC) AS rn "
        "FROM `teamster-332318.d.fact2`) "
        "SELECT student, item, school FROM r WHERE rn = 1"
    )

    found = _trace(duck, dash, [_group(1)], levels=1, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert not found.proven and not found.steps
    assert not found.none


def test_a_masked_unattributed_count_masks_its_whole_breakdown():
    # N3: 40 = 25 + 5 + 10; with the 10 shown, 40 - 25 - 10 gives the 5.
    found = trace.ItemTrace("dashboard", 40)
    found.steps |= {"a": 25, "b": 5}
    found.labels |= {"a": "main: a", "b": "main: b"}
    found.none = 10

    lines = found.evidence()

    assert lines[:2] == ("main: a: 25 rows", "main: b: <10 rows")
    assert lines[2] == "masked rows unattributed: masked recovered by no step"
    assert "10" not in lines[2]


def test_a_stop_keeps_the_items_already_proven(duck):
    # N4: one item is proven at level 0; the stop comes after.
    _cube_rows(duck, [(1, "a", "X"), (2, "b", "Y")])
    duck.table("fact", FACT, [(1, "a", "X", False, True)])
    wh = DuckWarehouse(duck)
    queries = []

    def rows(sql, timeout_s=None):
        queries.append(sql)
        if len(queries) > 1:
            raise trace.Stopped("the trace passed its time limit")
        return duck.rows(sql)

    wh.rows = rows
    groups = [_group(1, "X"), _group(1, "Y")]

    with pytest.raises(trace.Stopped) as caught:
        _trace(duck, FLAT, groups, wh=wh)

    proven = caught.value.found[trace.item_key(groups[0])]
    stopped = caught.value.found[trace.item_key(groups[1])]
    assert proven.proven and not proven.stopped
    assert stopped.stopped and not stopped.proven


def test_a_dry_run_error_partway_stops_with_its_job_and_reason(duck):
    # N5: level 0 ran (and was paid); the presence check fails its dry run.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table("fact", FACT, [])
    wh = DuckWarehouse(duck)

    def estimate(sql):
        if "'#0'" in sql:
            exc = BadRequest(
                "Unrecognized name: 12345", errors=[{"reason": "invalidQuery"}]
            )
            setattr(exc, JOB_ID, "job-7")
            raise exc
        return 0.0

    wh.estimate = estimate

    with pytest.raises(trace.Stopped) as caught:
        _trace(duck, FLAT, [_group(1)], wh=wh)

    assert "invalidQuery" in caught.value.reason and "12345" not in caught.value.reason
    assert caught.value.found[trace.item_key(_group(1))].stopped


def test_level_zero_is_priced_in_the_batches_it_runs_in(tmp_path, monkeypatch):
    # N12: a level-0 query past the limit is priced split, never as one.
    side = _side(FLAT)
    monkeypatch.setattr(trace, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: side.sides)
    run = RunResult(
        view="v", moment=BUILD, measures=[], applied=Applied(open=[_group(5)])
    )
    q = trace.Query(FLAT, frozenset(side.grain()), side.grain()[0])
    one = [(s.id, q.relaxed(s)) for s in q.steps("dashboard")][:1]
    # Room for 1 variant per query, not for all of them in one.
    monkeypatch.setattr(trace, "MAX_QUERY_CHARS", len(side.query(one, [], False)) + 10)
    priced = []

    class Strict(FakeWarehouse):
        def estimate(self, sql):
            assert len(sql) <= trace.MAX_QUERY_CHARS, "priced an unsplit query"
            priced.append(sql)
            return 0.0

    # Nothing comes back, so the trace stops after level 0.
    wh = Strict(lambda sql: [])

    trace.trace_run(CFG, run, wh=wh, cube=None, levels=0)

    assert len(priced) >= 2


def test_a_skipped_pair_search_says_why(duck, monkeypatch):
    # N7: rows a pair could explain, with no pair searched.
    _cube_rows(duck, [(2, "b", "X")])
    duck.table("fact", FACT, [(2, "b", "X", False, False)])
    monkeypatch.setattr(trace, "MAX_PAIRS", 0)

    found = _trace(duck, FLAT, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven
    assert "pair search skipped: 1 pairs" in found.evidence()[-1]


# --- fix round 3: a filter that feeds a row pick -----------------------------------

PICKED = (
    "WITH f AS (SELECT student, item, school, d FROM `teamster-332318.d.src` "
    "WHERE x), "
    "r AS (SELECT student, item, school, ROW_NUMBER() OVER "
    "(PARTITION BY student ORDER BY d DESC) AS rn FROM f) "
    "SELECT student, item, school FROM r WHERE rn = 1"
)
SRC = "student BIGINT, item VARCHAR, school VARCHAR, d BIGINT, x BOOLEAN"


def test_a_filter_whose_relaxing_lets_another_row_win_a_pick_is_no_cause(duck):
    # Student 1's pick keeps b. Relaxing `x` lets a later junk (1, a) win the
    # pick: (1, a) "comes back", but the pick, not `x`, dropped the real one.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "src",
        SRC,
        [(1, "a", "X", 1, True), (1, "b", "X", 2, True), (1, "a", "X", 3, False)],
    )

    found = _trace(duck, PICKED, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven and not found.steps
    assert "a row pick follows f: x; another row could stand in" in found.evidence()[-1]


def test_a_filter_ahead_of_a_pick_with_1_candidate_is_still_proven(duck):
    # Student 2's only row fails `x`: relaxing it brings back that row, the
    # only one its pick can keep.
    _cube_rows(duck, [(2, "c", "X")])
    duck.table("src", SRC, [(2, "c", "X", 1, False)])

    found = _trace(duck, PICKED, [_group(1)])[trace.item_key(_group(1))]

    assert found.proven
    assert [c["label"] for c in found.cause()] == ["f: x"]


# --- fix round 4: the guard fails closed -------------------------------------------

WINDOW = "ROW_NUMBER() OVER (PARTITION BY student ORDER BY d DESC) AS rn"
IN_PICK = (
    f"WITH r AS (SELECT student, item, school, {WINDOW} FROM `teamster-332318.d.src` "
    "WHERE d IN (SELECT d FROM `teamster-332318.d.days` WHERE z)) "
    "SELECT student, item, school FROM r WHERE rn = 1"
)
UNION_PICK = (
    f"WITH u AS (SELECT student, item, school, {WINDOW} FROM `teamster-332318.d.src` "
    "WHERE x UNION ALL SELECT student, item, school, {rn} "
    "FROM `teamster-332318.d.src2` WHERE d > 0) "
    "SELECT student, item, school FROM u WHERE rn = 1"
)
EXCEPT_PICK = (
    f"WITH r AS (SELECT student, item, school, {WINDOW} FROM `teamster-332318.d.src` "
    "WHERE x), k AS (SELECT student, item, school FROM r WHERE rn = 1 "
    "EXCEPT DISTINCT SELECT student, item, school FROM `teamster-332318.d.excl`) "
    "SELECT student, item, school FROM k"
)
PARENT_PICK = (
    f"WITH r AS (SELECT student, item, school, {WINDOW} "
    "FROM `teamster-332318.d.fact3`) "
    "SELECT student, item, school FROM r WHERE rn = 1"
)
RAW3 = "student BIGINT, item VARCHAR, school VARCHAR, d BIGINT, keep BOOLEAN"
FACT3 = {
    "fact3": (
        "select student, item, school, d from `teamster-332318`.`d`.`raw3` where keep",
        [],
    )
}


def test_a_step_in_the_window_s_in_subquery_is_no_cause_where_a_row_could_stand_in(
    duck,
):
    # N-new-1 (D2): relaxing `z` lets the junk (1, a, 3) win the pick over b.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "src",
        SRC,
        [
            (1, "a", "X", 1, True),
            (1, "b", "X", 2, True),
            (1, "a", "X", 3, True),
            (1, "c", "X", 4, True),
        ],
    )
    duck.table("days", "d BIGINT, z BOOLEAN", [(1, True), (2, True), (3, False)])

    found = _trace(duck, IN_PICK, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven and not found.steps
    assert "a row pick follows r: z; another row could stand in" in found.evidence()[-1]


def test_a_step_in_one_union_branch_is_guarded_by_that_branch_s_pick(duck):
    # N-new-2 (U): each branch computes its own rn; the junk (1, a, 3) fails x.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "src",
        SRC,
        [(1, "a", "X", 1, True), (1, "b", "X", 2, True), (1, "a", "X", 3, False)],
    )
    duck.table("src2", SRC, [(9, "z", "X", 1, True)])
    dash = UNION_PICK.format(rn=WINDOW)

    found = _trace(duck, dash, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven and not found.steps
    assert "a row pick follows u: x; another row could stand in" in found.evidence()[-1]

    # 1 candidate: student 1's only row fails x, so x alone is the cause.
    duck.table("src", SRC, [(1, "a", "X", 1, False)])

    found = _trace(duck, dash, [_group(1)])[trace.item_key(_group(1))]

    assert found.proven and [c["label"] for c in found.cause()] == ["u: x"]


def test_a_pick_a_branch_computes_without_a_window_blocks_every_step_ahead(duck):
    # N-new-2: the second branch's rn is a literal, so the guard cannot count
    # its candidates; even a 1-candidate row stays unattributed.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table("src", SRC, [(1, "a", "X", 1, False)])
    duck.table("src2", SRC, [(9, "z", "X", 1, True)])

    found = _trace(duck, UNION_PICK.format(rn="1 AS rn"), [_group(1)])[
        trace.item_key(_group(1))
    ]

    assert not found.proven and not found.steps
    assert "a row pick follows u: x; another row could stand in" in found.evidence()[-1]


def test_a_count_is_never_carried_through_an_except(duck):
    # N-new-3 (X): the true relaxed query still excludes (1, a). A NULL mark
    # on the EXCEPT's other branch would stop it matching, and put it back.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table("src", SRC, [(1, "a", "X", 1, False)])
    duck.table("excl", "student BIGINT, item VARCHAR, school VARCHAR", [(1, "a", "X")])

    found = _trace(duck, EXCEPT_PICK, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven and not found.steps
    assert not any("__cand" in sql for sql in duck.ran)


def test_a_pick_in_the_level_above_guards_a_step_below(duck, tmp_path):
    # P-old-1 (C): the side picks over fact3; relaxing fact3's `keep` lets the
    # junk (1, a, 3) win the pick over b.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table(
        "raw3",
        RAW3,
        [(1, "a", "X", 1, False), (1, "b", "X", 2, True), (1, "a", "X", 3, False)],
    )
    duck.table("fact3", RAW3.replace(", keep BOOLEAN", ""), [(1, "b", "X", 2)])
    manifest = _manifest(tmp_path, FACT3)

    found = _trace(duck, PARENT_PICK, [_group(1)], levels=1, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert not found.proven and not found.steps
    assert (
        "a row pick follows fact3/main: keep; another row could stand in"
        in found.evidence()[-1]
    )

    # 1 candidate: student 1's only row fails `keep`, so `keep` is the cause.
    duck.table("raw3", RAW3, [(1, "a", "X", 1, False)])
    duck.table("fact3", RAW3.replace(", keep BOOLEAN", ""), [])

    found = _trace(duck, PARENT_PICK, [_group(1)], levels=1, manifest=manifest)[
        trace.item_key(_group(1))
    ]

    assert found.proven
    assert [c["label"] for c in found.cause()] == ["fact3/main: keep"]


def test_a_row_only_a_row_pick_drops_says_so(duck):
    # M-new-1: (1, a) passes `x`; the pick keeps b. The reason must not point
    # at steps, and no pair search is needed.
    _cube_rows(duck, [(1, "a", "X")])
    duck.table("src", SRC, [(1, "a", "X", 1, True), (1, "b", "X", 2, True)])

    found = _trace(duck, PICKED, [_group(1)])[trace.item_key(_group(1))]

    assert not found.proven and not found.steps and not found.needs_more
    assert found.evidence()[-1] == (
        "<10 rows unattributed: <10 a row pick drops it; the row is in the "
        "tables the dashboard SQL reads"
    )


def test_masked_cells_of_a_breakdown_hold_10_or_more_together():
    # P-old-2: 40 = 10 + (25 + 3 + 2). With the 25 shown, 40 - 10 - 25 gives
    # the two small cells' sum; so the 25 is masked too, and the 30 may show.
    found = trace.ItemTrace("dashboard", 40)
    found.steps["a"] = 10
    found.labels["a"] = "main: a"
    found.many = 25
    found.many_labels = ("main: b", "main: c")
    found.pairs_many = 3
    found.none = 2

    lines = found.evidence()

    assert found.shown_total() == "40"
    assert lines[0] == "main: a: 10 rows"
    assert lines[1] == (
        "30 rows unattributed: masked recovered by steps in 2 or more scopes "
        "(main: b, main: c); <10 recovered by more than one pair of steps; "
        "<10 recovered by no step"
    )


# --- a pair search too complex to plan, and per-bucket stops -----------------------

PAIR_ID = re.compile(r"'[^']+\+[^']+' AS step_id")
FACT_OK3 = f"{FACT}, ok3 BOOLEAN"
FLAT_OK3 = FLAT + " AND f.ok3"


def _too_complex():
    return BadRequest("too big", errors=[{"reason": "resourcesExceeded"}])


def test_a_pair_search_too_complex_to_plan_skips_only_its_rows(duck):
    # (2, b) is present but needs ok1 and ok2 together: only a pair explains it.
    _cube_rows(duck, [(2, "b", "X")])
    duck.table("fact", FACT, [(2, "b", "X", False, False)])
    wh = DuckWarehouse(duck)

    def estimate(sql):
        if PAIR_ID.search(sql):
            raise _too_complex()
        return 0.0

    wh.estimate = estimate

    found = _trace(duck, FLAT, [_group(1)], wh=wh)[trace.item_key(_group(1))]

    assert found.skipped == {"query too complex": 1}
    assert not found.stopped and not found.unknown
    assert "pair search skipped: query too complex" in found.evidence()[-1]


def test_pair_batches_stay_under_the_pair_query_cap(duck, monkeypatch):
    # (2, b) fails ok1 and ok2: 3 pairs of 1 scope, each its own batch.
    _cube_rows(duck, [(2, "b", "X")])
    duck.table("fact", FACT_OK3, [(2, "b", "X", False, False, True)])
    side = _side(FLAT_OK3)
    q = trace.Query(FLAT_OK3, frozenset(side.grain()), side.grain()[0])
    a, b = q.steps("dashboard")[:2]
    one = [(f"{a.id}+{b.id}", q.relaxed_many([a, b]))]
    monkeypatch.setattr(
        trace, "MAX_PAIR_QUERY_CHARS", len(side.query(one, [], False)) + 200
    )
    wh = DuckWarehouse(duck)
    priced = []

    def estimate(sql):
        if PAIR_ID.search(sql):
            priced.append(sql)
        return 0.0

    wh.estimate = estimate

    found = _trace(duck, FLAT_OK3, [_group(1)], wh=wh)[trace.item_key(_group(1))]

    # A batch past the cap holds 1 pair alone: the cap splits, never drops.
    assert len(priced) >= 2
    assert all(
        len(sql) <= trace.MAX_PAIR_QUERY_CHARS or len(PAIR_ID.findall(sql)) == 1
        for sql in priced
    )
    assert found.proven and list(found.labels.values()) == ["main: f.ok1 + main: f.ok2"]


def test_the_pair_query_cap_holds_4_copies_of_the_56k_side_sql():
    # A 56K-character side SQL copied about 15 times was refused at planning.
    assert 4 * 56_000 <= trace.MAX_PAIR_QUERY_CHARS < 6 * 56_000


def test_a_stop_in_one_bucket_never_stops_the_other(monkeypatch):
    side = _side(FLAT)
    monkeypatch.setattr(trace, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: side.sides)
    cube_only = _group(5)
    dash_only = Group("mastery", (("abbreviation", "X"),), "dashboard_only", 4, 4)
    run = RunResult(
        view="v",
        moment=BUILD,
        measures=[],
        applied=Applied(open=[cube_only, dash_only]),
    )
    seen = []

    class Failing(FakeWarehouse):
        def estimate(self, sql):
            # The up-front level-0 price passes; the cube_only bucket's own
            # first query then fails its dry run.
            if "bucket = 'cube_only'" in sql:
                seen.append(sql)
                if len(seen) > 1:
                    raise BadRequest("x", errors=[{"reason": "invalidQuery"}])
            return 0.0

    wh = Failing(lambda sql: [])

    result = trace.trace_run(CFG, run, wh=wh, cube=None, levels=0)

    assert "invalidQuery" in result.items[trace.item_key(cube_only)].stopped
    assert not result.items[trace.item_key(dash_only)].stopped
    assert any("bucket = 'dashboard_only'" in sql for sql in wh.ran)
    assert result.stops == {
        ("mastery", "cube_only"): result.items[trace.item_key(cube_only)].stopped
    }


def test_a_level_zero_dry_run_error_stops_only_its_bucket(monkeypatch):
    side = _side(FLAT)
    monkeypatch.setattr(trace, "network_schools", lambda wh: set())
    monkeypatch.setattr(pipeline, "row_sides", lambda *a, **k: side.sides)
    cube_only = _group(5)
    dash_only = Group("mastery", (("abbreviation", "X"),), "dashboard_only", 4, 4)
    run = RunResult(
        view="v",
        moment=BUILD,
        measures=[],
        applied=Applied(open=[cube_only, dash_only]),
    )

    class Failing(FakeWarehouse):
        def estimate(self, sql):
            if "bucket = 'cube_only'" in sql:
                raise _too_complex()
            return 0.0

    wh = Failing(lambda sql: [])

    result = trace.trace_run(CFG, run, wh=wh, cube=None, levels=0)

    stopped = result.items[trace.item_key(cube_only)]
    assert "level 0" in stopped.stopped and stopped.unknown == 5
    assert not result.items[trace.item_key(dash_only)].stopped
    assert any("bucket = 'dashboard_only'" in sql for sql in wh.ran)
