import json

# trunk-ignore(pyright/reportAttributeAccessIssue): conftest.py registers cube_validation
from cube_validation import builder, cli, pipeline

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import Compiled, CubeError


class MetaCube:
    """A Cube whose `/meta` lists `cubes` and whose measures compile from `exprs`."""

    def __init__(self, cubes, exprs):
        self._cubes = cubes
        self.exprs = exprs
        self.compiled_queries: list[dict] = []

    def meta(self):
        return {"cubes": self._cubes}

    def compiled(self, query):
        self.compiled_queries.append(query)
        (member,) = query["measures"]
        cube, short = member.split(".", 1)
        fact, expr = self.exprs[member]

        if expr is None:
            raise CubeError(f"cannot compile {member}")

        sql = f"SELECT {expr} `{cube}__{short}`\nFROM kipptaf_marts.{fact} AS `t`"
        return Compiled(sql, [], [])


def _cube(name, measures, kind=None, **extra):
    entry = {
        "name": name,
        "measures": [{"name": f"{name}.{m}", "title": m.title()} for m in measures],
        "dimensions": [],
        "segments": [],
        **extra,
    }
    if kind:
        entry["type"] = kind
    return entry


def _students():
    cubes = [
        _cube("a", ["count_students"]),
        _cube("b", ["count_students"], kind="cube"),
        _cube("c", ["count_students"]),
        _cube("d", ["count_students"]),
    ]
    exprs = {
        f"{c}.count_students": (f"fct_{c}", f"count(distinct `t`.{c}_id)")
        for c in "abcd"
    }
    return MetaCube(cubes, exprs)


def test_members_compiles_every_measure_once():
    cube = MetaCube(
        [_cube("a", ["m1", "m2"]), _cube("v", ["m1"], kind="view")],
        {
            "a.m1": ("fct_a", "sum(`t`.x)"),
            "a.m2": ("fct_a", "count(`t`.x)"),
            "v.m1": ("fct_a", "sum(`t`.x)"),
        },
    )

    found = builder.members(cube)

    assert sorted(q["measures"][0] for q in cube.compiled_queries) == [
        "a.m1",
        "a.m2",
        "v.m1",
    ]
    by_name = {m.name: m for m in found}
    assert by_name["a.m1"].kind == "measure"
    assert by_name["v.m1"].kind == "measure"
    assert not by_name["a.m1"].view
    assert by_name["v.m1"].view
    assert by_name["a.m1"].cube == "a"
    assert by_name["a.m1"].title == "M1"
    assert by_name["a.m1"].sql == "sum(`t`.x)"
    assert by_name["a.m1"].fact == "fct_a"
    assert by_name["a.m1"].sql_fingerprint


def test_same_sql_groups_equal_expressions_on_one_fact():
    cube = MetaCube(
        [_cube("a", ["m"]), _cube("b", ["n"]), _cube("c", ["o"])],
        {
            "a.m": ("fct_a", "sum(`t`.x)"),
            "b.n": ("fct_a", "SUM(`t`.x)"),
            "c.o": ("fct_a", "sum(`t`.y)"),
        },
    )

    groups = builder.same_sql(builder.members(cube))

    assert [sorted(m.name for m in g) for g in groups] == [["a.m", "b.n"]]


def test_same_sql_does_not_group_equal_expressions_on_different_facts():
    cube = MetaCube(
        [_cube("a", ["m"]), _cube("b", ["m"])],
        {"a.m": ("fct_a", "sum(`t`.x)"), "b.m": ("fct_b", "sum(`t`.x)")},
    )

    assert builder.same_sql(builder.members(cube)) == []


def test_members_skips_a_measure_that_fails_to_compile():
    cube = MetaCube(
        [_cube("a", ["good", "bad", "also_good"])],
        {
            "a.good": ("fct_a", "sum(`t`.x)"),
            "a.bad": ("fct_a", None),
            "a.also_good": ("fct_a", "count(`t`.x)"),
        },
    )
    skipped: list[dict] = []

    found = builder.members(cube, skipped)

    assert [m.name for m in found] == ["a.good", "a.also_good"]
    assert skipped == [{"name": "a.bad", "reason": "cannot compile a.bad"}]


def test_same_sql_ignores_one_measure_repeated_on_several_views():
    cube = MetaCube(
        [_cube(v, ["m"], kind="view") for v in ("v1", "v2", "v3")],
        {f"{v}.m": ("fct_a", "sum(`t`.x)") for v in ("v1", "v2", "v3")},
    )

    assert builder.same_sql(builder.members(cube)) == []


def test_same_sql_groups_different_names_on_views_over_one_fact():
    cube = MetaCube(
        [
            _cube("v1", ["count_tardy"], kind="view"),
            _cube("v2", ["tardy_count"], kind="view"),
            _cube("v3", ["count_tardy"], kind="view"),
        ],
        {
            "v1.count_tardy": ("fct_a", "sum(`t`.x)"),
            "v2.tardy_count": ("fct_a", "sum(`t`.x)"),
            "v3.count_tardy": ("fct_a", "sum(`t`.x)"),
        },
    )

    groups = builder.same_sql(builder.members(cube))

    assert [sorted(m.name for m in g) for g in groups] == [
        ["v1.count_tardy", "v2.tardy_count", "v3.count_tardy"]
    ]


def test_same_name_finds_count_students_on_every_cube():
    found = builder.members(_students())

    hits = builder.same_name(found, "count_students")

    assert sorted(m.cube for m in hits) == ["a", "b", "c", "d"]
    assert len({m.fact for m in hits}) == 4
    assert len({m.sql for m in hits}) == 4
    assert builder.same_name(found, "nope") == []


def test_members_command_writes_json_and_prints_groups(monkeypatch, tmp_path, capsys):
    cube = MetaCube(
        [_cube("a", ["m", "bad"]), _cube("b", ["n"])],
        {
            "a.m": ("fct_a", "sum(`t`.x)"),
            "a.bad": ("fct_a", None),
            "b.n": ("fct_a", "sum(`t`.x)"),
        },
    )
    monkeypatch.setattr(cli, "make_cube", lambda url, secret, email: cube)
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setenv("CUBE_REST_URL", "http://cube.test/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_SECRET", "not-a-secret")
    monkeypatch.setenv("CUBE_VALIDATION_EMAIL", "analyst@example.org")

    assert cli.main(["members"]) == 0

    written = json.loads((tmp_path / "cache" / "members.json").read_text())
    assert sorted(m["name"] for m in written["members"]) == ["a.m", "b.n"]
    assert written["skipped"] == [{"name": "a.bad", "reason": "cannot compile a.bad"}]
    captured = capsys.readouterr()
    assert "a.m" in captured.out and "b.n" in captured.out
    assert "skipped a.bad: cannot compile a.bad" in captured.err


def test_measure_expression_keeps_a_from_inside_a_function():
    sql = (
        "SELECT count(distinct EXTRACT(YEAR FROM `t`.d)) `v__m`, "
        "TRIM(BOTH ' ' FROM 'a from b') x\nFROM kipptaf_marts.fct_a AS `t`"
    )

    assert pipeline._measure_expression(sql, "v", "m") == (
        "count(distinct EXTRACT(YEAR FROM `t`.d)) , TRIM(BOTH ' ' FROM 'a from b') x"
    )


def _twb(sheets: str = "", columns: str = "", extra_sheet_cols: str = "") -> str:
    return f"""<?xml version='1.0' encoding='utf-8' ?>
<workbook>
  <datasources>
    <datasource name='ds'>
      <column datatype='string' name='[tardy_code]' role='dimension'>
        <calculation class='categorical-bin' column='[code]'>
          <bin value='&quot;Tardy&quot;'><value>&quot;T&quot;</value>
            <value>&quot;ET&quot;</value></bin>
        </calculation>
      </column>
      {columns}
    </datasource>
  </datasources>
  <worksheets>{sheets}</worksheets>
</workbook>"""


def _sheet(name: str, deps: str, rows: str = "", cols: str = "", body: str = "") -> str:
    return f"""<worksheet name='{name}'><table><view>
      <datasource-dependencies datasource='ds'>{deps}</datasource-dependencies>
      {body}</view>
      <rows>{rows}</rows><cols>{cols}</cols></table></worksheet>"""


_CALC_COLUMNS = """
  <column caption='Tardy Rate' name='[Calc_1]' role='measure'>
    <calculation class='tableau' formula='SUM(IIF([tardy_code] = 1, 1, 0))' />
  </column>
  <column caption='Open Link' name='[Calc_2]' role='dimension'>
    <calculation class='tableau' formula='"https://x.test/" + [school]' />
  </column>
  <column caption='Mine' name='[Calc_3]' role='dimension'>
    <calculation class='tableau' formula='[owner] = USERNAME()' />
  </column>
  <column caption='Tardy Group' name='[Calc_4]' role='dimension'>
    <calculation class='tableau' formula='IF [tardy_code] = "T" THEN 1 END' />
  </column>
  <column caption='Cap' name='[Parameter 1]' param-domain-type='any' role='measure'>
    <calculation class='tableau' formula='5' />
  </column>
"""


def _dep(name: str, deriv: str, abbr: str, role: str = "dimension", cap: str = ""):
    caption = f" caption='{cap}'" if cap else ""
    return (
        f"<column{caption} name='[{name}]' role='{role}' />"
        f"<column-instance column='[{name}]' derivation='{deriv}' "
        f"name='[{abbr}:{name}:nk]' pivot='key' type='nominal' />"
    )


def _workbook() -> str:
    one = _sheet(
        "One",
        _dep("Calc_1", "User", "usr", "measure", "Tardy Rate")
        + _dep("school", "None", "none")
        + _dep("Calc_2", "User", "usr", cap="Open Link")
        + _dep("Parameter 1", "None", "none", "measure", "Cap")
        + "<column name='[Parameter 1]' param-domain-type='any' role='measure' />",
        rows="([ds].[none:school:nk] * [ds].[usr:Calc_2:nk])",
        cols="[ds].[usr:Calc_1:nk]",
        body="<filter class='categorical' column='[ds].[none:region:nk]'>"
        "<groupfilter function='member' level='[none:region:nk]' member='&quot;A&quot;' />"
        "</filter>",
    )
    two = _sheet(
        "Two",
        _dep("Calc_1", "User", "usr", "measure", "Tardy Rate")
        + _dep("Calc_3", "User", "usr", cap="Mine")
        + _dep("Calc_4", "User", "usr", cap="Tardy Group")
        + _dep("school", "None", "none")
        + _dep("membership", "Sum", "sum", "measure"),
        rows="[ds].[usr:Calc_4:nk]",
        cols="[ds].[usr:Calc_1:nk] [ds].[sum:membership:qk]",
        body="<filter class='categorical' column='[ds].[none:school:nk]'>"
        "<groupfilter function='level-members' level='[none:school:nk]' />"
        "</filter>"
        "<filter class='categorical' column='[ds].[usr:Calc_3:nk]'>"
        "<groupfilter function='member' level='[usr:Calc_3:nk]' member='true' />"
        "</filter>",
    )
    return _twb(one + two, _CALC_COLUMNS)


def _by_name(uses) -> dict:
    return {u.caption: u for u in uses}


def test_inventory_lists_each_field_once_with_all_its_sheets():
    uses = builder.workbook_inventory(_workbook())

    assert len({u.caption for u in uses}) == len(uses)
    by = _by_name(uses)
    assert by["Tardy Rate"].role == "measure"
    assert by["Tardy Rate"].sheets == ("One", "Two")
    assert by["school"].role == "cut"
    assert by["school"].sheets == ("One", "Two")
    assert by["region"].role == "filter"
    assert by["region"].sheets == ("One",)
    assert by["SUM(membership)"].role == "measure"
    assert by["SUM(membership)"].formula == "SUM([membership])"
    assert by["Tardy Group"].role == "cut"


def test_inventory_expands_code_groups_in_formulas():
    by = _by_name(builder.workbook_inventory(_workbook()))

    assert "[tardy_code: Tardy = T, ET]" in by["Tardy Rate"].formula
    assert "[tardy_code: Tardy = T, ET]" in by["Tardy Group"].formula


def test_inventory_marks_parameters_urls_and_identity_fields_presentation():
    by = _by_name(builder.workbook_inventory(_workbook()))

    assert by["Cap"].role == "parameter"
    assert by["Cap"].presentation
    assert by["Open Link"].presentation
    assert by["Mine"].presentation
    assert not by["Tardy Rate"].presentation
    assert not by["school"].presentation


def test_inventory_survives_odd_xml():
    xml = _twb(
        "<worksheet><table><view/></table></worksheet>"
        "<worksheet name='Empty'/>"
        + _sheet("Odd", "<column-instance derivation='Sum'/>", rows="[bad ref]")
    )

    assert builder.workbook_inventory(xml) == []


def test_inventory_workbook_command_prints_json(tmp_path, capsys):
    path = tmp_path / "w.twb"
    path.write_text(_workbook(), encoding="utf-8")

    assert cli.main(["inventory-workbook", str(path)]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert {u["caption"] for u in printed} >= {"Tardy Rate", "school", "region"}
    assert all(isinstance(u["sheets"], list) for u in printed)


def test_inventory_workbook_command_refuses_a_missing_or_broken_file(tmp_path, capsys):
    assert cli.main(["inventory-workbook", str(tmp_path / "none.twb")]) == 1
    broken = tmp_path / "b.twb"
    broken.write_text("<workbook", encoding="utf-8")

    assert cli.main(["inventory-workbook", str(broken)]) == 1
    assert "refused" in capsys.readouterr().err


def test_inventory_keeps_each_formula_of_calcs_sharing_a_caption():
    xml = f"""<workbook><datasources>
      <datasource name='a'><column caption='Rate' name='[Calc_A]' role='measure'>
        <calculation class='tableau' formula='SUM([x])' /></column></datasource>
      <datasource name='b'><column caption='Rate' name='[Calc_B]' role='measure'>
        <calculation class='tableau' formula='AVG([y])' /></column>
        <column caption='Rate' name='[raw]' role='measure' /></datasource>
    </datasources><worksheets>
      {
        _sheet(
            "S",
            _dep("Calc_A", "User", "usr", "measure", "Rate")
            + _dep("Calc_B", "User", "usr", "measure", "Rate")
            + _dep("raw", "Sum", "sum", "measure", "Rate"),
            cols="[a].[usr:Calc_A:nk] [b].[usr:Calc_B:nk] [b].[sum:raw:qk]",
        )
    }
    </worksheets></workbook>"""

    formulas = {u.name: u.formula for u in builder.workbook_inventory(xml)}

    assert formulas == {
        "Calc_A": "SUM([x])",
        "Calc_B": "AVG([y])",
        "SUM(raw)": "SUM([raw])",
    }


def test_inventory_shows_the_formula_inside_an_aggregated_calc():
    xml = _twb(
        _sheet(
            "S",
            _dep("Calc_1", "Sum", "sum", "measure", "Tardy Rate"),
            cols="[ds].[sum:Calc_1:qk]",
        ),
        _CALC_COLUMNS,
    )

    (use,) = builder.workbook_inventory(xml)

    assert use.name == "SUM(Calc_1)"
    assert use.caption == "SUM(Tardy Rate)"
    assert use.formula.startswith("SUM(SUM(IIF(")
    assert "[tardy_code: Tardy = T, ET]" in use.formula


def test_inventory_shows_the_groups_of_a_code_group_on_a_shelf():
    xml = _twb(
        _sheet(
            "S", _dep("tardy_code", "None", "none"), rows="[ds].[none:tardy_code:nk]"
        )
    )

    (use,) = builder.workbook_inventory(xml)

    assert use.role == "cut"
    assert use.formula == "Tardy = T, ET"


_CATALOG = """# Gap catalog

## Other Dash (`other`)

### Measures

| metric | agg | source field / formula (trimmed) | dashboards | status | where | regions |
| ------ | --- | -------------------------------- | ---------- | ------ | ----- | ------- |
| Wrong Rate | Avg | `x` | d | cube-covered | `a.wrong` | all |

## DDI Suite (`ddi_suite`)

- workbook: DDI Suite

### Measures

| metric | agg | source field / formula (trimmed) | dashboards | status | where | regions |
| ------ | --- | -------------------------------- | ---------- | ------ | ----- | ------- |
| Mastery rate (`is_mastery_int`), overall/standard toggle | Avg | `x` | d | **cube-covered** | `student_assessment_scores.pct_proficient` / `is_mastery` | all |
| Walkthrough Rate | Avg | `y` | d | mart-ready | `fct_staff_observation_scores.score_value` | all |
| Unused Count | Sum | `z` | d | cube-covered | `a.unused` | all |

### Dimensions

| dimension | used as | status | where | regions |
| --------- | ------- | ------ | ----- | ------- |
| Student Tier (Bucket 1/2), Is SIPPS | rows | cube-covered | `student_tiers.tier` | all |

### Notes

| not | a | table |
"""


def _member(name, title=""):
    cube, short = name.split(".", 1)
    return builder.Member(
        name=name,
        cube=cube,
        kind="measure",
        title=title,
        description="",
        sql="",
        sql_fingerprint="",
        fact="",
    )


def _use(caption, role="measure", name=None, presentation=False):
    return builder.FieldUse(
        caption=caption,
        name=name or caption,
        role=role,
        formula="",
        sheets=("S",),
        presentation=presentation,
    )


def test_catalog_rows_reads_the_dashboards_measures_and_dimensions():
    rows = builder.catalog_rows(_CATALOG, "ddi_suite")

    assert [(r["kind"], r["status"]) for r in rows] == [
        ("measure", "**cube-covered**"),
        ("measure", "mart-ready"),
        ("measure", "cube-covered"),
        ("dimension", "cube-covered"),
    ]
    assert (
        rows[0]["field"] == "Mastery rate (`is_mastery_int`), overall/standard toggle"
    )
    assert rows[3]["where"] == "`student_tiers.tier`"
    assert builder.catalog_rows(_CATALOG, "nope") == []


def test_inventory_matches_members_and_flags_disagreements():
    catalog = builder.catalog_rows(_CATALOG, "ddi_suite")
    review = [
        _use("Mastery Rate"),
        _use("Walkthrough Rate"),
        _use("SUM(Tardy Rate)", name="SUM(tardy_rate)"),
        _use("Student Tier", role="cut", name="nj_student_tier"),
    ]
    found = [
        _member("student_assessment_scores.pct_proficient"),
        _member("attendance.tardy_rate", title="Tardy Rate"),
    ]

    rows = {r.field: r for r in builder.inventory(catalog, review, [], found)}

    mastery = rows["Mastery Rate"]
    assert mastery.member == "student_assessment_scores.pct_proficient"
    assert mastery.sources == ("catalog", "review")
    assert mastery.disagreement == ""
    walkthrough = rows["Walkthrough Rate"]
    assert walkthrough.member == ""
    assert walkthrough.disagreement == ""
    tardy = rows["SUM(Tardy Rate)"]
    assert tardy.member == "attendance.tardy_rate"
    assert tardy.sources == ("review",)
    assert tardy.disagreement == "not in catalog"
    assert rows["Student Tier"].kind == "dimension"
    assert rows["Student Tier"].sources == ("catalog", "review")
    only_catalog = rows["Unused Count"]
    assert only_catalog.sources == ("catalog",)
    assert only_catalog.disagreement == (
        "only in catalog; catalog says cube-covered, no member found"
    )


def test_inventory_flags_a_member_the_catalog_says_is_missing():
    catalog = [
        {
            "field": "Tardy Rate",
            "kind": "measure",
            "status": "mart-missing",
            "where": "",
        }
    ]
    found = [_member("attendance.tardy_rate", title="Tardy Rate")]

    (row,) = builder.inventory(catalog, [_use("Tardy Rate")], [], found)

    assert row.member == "attendance.tardy_rate"
    assert row.disagreement == "catalog says mart-missing, member found"


def test_inventory_matches_a_member_by_the_fields_bare_name():
    found = [_member("attendance.nj_tier"), _member("other.nj_tier")]
    review = [_use("Tier", name="nj_tier"), _use("Rate", name="rate")]
    found.append(_member("attendance.rate"))

    rows = {r.field: r for r in builder.inventory([], review, [], found)}

    assert rows["Rate"].member == "attendance.rate"
    assert rows["Tier"].member == "attendance.nj_tier"
    assert "several" not in rows["Tier"].disagreement


def test_inventory_leaves_out_presentation_fields():
    catalog = [
        {"field": "Viewer Url", "kind": "dimension", "status": "x", "where": ""},
    ]
    review = [
        _use("Viewer Url", role="cut", presentation=True),
        _use("Tardy Rate"),
    ]
    asana = [{"field": "viewer url", "status": "open"}]

    rows = builder.inventory(catalog, review, asana, [])

    assert [r.field for r in rows] == ["Tardy Rate"]


def test_inventory_lists_deferred_asana_items_without_planning_them():
    asana = [
        {"field": "Tardy Rate", "status": "open"},
        {"field": "Parent Contact Rate", "status": "deferred"},
        {"field": "Brand New", "status": "open"},
    ]

    rows = {r.field: r for r in builder.inventory([], [_use("Tardy Rate")], asana, [])}

    assert rows["Tardy Rate"].sources == ("review", "asana")
    assert rows["Tardy Rate"].disagreement == "not in catalog"
    assert rows["Parent Contact Rate"].sources == ("asana",)
    assert (
        rows["Parent Contact Rate"].disagreement == "only in asana; deferred in asana"
    )
    assert rows["Brand New"].disagreement == "only in asana"


def test_inventory_attaches_an_asana_item_to_the_catalog_row_it_names():
    catalog = [
        {
            "field": "Unused Count",
            "kind": "measure",
            "status": "mart-ready",
            "where": "",
        }
    ]
    asana = [{"field": "unused count", "status": "open"}]

    (row,) = builder.inventory(catalog, [], asana, [])

    assert row.sources == ("catalog", "asana")
    assert row.disagreement == ""


def test_inventory_command_prints_a_table_then_json(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    catalog = tmp_path / "plan.md"
    catalog.write_text(_CATALOG, encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            [
                {
                    "caption": "Walkthrough Rate",
                    "name": "SUM(w)",
                    "role": "measure",
                    "formula": "",
                    "sheets": ["S"],
                    "presentation": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    asana = tmp_path / "asana.json"
    asana.write_text("[]", encoding="utf-8")
    argv = ["inventory", str(catalog), "ddi_suite", "--review", str(review)]
    argv += ["--asana", str(asana)]

    assert cli.main(argv) == 1
    assert "members" in capsys.readouterr().err

    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "members.json").write_text(
        json.dumps({"members": [], "skipped": []}), encoding="utf-8"
    )

    assert cli.main(argv) == 0

    out = capsys.readouterr().out
    assert "| field | kind | member | sources | disagreement |" in out
    assert "| Walkthrough Rate | measure |  | catalog, review |" in out
    printed = json.loads(out[out.index("[\n") :])
    assert {r["field"] for r in printed} >= {"Walkthrough Rate", "Unused Count"}
    assert printed[0]["sources"] == ["catalog", "review"]


def _dimension(name, title="", **extra):
    return builder.Member(
        name=name,
        cube=name.split(".", 1)[0],
        kind="dimension",
        title=title,
        description="",
        sql="",
        sql_fingerprint="",
        fact="",
        **extra,
    )


def test_members_lists_dimensions_without_compiling_them():
    dims = [{"name": "a.region", "title": "Region", "description": "Where"}]
    cube = MetaCube(
        [_cube("a", ["m"], dimensions=dims)], {"a.m": ("fct_a", "sum(`t`.x)")}
    )

    found = {m.name: m for m in builder.members(cube)}

    assert cube.compiled_queries == [{"measures": ["a.m"]}]
    region = found["a.region"]
    assert (region.kind, region.title, region.description) == (
        "dimension",
        "Region",
        "Where",
    )
    assert (region.sql, region.sql_fingerprint, region.fact) == ("", "", "")


def test_same_sql_ignores_dimensions():
    found = [_dimension("a.region"), _dimension("b.region")]

    assert builder.same_sql(found) == []


def test_inventory_gives_a_dimension_its_backticked_where_member():
    catalog = builder.catalog_rows(_CATALOG, "ddi_suite")
    found = [_dimension("student_tiers.tier", title="Tier")]

    rows = {
        r.field: r
        for r in builder.inventory(
            catalog, [_use("Student Tier", role="cut", name="nj_tier")], [], found
        )
    }

    assert rows["Student Tier"].member == "student_tiers.tier"
    assert rows["Student Tier"].disagreement == ""


def test_inventory_flags_a_cube_covered_dimension_with_no_member():
    catalog = builder.catalog_rows(_CATALOG, "ddi_suite")

    rows = {
        r.field: r
        for r in builder.inventory(
            catalog, [_use("Student Tier", role="cut", name="nj_tier")], [], []
        )
    }

    assert rows["Student Tier"].disagreement == (
        "catalog says cube-covered, no member found"
    )


def test_inventory_does_not_join_on_a_later_fragment_of_a_catalog_cell():
    catalog = builder.catalog_rows(_CATALOG, "ddi_suite")
    review = [_use("Mastery Rate"), _use("Overall Score")]

    rows = {r.field: r for r in builder.inventory(catalog, review, [], [])}

    assert rows["Mastery Rate"].sources == ("catalog", "review")
    assert rows["Overall Score"].sources == ("review",)


def test_inventory_notes_a_catalog_row_joining_several_fields():
    catalog = [
        {
            "field": "Student Tier (Bucket 1/2/Unbucketed), Is Low 25 FL, Is SIPPS",
            "kind": "dimension",
            "status": "mart-ready",
            "where": "",
        }
    ]
    review = [
        _use("Student Tier", role="cut"),
        _use("Is SIPPS", role="cut"),
        _use("Bucket", role="cut"),
    ]

    rows = {r.field: r for r in builder.inventory(catalog, review, [], [])}

    for caption in ("Student Tier", "Is SIPPS"):
        assert rows[caption].sources == ("catalog", "review")
        assert "catalog row matches several fields" in rows[caption].disagreement
    assert rows["Bucket"].sources == ("review",)


def _where_row(field, where, kind="measure"):
    return {"field": field, "kind": kind, "status": "cube-covered", "where": where}


def test_inventory_resolves_a_cube_level_where_name_to_a_view_member():
    found = [_member("student_assessment_scores_view.pct_proficient")]
    catalog = [
        _where_row("Pct Proficient", "`student_assessment_scores.pct_proficient`")
    ]

    (row,) = builder.inventory(catalog, [_use("Pct Proficient")], [], found)

    assert row.member == "student_assessment_scores_view.pct_proficient"
    assert row.disagreement == ""


def test_members_gives_a_view_measure_the_kind_measure():
    cube = MetaCube(
        [_cube("v", ["pct_proficient"], kind="view")],
        {"v.pct_proficient": ("fct_a", "avg(`t`.x)")},
    )

    (found,) = builder.members(cube)

    assert found.kind == "measure"


def test_inventory_resolves_a_dashboard_measure_to_the_measure_not_a_dimension():
    cube = MetaCube(
        [
            _cube(
                "v",
                ["pct_proficient"],
                kind="view",
                dimensions=[{"name": "v.is_mastery", "title": "Is Mastery Int"}],
            )
        ],
        {"v.pct_proficient": ("fct_a", "avg(`t`.x)")},
    )
    found = builder.members(cube)
    use = _use("AVG(Is Mastery Int)", name="AVG(Is Mastery Int)")
    catalog = [_where_row("Is Mastery Int", "`v.pct_proficient`")]

    (row,) = builder.inventory(catalog, [use], [], found)

    assert row.member == "v.pct_proficient"


def test_inventory_resolves_a_where_name_to_a_cube_prefixed_view_member():
    found = [
        _dimension("other_view.region_name"),
        _dimension("v.locations_location_name"),
    ]
    catalog = [_where_row("School", "`locations.location_name`", kind="dimension")]

    (row,) = builder.inventory(catalog, [_use("School", role="cut")], [], found)

    assert row.member == "v.locations_location_name"
    assert row.disagreement == ""


def test_inventory_counts_one_short_name_on_several_views_as_one_member():
    found = [_dimension(f"{v}.grade_level") for v in ("a_view", "b_view", "c_view")]

    (row,) = builder.inventory(
        [], [_use("Grade", role="cut", name="grade_level")], [], found
    )

    assert row.member == "a_view.grade_level"
    assert row.disagreement == "not in catalog"


def test_inventory_notes_different_short_names_matching_one_title():
    found = [
        _dimension("v.school_name", title="School"),
        _dimension("v.location_name", title="School"),
    ]

    (row,) = builder.inventory([], [_use("School", role="cut", name="x")], [], found)

    assert row.member == ""
    assert "several cubes" in row.disagreement
