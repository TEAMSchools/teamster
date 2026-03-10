# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "google-cloud-bigquery",
# ]
# ///

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from dataclasses import dataclass

from google.cloud import bigquery


@dataclass
class DbtRelation:
    database: str
    schema: str
    alias: str
    resource_type: str  # "model" or "source"
    materialization: str  # e.g. table/view/incremental/source
    enabled: bool
    unique_id: str


@dataclass
class BqObject:
    project: str
    dataset: str
    name: str
    table_type: str  # TABLE or VIEW


def dbt_run(project: str, *args: str, target_path: str | None = None) -> None:
    env = {
        **os.environ,
        "PATH": os.environ["PATH"] + ":/workspaces/teamster/.venv/bin",
        # Unset dev flag so Jinja env_var() checks resolve to prod schema names.
        "DBT_CLOUD_ENVIRONMENT_TYPE": "prod",
    }
    cmd = ["dbt", *args, f"--project-dir=src/dbt/{project}", "--target=prod"]
    if target_path:
        cmd.append(f"--target-path={target_path}")
    # trunk-ignore(bandit/B603)
    subprocess.run(args=cmd, env=env, check=True)


def load_manifest(project: str) -> dict:
    with tempfile.TemporaryDirectory() as target_path:
        dbt_run(project, "deps")
        dbt_run(project, "parse", target_path=target_path)
        path = pathlib.Path(target_path) / "manifest.json"
        return json.loads(path.read_text())


def relation_key(node: dict) -> tuple[str, str] | None:
    """Extract (dataset, table) from a node's relation_name.

    Using relation_name avoids Jinja/whitespace issues in schema fields
    (e.g. block scalars in source YAML that leave trailing newlines).
    Returns None for ephemeral models and nodes with no relation_name.
    """
    relation_name = node.get("relation_name")
    if not relation_name:
        return None
    parts = relation_name.replace("`", "").split(".")
    if len(parts) != 3:
        return None
    return parts[1], parts[2]


def get_dbt_relations(manifest: dict) -> dict[tuple[str, str], DbtRelation]:
    """Returns dict keyed by (dataset, table) for all non-ephemeral models and sources."""
    project_name = manifest["metadata"]["project_name"]
    relations: dict[tuple[str, str], DbtRelation] = {}

    for node_id, node in manifest["nodes"].items():
        if node["resource_type"] != "model":
            continue
        if node["package_name"] != project_name:
            continue
        materialization = node["config"].get("materialized", "table")
        if materialization == "ephemeral":
            continue
        key = relation_key(node)
        if key is None:
            continue
        alias = node.get("alias") or node["name"]
        relations[key] = DbtRelation(
            database=node["database"],
            schema=key[0],
            alias=alias,
            resource_type="model",
            materialization=materialization,
            enabled=True,
            unique_id=node_id,
        )

    for node_id, node in manifest["sources"].items():
        alias = node.get("identifier") or node["name"]
        # External sources have relation_name=null; fall back to schema+identifier.
        # schema.strip() handles trailing newlines from YAML block scalars.
        key = relation_key(node) or (node["schema"].strip(), alias)
        relations[key] = DbtRelation(
            database=node["database"],
            schema=key[0],
            alias=alias,
            resource_type="source",
            materialization="source",
            enabled=True,
            unique_id=node_id,
        )

    for node_id, node_list in manifest["disabled"].items():
        node = node_list[0]
        if node["package_name"] != project_name:
            continue
        materialization = node["config"].get("materialized", "table")
        if node["resource_type"] == "model":
            if materialization == "ephemeral":
                continue
            alias = node.get("alias") or node["name"]
        elif node["resource_type"] == "source":
            alias = node.get("identifier") or node["name"]
            materialization = "source"
        else:
            continue
        key = relation_key(node) or (node["schema"].strip(), alias)
        if key not in relations:
            relations[key] = DbtRelation(
                database=node["database"],
                schema=key[0],
                alias=alias,
                resource_type=node["resource_type"],
                materialization=materialization,
                enabled=False,
                unique_id=node_id,
            )

    return relations


def get_bq_objects(
    client: bigquery.Client, bq_project: str, datasets: set[str]
) -> dict[tuple[str, str], BqObject]:
    """Returns dict keyed by (dataset, table_name) for all BQ tables/views."""
    bq_objects: dict[tuple[str, str], BqObject] = {}
    for dataset_id in sorted(datasets):
        try:
            for table in client.list_tables(f"{bq_project}.{dataset_id}"):
                bq_objects[(dataset_id, table.table_id)] = BqObject(
                    project=bq_project,
                    dataset=dataset_id,
                    name=table.table_id,
                    table_type=table.table_type,
                )
        except Exception as e:
            print(
                f"Warning: could not list tables in {dataset_id}: {e}",
                file=sys.stderr,
            )
    return bq_objects


def drop_statement(obj: BqObject) -> str:
    obj_type = "VIEW" if obj.table_type == "VIEW" else "TABLE"
    return f"DROP {obj_type} IF EXISTS `{obj.project}`.`{obj.dataset}`.`{obj.name}`;"


def fmt_md_table(rows: list[dict], headers: list[tuple[str, str]]) -> str:
    """Render a markdown table. headers is list of (key, label) pairs."""
    keys = [k for k, _ in headers]
    labels = [lbl for _, lbl in headers]
    widths = [len(lbl) for lbl in labels]
    for row in rows:
        for i, k in enumerate(keys):
            widths[i] = max(widths[i], len(row.get(k, "")))

    def fmt_row(values: list[str]) -> str:
        return (
            "| " + " | ".join(v.ljust(widths[i]) for i, v in enumerate(values)) + " |"
        )

    lines = [
        fmt_row(labels),
        "| " + " | ".join("-" * w for w in widths) + " |",
        *[fmt_row([row.get(k, "") for k in keys]) for row in rows],
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit dbt models against BigQuery objects"
    )
    parser.add_argument("project", help="dbt project name (e.g. kipptaf)")
    parser.add_argument(
        "--bq-project",
        help="BigQuery project ID (default: read from manifest nodes)",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.project)

    bq_project = args.bq_project
    if not bq_project:
        for node in {**manifest["nodes"], **manifest["sources"]}.values():
            if node["resource_type"] in ("model", "source"):
                bq_project = node["database"]
                break
    if not bq_project:
        print("Error: could not determine BigQuery project ID.", file=sys.stderr)
        sys.exit(1)

    dbt_relations = get_dbt_relations(manifest)

    # Derive the target schema prefix from the manifest: all models this project
    # materializes will share a common prefix (e.g. "kipptaf_"). Datasets from
    # other dbt projects (e.g. "kippmiami_fldoe") won't match.
    model_schemas = [
        r.schema for r in dbt_relations.values() if r.resource_type == "model"
    ]
    target_prefix = os.path.commonprefix(model_schemas).rstrip("_")

    # Only scan datasets where this project materializes models AND whose name
    # starts with the derived target schema prefix.
    datasets = {
        schema
        for (schema, _), relation in dbt_relations.items()
        if relation.resource_type == "model" and schema.startswith(target_prefix)
    }

    client = bigquery.Client(project=bq_project)
    bq_objects = get_bq_objects(client, bq_project, datasets)

    untracked: list[BqObject] = []
    disabled_in_dbt: list[tuple[BqObject, DbtRelation]] = []
    missing_from_bq: list[DbtRelation] = []

    for key, bq_obj in bq_objects.items():
        relation = dbt_relations.get(key)
        if relation is None:
            untracked.append(bq_obj)
        elif not relation.enabled:
            disabled_in_dbt.append((bq_obj, relation))

    for key, relation in dbt_relations.items():
        if relation.enabled and key not in bq_objects:
            missing_from_bq.append(relation)

    rows = []
    for obj in sorted(untracked, key=lambda o: (o.dataset, o.name)):
        rows.append(
            {
                "object": f"`{bq_project}.{obj.dataset}.{obj.name}`",
                "status": "untracked",
                "bq_type": obj.table_type,
                "dbt_type": "",
            }
        )
    for obj, relation in sorted(
        disabled_in_dbt, key=lambda x: (x[0].dataset, x[0].name)
    ):
        rows.append(
            {
                "object": f"`{bq_project}.{obj.dataset}.{obj.name}`",
                "status": "disabled in dbt",
                "bq_type": obj.table_type,
                "dbt_type": relation.materialization,
            }
        )
    for relation in sorted(missing_from_bq, key=lambda r: (r.schema, r.alias)):
        rows.append(
            {
                "object": f"`{bq_project}.{relation.schema}.{relation.alias}`",
                "status": "missing from bigquery",
                "bq_type": "",
                "dbt_type": relation.materialization,
            }
        )

    headers = [
        ("object", "BigQuery Object"),
        ("status", "Status"),
        ("bq_type", "BQ Type"),
        ("dbt_type", "dbt Type"),
    ]
    audit_path = pathlib.Path(f"{args.project}-audit.md")
    audit_path.write_text(fmt_md_table(rows, headers) + "\n")
    print(f"wrote {audit_path}")

    if untracked:
        drops_path = pathlib.Path(f"{args.project}-drops.sql")
        drops_path.write_text(
            "\n".join(
                drop_statement(obj)
                for obj in sorted(untracked, key=lambda o: (o.dataset, o.name))
            )
            + "\n"
        )
        print(f"wrote {drops_path}")


if __name__ == "__main__":
    main()
