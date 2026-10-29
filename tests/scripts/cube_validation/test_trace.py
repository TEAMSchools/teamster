import json
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

    assert found.shown_total() == "masked"
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
