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
    assert by_name["a.m1"].kind == "cube"
    assert by_name["v.m1"].kind == "view"
    assert by_name["a.m1"].cube == "a"
    assert by_name["a.m1"].title == "M1"
    assert by_name["a.m1"].sql == "sum(`t`.x)"
    assert by_name["a.m1"].fact == "fct_a"
    assert by_name["a.m1"].sql_fingerprint


def test_same_sql_groups_equal_expressions_on_one_fact():
    cube = MetaCube(
        [_cube("a", ["m"]), _cube("b", ["m"]), _cube("c", ["m"])],
        {
            "a.m": ("fct_a", "sum(`t`.x)"),
            "b.m": ("fct_a", "SUM(`t`.x)"),
            "c.m": ("fct_a", "sum(`t`.y)"),
        },
    )

    groups = builder.same_sql(builder.members(cube))

    assert [sorted(m.name for m in g) for g in groups] == [["a.m", "b.m"]]


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


def test_same_sql_ignores_a_view_repeating_its_cube():
    cube = MetaCube(
        [_cube("a", ["m"]), _cube("v", ["m"], kind="view")],
        {"a.m": ("fct_a", "sum(`t`.x)"), "v.m": ("fct_a", "sum(`t`.x)")},
    )

    assert builder.same_sql(builder.members(cube)) == []


def test_same_name_finds_count_students_on_every_cube():
    found = builder.members(_students())

    hits = builder.same_name(found, "count_students")

    assert sorted(m.cube for m in hits) == ["a", "b", "c", "d"]
    assert len({m.fact for m in hits}) == 4
    assert len({m.sql for m in hits}) == 4
    assert builder.same_name(found, "nope") == []


def test_members_command_writes_json_and_prints_groups(monkeypatch, tmp_path, capsys):
    cube = MetaCube(
        [_cube("a", ["m", "bad"]), _cube("b", ["m"])],
        {
            "a.m": ("fct_a", "sum(`t`.x)"),
            "a.bad": ("fct_a", None),
            "b.m": ("fct_a", "sum(`t`.x)"),
        },
    )
    monkeypatch.setattr(cli, "make_cube", lambda url, secret, email: cube)
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setenv("CUBE_REST_URL", "http://cube.test/cubejs-api/v1")
    monkeypatch.setenv("CUBE_API_SECRET", "not-a-secret")
    monkeypatch.setenv("CUBE_VALIDATION_EMAIL", "analyst@example.org")

    assert cli.main(["members"]) == 0

    written = json.loads((tmp_path / "cache" / "members.json").read_text())
    assert sorted(m["name"] for m in written["members"]) == ["a.m", "b.m"]
    assert written["skipped"] == [{"name": "a.bad", "reason": "cannot compile a.bad"}]
    captured = capsys.readouterr()
    assert "a.m" in captured.out and "b.m" in captured.out
    assert "skipped a.bad: cannot compile a.bad" in captured.err


def test_measure_expression_keeps_a_from_inside_a_function():
    sql = (
        "SELECT count(distinct EXTRACT(YEAR FROM `t`.d)) `v__m`, "
        "TRIM(BOTH ' ' FROM 'a from b') x\nFROM kipptaf_marts.fct_a AS `t`"
    )

    assert pipeline._measure_expression(sql, "v", "m") == (
        "count(distinct EXTRACT(YEAR FROM `t`.d)) , TRIM(BOTH ' ' FROM 'a from b') x"
    )
