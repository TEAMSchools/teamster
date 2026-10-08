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


def test_int_reading_two_source_folders_is_domain() -> None:
    node = model(
        "int_kippadb__roster",
        "models/kippadb/intermediate/b.sql",
        [uid(STG_PS), uid(STG_DL)],
    )
    m = manifest(*BASE, node)
    assert mod.layer_of(node, m, "kipptaf", DOMAIN) == "domain_int"


def test_google_sheets_parent_is_not_a_second_folder() -> None:
    node = model(
        "int_powerschool__y",
        "models/powerschool/intermediate/b.sql",
        [uid(STG_PS), uid(STG_GS)],
    )
    m = manifest(*BASE, node)
    assert mod.layer_of(node, m, "kipptaf", DOMAIN) == "source_int"


def test_base_is_classified_like_int() -> None:
    src_base = model(
        "base_powerschool__x", "models/powerschool/intermediate/b.sql", [uid(STG_PS)]
    )
    dom_base = model("base_students__x", "models/students/b.sql", [uid(STG_PS)])
    m = manifest(*BASE, src_base, dom_base)
    assert mod.layer_of(src_base, m, "kipptaf", DOMAIN) == "source_int"
    assert mod.layer_of(dom_base, m, "kipptaf", DOMAIN) == "domain_int"


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
    assert mod.layer_of(source("s", table), {}, "kipptaf", DOMAIN) == layer


def test_disabled_model_is_skipped() -> None:
    bad = model("dim_y", "models/marts/dimensions/b.sql", [uid(STG_PS)], enabled=False)
    assert violations(bad) == []


def test_tableau_exposure_on_int_is_a8() -> None:
    assert violations(exposure("tableau_x", [uid(INT_STU)])) == [
        ("kipptaf.tableau_x", "A8", "kipptaf.int_students__students")
    ]


def test_cube_exposure_on_rpt_is_a8() -> None:
    cube = exposure(
        "cube_semantic_layer", [uid(DIM), uid(RPT)], kinds=("semanticmodel", "cube")
    )
    assert violations(cube) == [
        ("kipptaf.cube_semantic_layer", "A8", "kipptaf.rpt_tableau__x")
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


def test_district_int_in_students_folder_is_source_int() -> None:
    node = model(
        "int_students__x", "models/students/a.sql", [uid(D_STG)], package="kippnewark"
    )
    assert (
        mod.layer_of(node, manifest(D_STG, node), "kippnewark", DOMAIN) == "source_int"
    )


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
