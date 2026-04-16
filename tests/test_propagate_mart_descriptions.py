"""Tests for scripts/propagate_mart_descriptions.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path("scripts/propagate_mart_descriptions.py")


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "propagate_mart_descriptions", _SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


STAGING_FIXTURE = Path("tests/fixtures/staging_yaml")


def test_build_staging_dict_keys() -> None:
    module = _load_script()
    result = module._build_staging_description_dict([STAGING_FIXTURE])
    assert ("stg_source__table", "dob") in result
    assert ("stg_source__table", "student_number") in result
    assert ("stg_source__table", "lastfirst") in result


def test_build_staging_dict_description() -> None:
    module = _load_script()
    result = module._build_staging_description_dict([STAGING_FIXTURE])
    entry = result[("stg_source__table", "dob")]
    assert entry["description"] == "Date of Birth."
    assert entry["contains_pii"] is True


def test_build_staging_dict_no_pii_flag() -> None:
    module = _load_script()
    result = module._build_staging_description_dict([STAGING_FIXTURE])
    entry = result[("stg_source__table", "student_number")]
    assert entry["contains_pii"] is False


def test_build_staging_dict_skips_empty_descriptions() -> None:
    module = _load_script()
    result = module._build_staging_description_dict([STAGING_FIXTURE])
    assert ("stg_source__table", "computed_col") not in result


def test_build_source_mapping_extracts_relation() -> None:
    module = _load_script()
    manifest = {
        "sources": {
            "source.kipptaf.kippnewark_powerschool.stg_powerschool__students": {
                "relation_name": "`teamster-332318`.`kippnewark_powerschool`.`stg_powerschool__students`",
                "source_name": "kippnewark_powerschool",
                "name": "stg_powerschool__students",
            },
        },
    }
    result = module._build_source_mapping(manifest)
    key = "`teamster-332318`.`kippnewark_powerschool`.`stg_powerschool__students`"
    assert key in result
    assert result[key]["source_name"] == "kippnewark_powerschool"
    assert result[key]["table_name"] == "stg_powerschool__students"
    assert result[key]["package"] == "powerschool"


def test_build_source_mapping_strips_region_prefix() -> None:
    module = _load_script()
    manifest = {
        "sources": {
            "source.kipptaf.kippcamden_deanslist.stg_deanslist__incidents": {
                "relation_name": "`teamster-332318`.`kippcamden_deanslist`.`stg_deanslist__incidents`",
                "source_name": "kippcamden_deanslist",
                "name": "stg_deanslist__incidents",
            },
        },
    }
    result = module._build_source_mapping(manifest)
    key = "`teamster-332318`.`kippcamden_deanslist`.`stg_deanslist__incidents`"
    assert result[key]["package"] == "deanslist"


def test_build_source_mapping_non_regional_source() -> None:
    module = _load_script()
    manifest = {
        "sources": {
            "source.kipptaf.kippadb.contact": {
                "relation_name": "`teamster-332318`.`kipptaf_kippadb`.`Contact`",
                "source_name": "kippadb",
                "name": "contact",
            },
        },
    }
    result = module._build_source_mapping(manifest)
    key = "`teamster-332318`.`kipptaf_kippadb`.`Contact`"
    assert result[key]["package"] == "kippadb"
