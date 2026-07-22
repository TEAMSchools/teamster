from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

FIXTURE_DIR = Path(__file__).parent / "fixtures/cube_ref_sample"
SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/generate_cube_reference.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_cube_reference", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_cube_reference"] = module
    spec.loader.exec_module(module)
    return module


gen = _load_module()


def test_parse_cubes_indexes_members_and_kinds() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    fact = cubes["sample_fact"]
    assert fact["count_rows"].kind == "measure"
    assert fact["grade_level"].kind == "dimension"
    assert fact["grade_level"].type == "number"
    assert fact["grade_level"].description == "Student grade level."
    # missing description is preserved as None (not the empty string)
    assert fact["no_desc_dim"].description is None


def test_parse_cubes_flattens_extends() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")

    # sample_alias extends sample_base and defines no members of its own, so it
    # inherits base_key with its description and primary_key flag.
    alias = cubes["sample_alias"]
    assert "base_key" in alias
    assert alias["base_key"].description == "Base key."
    assert alias["base_key"].primary_key is True


def _resolved_view(name: str = "sample_view"):
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    return next(v for v in views if v.name == name)


def test_resolve_view_applies_prefix_rule() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    # prefix: false -> bare member names
    assert "grade_level" in by_name
    assert "count_rows" in by_name
    assert "base_key" in by_name  # from sample_alias (extends sample_base)
    # prefix: true -> <last-join_path-segment>_<member>
    assert "sample_dim_region_name" in by_name
    assert by_name["sample_dim_region_name"].description == "Region name."


def test_resolve_view_classifies_and_types_members() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["count_rows"].kind == "measure"
    assert by_name["grade_level"].kind == "dimension"
    assert by_name["grade_level"].type == "number"
    assert by_name["no_desc_dim"].description is None
    assert by_name["grade_level"].source == "sample_fact.grade_level"


def test_resolve_view_assigns_folders_with_other_fallback() -> None:
    view = _resolved_view()
    by_name = {m.exposed_name: m for m in view.members}

    assert by_name["grade_level"].folder == "Sample"
    assert by_name["sample_dim_region_name"].folder == "Region"
    # base_key is exposed but listed in no meta folder -> "Other"
    assert by_name["base_key"].folder == "Other"
    # measures are never folder-grouped
    assert by_name["count_rows"].folder == ""


def test_derive_access_reads_groups_and_row_level() -> None:
    view = _resolved_view()
    access = view.access

    assert access.groups == ["sample-network", "sample-region"]
    assert access.row_level_members == ["sample_dim_region_name"]
    # no sensitive members in the fixture
    assert access.exposes_pii is False


def test_sensitive_members_excludes_directory_public_names() -> None:
    # full_name is directory-public (staff_directory) and must not drive the flag
    assert "full_name" not in gen.SENSITIVE_MEMBERS
    assert "personal_email" in gen.SENSITIVE_MEMBERS


def test_derive_access_recurses_nested_or_and_filters() -> None:
    # a member referenced only inside a nested or/and must still be collected
    view = {
        "name": "v",
        "access_policy": [
            {
                "group": "g",
                "row_level": {
                    "filters": [
                        {"member": "top_level", "operator": "equals", "values": ["x"]},
                        {
                            "or": [
                                {"member": "nested_a", "operator": "set"},
                                {
                                    "and": [
                                        {"member": "deep_b", "operator": "set"},
                                    ]
                                },
                            ]
                        },
                    ]
                },
            }
        ],
    }
    access = gen.derive_access(view, [])
    assert access.row_level_members == ["top_level", "nested_a", "deep_b"]


def test_resolve_view_wildcard_excludes_underscore_helpers() -> None:
    cubes = {
        "c": {
            "count_rows": gen.CubeMember(
                name="count_rows",
                kind="measure",
                type="count",
                description=None,
                primary_key=False,
                public=True,
            ),
            "_sum_helper": gen.CubeMember(
                name="_sum_helper",
                kind="measure",
                type="sum",
                description=None,
                primary_key=False,
                public=False,
            ),
        }
    }
    view = {"name": "v", "cubes": [{"join_path": "c", "includes": "*"}]}
    resolved = gen.resolve_view(view, cubes)
    names = {m.exposed_name for m in resolved.members}
    assert "count_rows" in names
    assert "_sum_helper" not in names


def test_render_page_has_banner_and_one_h2_per_view() -> None:
    cubes = gen.parse_cubes(FIXTURE_DIR / "cubes")
    views = gen.parse_views(FIXTURE_DIR / "views", cubes)
    page = gen.render_page(views)

    assert page.startswith("# Cube data catalog\n")
    assert gen.BANNER in page
    assert page.count("\n## ") == 1
    assert "## sample_view" in page


def test_render_view_tables_and_placeholder() -> None:
    view = _resolved_view()
    block = gen.render_view(view)

    # measures section + a measure row
    assert "### Measures" in block
    assert "| `count_rows` | count | Row count. |" in block
    # dimensions grouped by folder heading
    assert "#### Sample" in block
    assert "#### Region" in block
    assert "#### Other" in block
    assert "| `grade_level` | number | Student grade level. |" in block
    # missing description -> visible placeholder, not blank
    assert "| `no_desc_dim` | string | _No description._ |" in block
    # access summary line
    assert "sample-network" in block
    assert "sample-region" in block


def test_normalize_neutralizes_table_padding() -> None:
    compact = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    padded = "| Name  | Type   |\n| ----- | ------ |\n| `a`   | number |\n"
    assert gen._normalize(compact) == gen._normalize(padded)


def test_normalize_neutralizes_prose_wrap() -> None:
    # prettier's proseWrap: always hard-wraps long paragraphs; the unwrapped
    # generator output and the wrapped-on-commit file must normalize equal.
    one_line = "## view\n\nA long description that would normally wrap onto more than one line here.\n"
    wrapped = (
        "## view\n\nA long description that would normally wrap onto more than\n"
        "one line here.\n"
    )
    assert gen._normalize(one_line) == gen._normalize(wrapped)


def test_check_stale_passes_on_padding_only_diff(tmp_path) -> None:
    page = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    padded_file = tmp_path / "out.md"
    padded_file.write_text(
        "| Name  | Type   |\n| ----- | ------ |\n| `a`   | number |\n",
        encoding="utf-8",
    )
    assert gen.check_stale(page, padded_file) == 0


def test_check_stale_fails_on_content_diff(tmp_path) -> None:
    page = "| Name | Type |\n| --- | --- |\n| `a` | number |\n"
    out = tmp_path / "out.md"
    out.write_text(
        "| Name | Type |\n| --- | --- |\n| `b` | number |\n", encoding="utf-8"
    )
    assert gen.check_stale(page, out) == 1


def test_main_writes_output(tmp_path) -> None:
    out = tmp_path / "catalog.md"
    rc = gen.main(
        [
            "--cubes-dir",
            str(FIXTURE_DIR / "cubes"),
            "--views-dir",
            str(FIXTURE_DIR / "views"),
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    assert "## sample_view" in out.read_text(encoding="utf-8")


def _fake_meta() -> dict:
    return {
        "cubes": [
            {
                "name": "sample_view",
                "measures": [{"name": "sample_view.count_rows", "type": "count"}],
                "dimensions": [
                    {"name": "sample_view.grade_level", "type": "number"},
                    {"name": "sample_view.no_desc_dim", "type": "string"},
                    {"name": "sample_view.sample_dim_region_name", "type": "string"},
                    {"name": "sample_view.base_key", "type": "string"},
                ],
            }
        ]
    }


def test_meta_member_types_strips_view_prefix() -> None:
    types = gen.meta_member_types(_fake_meta())
    assert types["sample_view"]["grade_level"] == "number"
    assert types["sample_view"]["count_rows"] == "count"


def test_verify_against_meta_passes_when_matching() -> None:
    rc = gen.verify_against_meta(
        FIXTURE_DIR / "cubes",
        FIXTURE_DIR / "views",
        fetch=lambda: _fake_meta(),
    )
    assert rc == 0


def test_verify_against_meta_fails_on_missing_member(capsys) -> None:
    meta = _fake_meta()
    meta["cubes"][0]["dimensions"] = [
        d for d in meta["cubes"][0]["dimensions"] if d["name"] != "sample_view.base_key"
    ]
    rc = gen.verify_against_meta(
        FIXTURE_DIR / "cubes", FIXTURE_DIR / "views", fetch=lambda: meta
    )
    assert rc == 1
    assert "base_key" in capsys.readouterr().err
