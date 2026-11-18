import json
from dataclasses import replace

from cube_validation import pipeline
from cube_validation.config import Comparison
from cube_validation.reconcile import Group


def _slice() -> pipeline.Sides:
    return pipeline.Sides(
        cube_tables={"m.fct"},
        live={"g.sheet"},
        cells=[pipeline.Cell("c", "{}", "X", 1.0, 2.0, "differs", (("school", "X"),))],
        groups=[
            Group(
                "c",
                (("school", ""),),
                "cube_only",
                3,
                2,
                ("school",),
                cut_rows=(("{}", 3, 0), ('{"Region": "Miami"}', 1, 0)),
            )
        ],
        sql={"c": ("SELECT d", "SELECT c")},
        fingerprints={"c": {"cube": "1", "dashboard": "2"}},
        moved={"m.dim": False},
        cell_sql={"c": {"{}": ["d", "c"]}},
        cell_sql_usd={"c": {"{}": [0.1, 0.2]}},
        students={"c": {("{}", ("X",)): 12}},
    )


def test_a_comparison_slice_survives_json():
    s = _slice()

    back = pipeline.Sides.from_json(json.loads(json.dumps(s.to_json())))

    assert back == s
    assert back.groups[0].cut_rows == (("{}", 3, 0), ('{"Region": "Miami"}', 1, 0))


def test_merging_slices_adds_every_part():
    a = _slice()
    b = pipeline.Sides(
        cube_tables={"m.dim"},
        cells=[pipeline.Cell("d", "{}", "Y", 1.0, 1.0, "pass", ())],
        fingerprints={"d": {"cube": "3", "dashboard": "4"}},
        moved={"m.other": True},
    )

    a.merge(b)

    assert a.cube_tables == {"m.fct", "m.dim"}
    assert [c.comparison for c in a.cells] == ["c", "d"]
    assert set(a.fingerprints) == {"c", "d"}
    assert a.moved == {"m.dim": False, "m.other": True}


def test_a_changed_comparison_entry_changes_its_checkpoint_fingerprint():
    a = Comparison(id="c", measure="m", decimals=2)
    fp = {"cube": "1", "dashboard": "2"}

    assert pipeline.checkpoint_fingerprint(a, fp) == pipeline.checkpoint_fingerprint(
        a, dict(fp)
    )
    assert pipeline.checkpoint_fingerprint(a, fp) != pipeline.checkpoint_fingerprint(
        replace(a, decimals=3), fp
    )
    assert pipeline.checkpoint_fingerprint(a, fp) != pipeline.checkpoint_fingerprint(
        a, {**fp, "cube": "9"}
    )


def test_adding_a_reduce_makes_the_comparison_stale():
    from cube_validation import latest
    from cube_validation.config import ColumnPair, RowSpec, ViewConfig

    rows = RowSpec(grain=[ColumnPair("student", "lea")], values=[ColumnPair("v", "vc")])
    plain = Comparison(
        id="c", measure="m", dashboard_view="d.t", rows=rows, confirmed=True
    )
    reduced = replace(
        plain, rows=replace(rows, reduce={"rule": "latest", "by": "calendardate"})
    )
    cfg = ViewConfig(view="v", fact="kipptaf_marts.fct_f", comparisons=[plain])

    assert latest.entry_fingerprint(plain) != latest.entry_fingerprint(reduced)
    assert pipeline.dashboard_rows_sql(cfg, plain) != pipeline.dashboard_rows_sql(
        cfg, reduced
    )


def _sheet_comparisons():
    from cube_validation.config import ColumnPair, RowSpec, ViewConfig

    sheet = Comparison(
        id="c",
        measure="m",
        dashboard_view="d.t",
        sheet_query="AVG(score)",
        dims=[ColumnPair("school", "abbreviation"), ColumnPair("day", "date")],
        filters={"Region": ColumnPair("region", "region_c")},
        defaults={"Region": "Newark"},
        cuts=[{}, {"Region": ["Miami", "Camden"]}],
        dashboard_filters=[
            {"dashboard": "future", "operator": "equals", "values": ["no"]}
        ],
        dashboard_columns={"half": "score / 2"},
    )
    template = Comparison(
        id="t",
        measure="m",
        dashboard_view="d.t",
        sheet_query_sql=(
            "SELECT {dims}, SUM(n) AS value FROM ({rows}) WHERE {where} GROUP BY {dims}"
        ),
        dims=[ColumnPair("school", "abbreviation")],
    )
    rows = Comparison(
        id="r",
        measure="m",
        dashboard_view="d.t",
        sheet_query="AVG(score)",
        dims=[ColumnPair("school", "abbreviation")],
        filters={"Region": ColumnPair("region", "region_c")},
        cuts=[{}, {"Region": "Miami"}],
        dashboard_filters=[
            {"dashboard": "future", "operator": "equals", "values": ["no"]}
        ],
        rows=RowSpec(
            grain=[ColumnPair("student", "lea"), ColumnPair("day", "date")],
            values=[ColumnPair("score", "score_c")],
            dashboard_scope=[
                {"dashboard": "in_scope", "operator": "equals", "values": [True]}
            ],
            reduce={"rule": "latest", "by": "updated"},
        ),
    )
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[sheet], time_dimension="date")
    return cfg, sheet, template, rows


def test_sheet_query_takes_other_rows_and_keeps_its_fingerprint():
    # The SQL and fingerprints as they stood before `rows` existed: saved
    # rebuild checks and results are keyed on them.
    cfg, sheet, template, _ = _sheet_comparisons()
    rows = "SELECT * FROM (SELECT *, score / 2 AS half FROM `teamster-332318`.`d`.`t`)"
    base = (
        "SELECT school, DATE(day) AS day, AVG(score) AS value "
        f"FROM ({rows}) WHERE CAST(region AS STRING) IN ('Newark') "
        "AND CAST(future AS STRING) IN ('no') GROUP BY 1, 2"
    )
    template_rows = "SELECT * FROM `teamster-332318`.`d`.`t`"
    template_base = (
        f"SELECT school, SUM(n) AS value FROM ({template_rows}) WHERE TRUE "
        "GROUP BY school"
    )

    assert pipeline.sheet_query(cfg, sheet, {}) == base
    assert pipeline.sheet_query(cfg, sheet, {}, rows=None) == base
    assert pipeline.sheet_query(cfg, template, {}) == template_base
    assert pipeline.sheet_query_fingerprint(cfg, sheet) == (
        "a7316550376a45571c304fd561c44546ecc3b187fd923cddce8a0ecd1ad40de9"
    )
    assert pipeline.sheet_query_fingerprint(cfg, template) == (
        "a57343fcbda18df23cfc6bf562572585c253a53f6c4b76fdb23fdc042659ba16"
    )
    assert pipeline.sheet_query(cfg, sheet, {}, rows="SELECT 1") == base.replace(
        rows, "SELECT 1"
    )
    assert pipeline.sheet_query(
        cfg, template, {}, rows="SELECT 1"
    ) == template_base.replace(template_rows, "SELECT 1")


def test_dashboard_rows_keep_their_sql_beside_the_scoped_rows():
    # The reconcile's rows as they stood before `dashboard_scoped_rows_sql`
    # shared their WHERE and ranking.
    cfg, _, _, rows = _sheet_comparisons()

    assert pipeline.dashboard_rows_sql(cfg, rows) == (
        "SELECT * EXCEPT (__reduce_by) FROM (SELECT student, DATE(day) AS day, "
        "score, school, region, COALESCE(CAST(future AS STRING) IN ('no'), FALSE) "
        "AS __df0, updated AS __reduce_by FROM `teamster-332318`.`d`.`t` "
        "WHERE (TRUE) AND (in_scope IN (TRUE))) QUALIFY RANK() OVER "
        "(PARTITION BY student, day, region ORDER BY (__df0 AND TRUE) DESC, "
        "__reduce_by DESC) = 1"
    )
    assert pipeline.dashboard_scoped_rows_sql(cfg, rows) == (
        "SELECT * EXCEPT (__reduce_by) FROM (SELECT *, updated AS __reduce_by "
        "FROM `teamster-332318`.`d`.`t` WHERE (TRUE) AND (in_scope IN (TRUE))) "
        "QUALIFY RANK() OVER (PARTITION BY student, DATE(day), region ORDER BY "
        "(COALESCE(CAST(future AS STRING) IN ('no'), FALSE) AND TRUE) DESC, "
        "__reduce_by DESC) = 1"
    )
