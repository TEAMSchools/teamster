import json
from datetime import datetime, timezone

import pytest

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import pipeline, trace

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.bq import CostCapError, Warehouse

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.compare import Group

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.config import ColumnPair, Comparison, RowSpec, ViewConfig

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.moment import Build

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.sqlsteps import Query

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.timetravel import AsOf, TableInfo
from google.api_core.exceptions import BadRequest

START = datetime(2026, 10, 28, 21, 34, tzinfo=timezone.utc)
END = datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc)
BUILD = Build(START, END, "job")
TIB = 2**40

DASH = """
WITH responses AS (
  SELECT co.student_number, co.school, r.assessment_id, r.response_type
  FROM `teamster-332318.kipptaf_extracts.enrollments` AS co
  LEFT JOIN `teamster-332318.kipptaf_assessments.response_rollup` AS r
    ON co.student_number = r.student_number
  WHERE co.is_enrolled_week_end AND r.module_type != 'WPP'
)
SELECT student_number, school, assessment_id, response_type FROM responses
"""
CUBE = "SELECT 1 AS `v__lea_student_identifier` FROM `teamster-332318.m.fct` AS f"
ROWS = RowSpec(
    grain=[
        ColumnPair("student_number", "lea_student_identifier"),
        ColumnPair("assessment_id", "source_assessment_id"),
        ColumnPair("response_type", "response_type"),
    ],
    values=[],
)
COMPARISON = Comparison(
    id="mastery",
    measure="pct",
    dims=[ColumnPair("school", "abbreviation")],
    rows=ROWS,
)
CFG = ViewConfig(view="v", fact="m.fct", comparisons=[COMPARISON])
GROUP = Group("mastery", (("abbreviation", "BOLD"),), "cube_only", 5, 3)


def _side(bucket="cube_only"):
    sides = pipeline.RowSides(
        cube=AsOf(CUBE, frozenset({"m.fct"}), frozenset()),
        dashboard=AsOf(DASH, frozenset(), frozenset()),
        cube_rows_sql=CUBE,
        columns=["lea_student_identifier", "source_assessment_id", "response_type"],
    )
    return trace._Side(CFG, COMPARISON, sides, BUILD, bucket)


def _step_id(text):
    q = Query(DASH, frozenset({"student_number", "assessment_id", "response_type"}))
    return next(s.id for s in q.steps("dashboard") if text in s.label)


class FakeWarehouse:
    """Answers each trace query from `answer(sql)`; prices nothing."""

    def __init__(self, answer):
        self.answer = answer
        self.ran: list[str] = []

    def estimate(self, sql):
        return 0.0

    def refuse_past_caps(self, usd):
        pass

    def rows(self, sql):
        self.ran.append(sql)
        return self.answer(sql)

    def table(self, dataset, name):
        return TableInfo("TABLE", None)


def _row(step_id, n, school="BOLD"):
    return {
        "bucket": "cube_only",
        "abbreviation": school,
        "step_id": step_id,
        "n_rows": n,
    }


def _trace(answer, *, levels=0, manifest=None, wh=None):
    wh = wh or FakeWarehouse(answer)
    found = trace._trace_bucket(
        _side(),
        [GROUP],
        wh=wh,
        manifest=manifest,
        levels=levels,
        end_tables=set(),
        moved={},
    )
    return found[trace.item_key(GROUP)], wh


def test_rows_one_step_recovers_are_attributed_and_prove_the_item():
    wpp = _step_id("module_type")

    found, _ = _trace(lambda sql: [_row(wpp, 5), _row(f"+{wpp}", 5)])

    assert found.proven
    assert found.cause() == [
        {
            "side": "dashboard",
            "step": wpp,
            "label": "responses: r.module_type <> 'WPP'",
            "n_rows": 5,
        }
    ]
    assert found.evidence() == ("responses: r.module_type <> 'WPP': <10 rows",)


def test_rows_two_steps_recover_stay_unattributed():
    wpp, week = _step_id("module_type"), _step_id("is_enrolled_week_end")

    found, _ = _trace(
        lambda sql: [
            _row(wpp, 2),
            _row("*", 3),
            _row(f"+{wpp}", 5),
            _row(f"+{week}", 3),
        ]
    )

    assert not found.proven
    assert found.steps == {wpp: 2} and found.many == 3
    assert found.evidence()[-1] == (
        "<10 rows unattributed: <10 recovered by more than one step "
        "(responses: r.module_type <> 'WPP', responses: co.is_enrolled_week_end)"
    )


def test_rows_no_step_recovers_stay_unattributed():
    found, _ = _trace(lambda sql: [_row("", 5)])

    assert not found.proven and found.none == 5
    assert found.cause() == []
    assert found.evidence() == ("<10 rows unattributed: <10 recovered by no step",)


def test_trace_queries_select_no_grain_column():
    _, wh = _trace(lambda sql: [_row("", 5)])

    (sql,) = wh.ran
    outer = sql.rsplit("-- outer", 1)[1]
    assert outer.startswith(
        "\nSELECT bucket, abbreviation, step_id, COUNT(*) AS n_rows"
    )
    for column in ("student_number", "assessment_id", "lea_student_identifier"):
        assert column not in outer


def test_a_level_past_the_cap_refuses_before_it_runs():
    client = _DryClient(nbytes=TIB)
    wh = Warehouse(client=client)

    with (
        wh.budget(1.0),
        pytest.raises(CostCapError, match="would pass the \\$1.00 cap"),
    ):
        _trace(None, wh=wh)
    assert all(dry for _, dry in client.queries)


def test_a_level_past_the_daily_cap_refuses(tmp_path):
    wh = Warehouse(client=_DryClient(nbytes=TIB // 4))
    wh.configure_local(tmp_path, daily_cap=1.0)

    with pytest.raises(CostCapError, match="daily cap"):
        _trace(None, wh=wh)


class _DryClient:
    def __init__(self, nbytes):
        self.nbytes = nbytes
        self.queries: list[tuple[str, bool]] = []

    def query(self, sql, job_config=None):
        dry = bool(job_config and job_config.dry_run)
        self.queries.append((sql, dry))
        return type("Job", (), {"total_bytes_processed": self.nbytes, "result": list})()


def _manifest(tmp_path, compiled):
    nodes = {
        "model.kipptaf.response_rollup": {
            "name": "response_rollup",
            "database": "teamster-332318",
            "schema": "kipptaf_assessments",
            "alias": "response_rollup",
            "config": {"materialized": "table"},
            "depends_on": {"nodes": []},
            "compiled_code": compiled,
        }
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"nodes": nodes}))
    return trace.Manifest(path)


def test_missing_compiled_sql_refuses_with_the_command_that_writes_it(tmp_path):
    wh = FakeWarehouse(lambda sql: pytest.fail("no query runs"))

    with pytest.raises(pipeline.Refusal) as caught:
        _trace(None, levels=2, manifest=_manifest(tmp_path, ""), wh=wh)

    message = str(caught.value)
    assert "no compiled SQL for response_rollup" in message
    assert trace.compile_command(["response_rollup"]) in message
    assert "--target prod --target-path target/prod" in message
    assert wh.ran == []


def test_a_missing_manifest_refuses(tmp_path):
    with pytest.raises(pipeline.Refusal, match="no dbt manifest"):
        trace.Manifest(tmp_path / "nope.json")


ROLLUP = (
    "select student_number, assessment_id, response_type, module_type "
    "from `teamster-332318`.`raw`.`responses` where not is_replacement"
)


def test_descends_into_a_table_its_steps_explain(tmp_path):
    def answer(sql):
        if "'?0'" in sql:
            return [_row("+?0", 5)]
        if "response_rollup/main" in sql:
            step = next(s for s in sql.split("'") if s.startswith("dashboard:response"))
            return [_row(step, 5), _row(f"+{step}", 5)]
        return [_row("", 5)]

    found, wh = _trace(answer, levels=1, manifest=_manifest(tmp_path, ROLLUP))

    assert found.proven
    (cause,) = found.cause()
    assert cause["label"] == "response_rollup/main: NOT is_replacement"
    assert cause["step"] == "dashboard:response_rollup/main:1"
    level0, screen, level1 = wh.ran
    # The table is read as of the build start, inside the side's own SQL, and
    # its unrelaxed SQL is checked for rows it already returns.
    assert "FOR SYSTEM_TIME AS OF" in level1 and "'!response_rollup'" in level1
    # Rows the side's own steps explained are left out a level down; here
    # none were.
    assert " x0 AS" not in level1


def test_rows_left_at_the_deepest_level_are_below_its_tables(tmp_path):
    found, _ = _trace(lambda sql: [_row("", 5)], levels=0)
    assert found.below == ()

    def answer(sql):
        if "'?0'" in sql:
            return [_row("+?0", 5)]
        return [_row("", 5)]

    found, _ = _trace(answer, levels=1, manifest=_manifest(tmp_path, ROLLUP))

    assert found.below == ()
    assert "recovered by no step" in found.evidence()[-1]


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


def test_rows_the_unrelaxed_sql_already_returns_are_never_attributed():
    found, wh = _trace(lambda sql: [_row("!dashboard", 5), _row("+!dashboard", 5)])

    assert "'!dashboard' AS step_id" in wh.ran[0]
    assert not found.proven and found.unreproduced == {"dashboard": 5}
    assert found.evidence() == (
        "<10 rows unattributed: <10 already returned by the dashboard SQL with no "
        "step neutralized",
    )


def test_a_table_whose_compiled_sql_does_not_run_is_skipped_and_named(tmp_path):
    class Stale(FakeWarehouse):
        def estimate(self, sql):
            if "raw.responses`" in sql and "?0" not in sql and "!" not in sql:
                raise BadRequest("Unrecognized name: quarter")
            return 0.0

    wh = Stale(lambda sql: [_row("", 5)])

    found, _ = _trace(None, levels=1, manifest=_manifest(tmp_path, ROLLUP), wh=wh)

    assert found.below == ("response_rollup",)
    assert "(below response_rollup)" in found.evidence()[-1]
    assert len(wh.ran) == 1  # nothing to screen
