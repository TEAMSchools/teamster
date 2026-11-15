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
