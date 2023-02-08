import argparse
import pathlib

from yaml import safe_load


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sources_file_path", type=pathlib.Path)
    args = parser.parse_args()

    with args.sources_file_path.open(mode="r") as f:
        sources = safe_load(f)

    tables = sources["sources"][0]["tables"]

    for t in tables:
        model_path: pathlib.Path = args.sources_file_path.parent / (
            t["name"].replace("src_", "") + ".sql"
        )
        print(model_path)
        model_path.touch(exist_ok=True)


if __name__ == "__main__":
    main()

{
    "database": "teamster-332318",
    "schema": "dbt_powerschool",
    "name": "assignmentcategoryassoc",
    "resource_type": "model",
    "package_name": "teamster",
    "path": "powerschool/staging/assignmentcategoryassoc.sql",
    "original_file_path": "models/powerschool/staging/assignmentcategoryassoc.sql",
    "unique_id": "model.teamster.assignmentcategoryassoc",
    "fqn": ["teamster", "powerschool", "staging", "assignmentcategoryassoc"],
    "alias": "assignmentcategoryassoc",
    "checksum": {
        "name": "sha256",
        "checksum": "f108fb2b9e74dd8919edea03357379a9f13d7d9dd0f175c9503c4078bda79789",
    },
    "config": {
        "enabled": True,
        "schema": "powerschool",
        "tags": [],
        "meta": {},
        "materialized": "incremental",
        "incremental_strategy": "merge",
        "persist_docs": {},
        "quoting": {},
        "column_types": {},
        "unique_key": "assignmentcategoryassocid",
        "on_schema_change": "ignore",
        "grants": {},
        "packages": [],
        "docs": {"show": True},
        "post-hook": [],
        "pre-hook": [],
    },
    "tags": [],
    "description": "",
    "columns": {},
    "meta": {},
    "docs": {"show": True},
    "deferred": False,
    "unrendered_config": {
        "schema": "powerschool",
        "materialized": "incremental",
        "incremental_strategy": "merge",
        "unique_key": "assignmentcategoryassocid",
    },
    "created_at": 1675881991.6021843,
    "config_call_dict": {
        "materialized": "incremental",
        "incremental_strategy": "merge",
        "unique_key": "assignmentcategoryassocid",
    },
    "relation_name": "`teamster-332318`.`dbt_powerschool`.`assignmentcategoryassoc`",
    "raw_code": '{%- set code_location = "kippcamden" -%}\n{%- set source_name = "powerschool" -%}\n\n{%- set file_uri = (\n    "gs://teamster-"\n    ~ code_location\n    ~ "/dagster/"\n    ~ code_location\n    ~ "/"\n    ~ source_name\n    ~ "/"\n    ~ this.identifier\n    ~ "/"\n    ~ var("partition")\n) -%}\n{{ log(model, info=True) }}\n{{\n    incremental_merge_source_file(\n        source_name,\n        this.identifier,\n        "assignmentcategoryassocid",\n        file_uri,\n        [\n            {"name": "assignmentcategoryassocid", "type": "int_value"},\n            {"name": "assignmentsectionid", "type": "int_value"},\n            {"name": "teachercategoryid", "type": "int_value"},\n            {"name": "yearid", "type": "int_value"},\n            {"name": "isprimary", "type": "int_value"},\n            {"name": "whomodifiedid", "type": "int_value"},\n        ],\n    )\n}}',
    "language": "<ModelLanguage.sql: 'sql'>",
    "refs": [],
    "sources": [["powerschool", "src_assignmentcategoryassoc"]],
    "metrics": [],
    "depends_on": {
        "macros": ["macro.teamster.incremental_merge_source_file"],
        "nodes": ["source.teamster.powerschool.src_assignmentcategoryassoc"],
    },
}
