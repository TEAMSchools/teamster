from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/check_dbt_standard.py"
DOMAIN = {"students", "people", "topline", "extracts"}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_dbt_standard", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_dbt_standard"] = module
    spec.loader.exec_module(module)
    return module


mod = _load()


def model(name, path, parents=(), package="kipptaf", enabled=True) -> dict:
    return {
        "unique_id": f"model.{package}.{name}",
        "resource_type": "model",
        "name": name,
        "package_name": package,
        "original_file_path": path,
        "config": {"enabled": enabled},
        "depends_on": {"nodes": list(parents)},
    }


def snapshot(name, yml) -> dict:
    return {
        "unique_id": f"snapshot.kipptaf.{name}",
        "resource_type": "snapshot",
        "name": name,
        "package_name": "kipptaf",
        "original_file_path": f"snapshots/{yml}.yml",
        "config": {"enabled": True},
        "depends_on": {"nodes": []},
    }


def source(source_name, name, package="kipptaf") -> dict:
    return {
        "unique_id": f"source.{package}.{source_name}.{name}",
        "resource_type": "source",
        "source_name": source_name,
        "name": name,
        "identifier": name,
        "package_name": package,
    }


def exposure(name, parents, kinds=("tableau",)) -> dict:
    return {
        "unique_id": f"exposure.kipptaf.{name}",
        "resource_type": "exposure",
        "name": name,
        "package_name": "kipptaf",
        "config": {"meta": {"dagster": {"kinds": list(kinds)}}},
        "depends_on": {"nodes": list(parents)},
    }


def manifest(*items) -> dict:
    m: dict = {"nodes": {}, "sources": {}, "exposures": {}}
    for item in items:
        key = {"source": "sources", "exposure": "exposures"}.get(
            item["resource_type"], "nodes"
        )
        m[key][item["unique_id"]] = item
    return m


def uid(node: dict) -> str:
    return node["unique_id"]


# kipptaf building blocks
SRC = source("kippnewark_powerschool", "src_powerschool__students")
STG_PS = model(
    "stg_powerschool__students", "models/powerschool/staging/a.sql", [uid(SRC)]
)
STG_DL = model("stg_deanslist__incidents", "models/deanslist/staging/a.sql", [uid(SRC)])
STG_GS = model("stg_google_sheets__people__locations", "models/google/sheets/a.sql")
INT_PS = model(
    "int_powerschool__enrollments",
    "models/powerschool/intermediate/a.sql",
    [uid(STG_PS)],
)
SNAP_PS = snapshot("snapshot_powerschool__gpa_term", "powerschool")
SNAP_DL = snapshot("snapshot_deanslist__x", "deanslist")
INT_STU = model(
    "int_students__students", "models/students/intermediate/a.sql", [uid(INT_PS)]
)
DIM = model("dim_students", "models/marts/dimensions/a.sql", [uid(INT_STU)])
FCT = model("fct_x", "models/marts/facts/a.sql", [uid(DIM)])
RPT = model("rpt_tableau__x", "models/extracts/tableau/a.sql", [uid(FCT)])
BASE = [SRC, STG_PS, STG_DL, STG_GS, INT_PS, SNAP_PS, SNAP_DL, INT_STU, DIM, FCT, RPT]


def violations(*extra, project="kipptaf") -> list:
    m = manifest(*BASE, *extra)
    return [(v.model, v.rule, v.detail) for v in mod.check_edges(m, project, DOMAIN)]


def test_clean_graph_has_no_violations() -> None:
    assert violations() == []


@pytest.mark.parametrize(
    ("name", "path", "parents", "detail"),
    [
        # stg_ reads source() only
        (
            "stg_powerschool__y",
            "models/powerschool/staging/b.sql",
            [STG_PS],
            "kipptaf.stg_powerschool__students",
        ),
        # source int_: other folder's stg_, a mart, other folder's snapshot
        (
            "int_powerschool__y",
            "models/powerschool/intermediate/b.sql",
            [STG_DL],
            "kipptaf.stg_deanslist__incidents",
        ),
        (
            "int_powerschool__z",
            "models/powerschool/intermediate/c.sql",
            [DIM],
            "kipptaf.dim_students",
        ),
        (
            "int_powerschool__w",
            "models/powerschool/intermediate/d.sql",
            [SNAP_DL],
            "kipptaf.snapshot_deanslist__x",
        ),
        # domain int_ never reads a mart
        (
            "int_people__y",
            "models/people/intermediate/b.sql",
            [DIM],
            "kipptaf.dim_students",
        ),
        # marts read domain int_ and marts only
        (
            "dim_y",
            "models/marts/dimensions/b.sql",
            [STG_PS],
            "kipptaf.stg_powerschool__students",
        ),
        (
            "dim_z",
            "models/marts/dimensions/c.sql",
            [INT_PS],
            "kipptaf.int_powerschool__enrollments",
        ),
        # rpt_ never reads stg_, source int_, or another kipptaf rpt_
        (
            "rpt_gsheets__y",
            "models/extracts/gsheets/b.sql",
            [STG_PS],
            "kipptaf.stg_powerschool__students",
        ),
        (
            "rpt_gsheets__z",
            "models/extracts/gsheets/c.sql",
            [RPT],
            "kipptaf.rpt_tableau__x",
        ),
    ],
)
def test_disallowed_edges_are_a1(name, path, parents, detail) -> None:
    child = model(name, path, [uid(p) for p in parents])
    assert violations(child) == [(f"kipptaf.{name}", "A1", detail)]


@pytest.mark.parametrize(
    ("name", "path", "parents"),
    [
        (
            "int_powerschool__y",
            "models/powerschool/intermediate/b.sql",
            [STG_PS, INT_PS, SNAP_PS, STG_GS],
        ),
        (
            "int_powerschool__u",
            "models/powerschool/intermediate/e.sql",
            [source("kippnewark_powerschool", "int_powerschool__x")],
        ),
        (
            "int_people__y",
            "models/people/intermediate/b.sql",
            [STG_DL, INT_PS, INT_STU, SNAP_DL],
        ),
        ("bridge_y", "models/marts/bridges/b.sql", [INT_STU, DIM, FCT]),
        ("rpt_gsheets__y", "models/extracts/gsheets/b.sql", [DIM, INT_STU]),
    ],
)
def test_allowed_edges_pass(name, path, parents) -> None:
    extra = [p for p in parents if p["resource_type"] == "source"]
    child = model(name, path, [uid(p) for p in parents])
    assert violations(child, *extra) == []


def test_stg_union_view_over_district_stg_source_passes() -> None:
    district_stg = source("kippnewark_amplify", "stg_amplify__x")
    union = model("stg_amplify__x", "models/amplify/staging/b.sql", [uid(district_stg)])
    assert violations(district_stg, union) == []


@pytest.mark.parametrize("table", ["int_renlearn__star", "base_renlearn__star"])
def test_stg_over_district_int_source_is_a1(table) -> None:
    district_int = source("kippmiami_renlearn", table)
    stg = model(
        "stg_renlearn__star", "models/renlearn/staging/b.sql", [uid(district_int)]
    )
    assert violations(district_int, stg) == [
        ("kipptaf.stg_renlearn__star", "A1", f"source.kippmiami_renlearn.{table}")
    ]


def test_int_reading_two_source_folders_outside_domain_is_source_int() -> None:
    node = model(
        "int_kippadb__roster",
        "models/kippadb/intermediate/b.sql",
        [uid(STG_PS), uid(STG_DL)],
    )
    assert mod.layer_of(node, "kipptaf", DOMAIN) == "source_int"


def test_domain_folders_constant() -> None:
    assert mod.DOMAIN_FOLDERS == {
        "assessments",
        "extracts",
        "finance",
        "gpa",
        "people",
        "performance_management",
        "reporting",
        "students",
        "surveys",
        "topline",
    }


def test_base_is_classified_like_int() -> None:
    src_base = model(
        "base_powerschool__x", "models/powerschool/intermediate/b.sql", [uid(STG_PS)]
    )
    dom_base = model("base_students__x", "models/students/b.sql", [uid(STG_PS)])
    assert mod.layer_of(src_base, "kipptaf", DOMAIN) == "source_int"
    assert mod.layer_of(dom_base, "kipptaf", DOMAIN) == "domain_int"


@pytest.mark.parametrize(
    ("table", "layer"),
    [
        ("src_powerschool__students", "source"),
        ("students", "source"),
        ("stg_focus__schools", "stg"),
        ("int_powerschool__x", "source_int"),
        ("rpt_powerschool__autocomm_students", "rpt"),
    ],
)
def test_source_layer_follows_table_prefix(table, layer) -> None:
    assert mod.layer_of(source("s", table), "kipptaf", DOMAIN) == layer


def test_disabled_model_is_skipped() -> None:
    bad = model("dim_y", "models/marts/dimensions/b.sql", [uid(STG_PS)], enabled=False)
    assert violations(bad) == []


def test_tableau_exposure_on_int_is_a8() -> None:
    assert violations(exposure("tableau_x", [uid(INT_STU)])) == [
        ("exposure.tableau_x", "A8", "kipptaf.int_students__students")
    ]


def test_cube_exposure_on_rpt_is_a8() -> None:
    cube = exposure(
        "cube_semantic_layer", [uid(DIM), uid(RPT)], kinds=("semanticmodel", "cube")
    )
    assert violations(cube) == [
        ("exposure.cube_semantic_layer", "A8", "kipptaf.rpt_tableau__x")
    ]


def test_exposures_on_rpt_and_mart_pass() -> None:
    assert violations(exposure("tableau_x", [uid(RPT), uid(FCT)])) == []


# district projects: every int_ is source int_; folder is the package
D_SRC = source(
    "kipptaf_extracts", "rpt_powerschool__autocomm_students", package="kippnewark"
)
D_STG = model(
    "stg_powerschool__students", "models/staging/a.sql", package="powerschool"
)


def district(*nodes) -> list:
    m = manifest(D_SRC, D_STG, *nodes)
    return [
        (v.model, v.rule, v.detail) for v in mod.check_edges(m, "kippnewark", DOMAIN)
    ]


def test_district_wrapper_reads_kipptaf_rpt() -> None:
    wrapper = model(
        "rpt_powerschool__autocomm_students",
        "models/extracts/a.sql",
        [uid(D_SRC)],
        package="kippnewark",
    )
    assert district(wrapper) == []


def test_reconciling_wrapper_may_read_stg() -> None:
    wrapper = model(
        "rpt_focus__x",
        "models/extracts/a.sql",
        [uid(D_SRC), uid(D_STG)],
        package="kippnewark",
    )
    assert district(wrapper) == []


def test_district_rpt_reading_stg_alone_is_a1() -> None:
    rpt = model("rpt_x__y", "models/extracts/a.sql", [uid(D_STG)], package="kippnewark")
    assert district(rpt) == [
        ("kippnewark.rpt_x__y", "A1", "powerschool.stg_powerschool__students")
    ]


def test_district_rpt_reading_other_rpt_source_is_a1() -> None:
    other = source("kipptaf_reporting", "rpt_x__z", package="kippnewark")
    rpt = model("rpt_x__y", "models/extracts/a.sql", [uid(other)], package="kippnewark")
    assert district(other, rpt) == [
        ("kippnewark.rpt_x__y", "A1", "source.kipptaf_reporting.rpt_x__z")
    ]


def test_district_int_in_students_folder_is_source_int() -> None:
    node = model(
        "int_students__x", "models/students/a.sql", [uid(D_STG)], package="kippnewark"
    )
    assert mod.layer_of(node, "kippnewark", DOMAIN) == "source_int"


def test_duplicate_name_across_packages_is_keyed_by_package() -> None:
    pkg = model(
        "int_finalsite__x",
        "models/intermediate/a.sql",
        [uid(D_STG)],
        package="finalsite",
    )
    root = model(
        "int_finalsite__x", "models/finalsite/a.sql", [uid(D_STG)], package="kippnewark"
    )
    assert district(pkg, root) == [
        ("finalsite.int_finalsite__x", "A1", "powerschool.stg_powerschool__students"),
        ("kippnewark.int_finalsite__x", "A1", "powerschool.stg_powerschool__students"),
    ]


# --- touched-model rules (A3, A4, A7, A9) ---------------------------------


def coded(name, path, code, meta=None, parents=(), patch=None) -> dict:
    node = model(name, path, parents)
    node["raw_code"] = code
    node["config"]["meta"] = meta or {}
    node["patch_path"] = patch
    return node


def unique_test(node, column=None, combo=None) -> dict:
    kwargs = {"combination_of_columns": combo} if combo else {}
    return {
        "unique_id": f"test.kipptaf.u_{node['name']}_{column or '_'.join(combo or [])}",
        "resource_type": "test",
        "attached_node": node["unique_id"],
        "column_name": column,
        "test_metadata": {
            "name": "unique_combination_of_columns" if combo else "unique",
            "kwargs": kwargs,
        },
        "depends_on": {"nodes": [node["unique_id"]]},
    }


def touched(*nodes, changed=None, added=(), project="kipptaf") -> list:
    """changed and added take paths; every node's package is its own key."""
    m = manifest(*BASE, *nodes)
    pkg = {n["original_file_path"]: n["package_name"] for n in nodes if "raw_code" in n}
    if changed is None:
        changed = {p: set(range(1, 200)) for p in pkg}
    changed_keys = {(pkg[p], p): lines for p, lines in changed.items()}
    added_keys = {(pkg[p], p) for p in added}
    v = mod.check_touched(m, project, changed_keys, added_keys, DOMAIN)
    return [(x.model, x.rule, x.severity) for x in v]


def test_a3_runs_on_added_package_intermediate() -> None:
    node = coded(
        "int_powerschool__x_pivoted", "models/intermediate/a.sql", "select 1,\n"
    )
    node["package_name"] = "powerschool"
    added = ["models/intermediate/a.sql"]
    assert touched(node, added=added, project="kippnewark") == [
        ("powerschool.int_powerschool__x_pivoted", "A3", "error")
    ]


MART_STAR = "with final as (select 1 as a)\n\nselect *\nfrom final\n"


def test_a9_star_final_select_on_changed_line() -> None:
    node = coded("dim_y", "models/marts/dimensions/b.sql", MART_STAR)
    assert touched(node) == [("kipptaf.dim_y", "A9", "error")]


@pytest.mark.parametrize(
    "code",
    [
        "with f as (select 1 as a)\n\nselect distinct *\nfrom f\n",
        "select *\nfrom a\n\nunion all\n\nselect a,\nfrom b\n",
    ],
)
def test_a9_star_in_distinct_or_any_union_branch(code) -> None:
    node = coded("dim_y", "models/marts/dimensions/b.sql", code)
    assert touched(node) == [("kipptaf.dim_y", "A9", "error")]


def test_a9_ignores_star_final_select_on_unchanged_line() -> None:
    node = coded("dim_y", "models/marts/dimensions/b.sql", MART_STAR)
    assert touched(node, changed={"models/marts/dimensions/b.sql": {1}}) == []


def test_a9_ignores_star_in_cte_and_int() -> None:
    mart = coded(
        "dim_y",
        "models/marts/dimensions/b.sql",
        "with x as (\n    select *\n    from t\n)\n\nselect a,\nfrom x\n",
    )
    int_ = coded("int_people__y", "models/people/b.sql", MART_STAR)
    assert touched(mart, int_) == []


def test_a9_dropped_by_standard_exempt() -> None:
    node = coded(
        "rpt_x__y",
        "models/extracts/x/b.sql",
        MART_STAR,
        meta={"standard_exempt": {"A9": "tool needs every column"}},
    )
    assert touched(node) == []


@pytest.mark.parametrize(
    "name", ["int_people__staff_pivoted", "int_people__staff_unioned"]
)
def test_a3_near_miss_suffix_on_added_int(name) -> None:
    path = "models/people/b.sql"
    node = coded(name, path, "select 1 as a,\n")
    assert touched(node, added=[path]) == [(f"kipptaf.{name}", "A3", "error")]


@pytest.mark.parametrize(
    "name", ["int_people__staff_pivot", "int_people__staff", "int_people__roster"]
)
def test_a3_valid_names_pass(name) -> None:
    path = "models/people/b.sql"
    assert touched(coded(name, path, "select 1 as a,\n"), added=[path]) == []


def test_a3_only_judges_added_models() -> None:
    node = coded("int_people__staff_pivoted", "models/people/b.sql", "select 1,\n")
    assert touched(node) == []


SK = "{{ dbt_utils.generate_surrogate_key(['employee_number']) }}"


@pytest.mark.parametrize(
    "code",
    [
        f"select\n    {SK} as staff_key,\nfrom t\n",
        f"select\n    {SK} as submitter_staff_key,\nfrom t\n",
        "select\n    {{-\n        dbt_utils.generate_surrogate_key(\n"
        "            ['employee_number']\n        )\n    }} as staff_key,\nfrom t\n",
        f"select\n    if(\n        e is not null,\n        {SK},\n"
        "        cast(null as string)\n    ) as staff_key,\nfrom t\n",
        f"select\n    {SK} as staff_observation_key,\nfrom t\n",
    ],
)
def test_a7_direct_hash_of_macro_key(code) -> None:
    node = coded("fct_y", "models/marts/facts/b.sql", code)
    assert touched(node) == [("kipptaf.fct_y", "A7", "error")]


@pytest.mark.parametrize(
    "code",
    [
        "select\n    {{ staff_key('employee_number') }} as staff_key,\nfrom t\n",
        f"select\n    {SK} as assessment_score_key,\nfrom t\n",
        f"select\n    {SK} as grades_term_key,\nfrom t\n",
        f"select\n    {SK} as row_hash,\n    x as staff_key,\nfrom t\n",
        f"select a,\nfrom t\nwhere k = {SK}\n\nunion all\n\nselect x as staff_key,\n",
    ],
)
def test_a7_passes_macro_call_and_keys_without_macro(code) -> None:
    assert touched(coded("fct_y", "models/marts/facts/b.sql", code)) == []


def test_a7_ignores_unchanged_lines() -> None:
    node = coded(
        "fct_y", "models/marts/facts/b.sql", f"select\n    {SK} as staff_key,\n"
    )
    assert touched(node, changed={"models/marts/facts/b.sql": {1}}) == []


def test_a4_warns_on_added_int_sharing_a_grain() -> None:
    a = coded("int_people__a", "models/people/a.sql", "select 1,\n")
    b = coded("int_people__b", "models/people/b.sql", "select 1,\n")
    tests = [unique_test(a, combo=["x", "y"]), unique_test(b, combo=["y", "x"])]
    assert touched(a, b, *tests, added=["models/people/b.sql"]) == [
        ("kipptaf.int_people__b", "A4", "warning")
    ]


def test_a4_skips_parents_and_siblings_sharing_a_consumer() -> None:
    a = coded("int_people__a", "models/people/a.sql", "select 1,\n")
    b = coded("int_people__b", "models/people/b.sql", "select 1,\n", parents=[uid(a)])
    c = coded("int_people__c", "models/people/c.sql", "select 1,\n")
    d = coded("int_people__d", "models/people/d.sql", "select 1,\n")
    u = coded(
        "int_people__u", "models/people/u.sql", "select 1,\n", parents=[uid(c), uid(d)]
    )
    tests = [unique_test(a, column="k"), unique_test(b, column="k")]
    tests += [unique_test(c, column="j"), unique_test(d, column="j")]
    added = ["models/people/b.sql", "models/people/d.sql"]
    assert touched(a, b, c, d, u, *tests, added=added) == []


# --- file selection, baseline, diff ---------------------------------------


def test_load_baseline_and_compare(tmp_path) -> None:
    f = tmp_path / "b.tsv"
    f.write_text(
        "model\trule\tdetail\tissue\n"
        "kipptaf.a\tA1\tkipptaf.p\t#1\n"
        "kipptaf.b\tA1\tkipptaf.p\t\n"
        "kipptaf.gone\tA1\tkipptaf.p\t#2\n"
    )
    baseline = mod.load_baseline(f)
    v = [
        mod.Violation(m_, "A1", "kipptaf.p", "error", "")
        for m_ in ("kipptaf.a", "kipptaf.b", "kipptaf.new")
    ]
    new, stale, missing = mod.compare(v, baseline)
    assert [x.model for x in new] == ["kipptaf.new"]
    assert stale == [("kipptaf.gone", "A1", "kipptaf.p")]
    assert missing == [("kipptaf.b", "A1", "kipptaf.p")]


def test_load_baseline_skips_blank_lines(tmp_path) -> None:
    f = tmp_path / "b.tsv"
    f.write_text("model\trule\tdetail\tissue\nkipptaf.a\tA1\tkipptaf.p\t#1\n\n")
    assert mod.load_baseline(f) == {("kipptaf.a", "A1", "kipptaf.p"): "#1"}


DIFF = """diff --git a/src/dbt/kipptaf/models/a.sql b/src/dbt/kipptaf/models/a.sql
index 1..2 100644
--- a/src/dbt/kipptaf/models/a.sql
+++ b/src/dbt/kipptaf/models/a.sql
@@ -3,0 +4,2 @@ select
+    x,
+    y,
@@ -10 +12 @@ from t
-where a
+where b
diff --git a/src/dbt/kipptaf/models/new.sql b/src/dbt/kipptaf/models/new.sql
new file mode 100644
--- /dev/null
+++ b/src/dbt/kipptaf/models/new.sql
@@ -0,0 +1,2 @@
+select 1 as a,
+from t
diff --git a/src/dbt/kippnewark/models/z.sql b/src/dbt/kippnewark/models/z.sql
--- a/src/dbt/kippnewark/models/z.sql
+++ b/src/dbt/kippnewark/models/z.sql
@@ -1 +1 @@
-a
+b
"""


ROOTS = {"kipptaf": "src/dbt/kipptaf", "powerschool": "src/dbt/powerschool"}


def test_parse_diff_scopes_to_package_roots() -> None:
    changed, added = mod.parse_diff(DIFF, {"kipptaf": "src/dbt/kipptaf"})
    assert changed == {
        ("kipptaf", "models/a.sql"): {4, 5, 12},
        ("kipptaf", "models/new.sql"): {1, 2},
    }
    assert added == {("kipptaf", "models/new.sql")}


EDGE_DIFF = """diff --git a/src/dbt/powerschool/models/a.sql b/src/dbt/powerschool/models/a.sql
--- a/src/dbt/powerschool/models/a.sql
+++ b/src/dbt/powerschool/models/a.sql
@@ -2,0 +3,2 @@ select
+++ x,
+    y,
@@ -9 +10,0 @@ from t
-where a
@@ -20 +20 @@ from t
-z
\\ No newline at end of file
+zz
\\ No newline at end of file
"""


def test_parse_diff_reads_plus_lines_deletions_and_no_newline() -> None:
    changed, added = mod.parse_diff(EDGE_DIFF, ROOTS)
    assert changed == {("powerschool", "models/a.sql"): {3, 4, 20}}
    assert added == set()


def test_package_roots_are_cwd_relative_from_an_absolute_project_dir(
    tmp_path, monkeypatch
) -> None:
    for name in ("kippnewark", "powerschool", "notes"):
        (tmp_path / "src/dbt" / name).mkdir(parents=True)
    for name in ("kippnewark", "powerschool"):
        (tmp_path / "src/dbt" / name / "dbt_project.yml").write_text(f"name: {name}\n")
    monkeypatch.chdir(tmp_path)
    assert mod.package_roots(tmp_path / "src/dbt/kippnewark") == {
        "kippnewark": "src/dbt/kippnewark",
        "powerschool": "src/dbt/powerschool",
    }


def test_exposure_named_like_its_rpt_reads_its_own_exemption() -> None:
    rpt = model("rpt_gsheets__x", "models/extracts/google/sheets/b.sql", [])
    rpt["config"]["meta"] = {"standard_exempt": {"A1": "model"}}
    exp = exposure("rpt_gsheets__x", [uid(rpt)])
    exp["config"]["meta"]["standard_exempt"] = {"A8": "exposure"}
    m = manifest(rpt, exp)
    exempt = mod.exempt_index(m)
    assert exempt["exposure.rpt_gsheets__x"] == {"A8": "exposure"}
    assert exempt["kipptaf.rpt_gsheets__x"] == {"A1": "model"}


def test_snapshot_folder_follows_the_model_it_snapshots() -> None:
    stg = model(
        "stg_google_appsheet__seats", "models/google/appsheet/staging/b.sql", [uid(SRC)]
    )
    snap = snapshot("snapshot_seat_tracker__seats", "google_appsheet")
    snap["depends_on"]["nodes"] = [uid(stg)]
    child = model(
        "int_seat_tracker__snapshot", "models/google/appsheet/b.sql", [uid(snap)]
    )
    assert violations(stg, snap, child) == []
