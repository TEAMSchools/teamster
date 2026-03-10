# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "google-cloud-bigquery",
#   "tabulate",
# ]
# ///

import itertools
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from google.cloud import bigquery
from tabulate import tabulate

_DROP_TYPE_MAP = {
    "VIEW": "VIEW",
    "MATERIALIZED_VIEW": "MATERIALIZED VIEW",
    "EXTERNAL": "EXTERNAL TABLE",
    "SNAPSHOT": "SNAPSHOT TABLE",
    "TABLE": "TABLE",
}

OUTPUT_DIR = Path("scripts/script_output")


@dataclass
class DbtRelation:
    database: str
    schema: str
    alias: str
    resource_type: str  # "model", "snapshot", or "source"
    materialization: str  # e.g. table/view/incremental/snapshot/source
    enabled: bool
    unique_id: str


@dataclass
class BqObject:
    project: str
    dataset: str
    name: str
    table_type: str


def find_kipp_projects() -> list[str]:
    return sorted(
        p.name
        for p in Path("src/dbt").iterdir()
        if p.is_dir() and p.name.startswith("kipp")
    )


def dbt_run(project: str, *args: str, target_path: str | None = None) -> None:
    cmd = ["dbt", *args, f"--project-dir=src/dbt/{project}", "--target=prod"]
    env = {
        **os.environ,
        "PATH": (
            os.environ["PATH"] + f":{Path(__file__).parent.parent / '.venv' / 'bin'}"
        ),
        # Ensure Jinja env_var() checks resolve to prod schema names.
        # GITHUB_USER must be cleared so sources using it as a schema prefix
        # (e.g. zz_{{ env_var('GITHUB_USER') }}_kipptaf_*) resolve correctly.
        "DBT_CLOUD_ENVIRONMENT_TYPE": "prod",
        "GITHUB_USER": "",
    }

    if target_path:
        cmd.append(f"--target-path={target_path}")

    # trunk-ignore(bandit/B603)
    subprocess.run(args=cmd, env=env, check=True)


def deps_needed(project: str) -> bool:
    """Return True if dbt deps must be run for the project.

    Compares the mtime of dbt_packages/ against packages.yml: if packages.yml
    is newer (or dbt_packages/ is missing), the installed packages are stale.
    """
    project_dir = Path("src/dbt") / project

    packages_file = project_dir / "packages.yml"
    packages_dir = project_dir / "dbt_packages"

    if not packages_dir.exists():
        return True

    if not packages_file.exists():
        return False

    return packages_file.stat().st_mtime > packages_dir.stat().st_mtime


def load_manifest(project: str) -> dict:
    with tempfile.TemporaryDirectory() as target_path:
        if deps_needed(project):
            dbt_run(project, "deps")
        dbt_run(project, "parse", target_path=target_path)

        path = Path(target_path) / "manifest.json"

        return json.loads(path.read_text(encoding="utf-8"))


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


def _parse_node(node: dict) -> tuple[tuple[str, str], str, str] | None:
    """Extract (key, alias, materialization) from a manifest node.

    Returns None for nodes that should be skipped (ephemeral models,
    non-kipp schemas for models/snapshots, missing relation_name).
    """
    resource_type = node["resource_type"]

    if resource_type == "model":
        materialization = node["config"].get("materialized", "table")

        if materialization == "ephemeral":
            return None

        key = relation_key(node)

        if key is None or not key[0].startswith("kipp"):
            return None

        alias = node.get("alias") or node["name"]
    elif resource_type == "snapshot":
        materialization = "snapshot"
        key = relation_key(node)

        if key is None or not key[0].startswith("kipp"):
            return None

        alias = node.get("alias") or node["name"]
    elif resource_type == "source":
        materialization = "source"
        key = relation_key(node)

        if key is None:
            return None

        alias = node.get("identifier") or node["name"]
    else:
        return None

    return key, alias, materialization


def collect_relations(manifests: list[dict]) -> dict[tuple[str, str], DbtRelation]:
    """Build combined dbt relations from all project manifests.

    Models: included if their schema starts with "kipp", covering both
    first-party models and packaged source-system models (e.g. powerschool)
    materialized into school-specific datasets.

    Sources: all sources from all manifests are included. This covers
    external sources (DLT, Airbyte) whose dataset names don't follow the
    kipp* prefix convention (e.g. dagster_kipptaf_dlt_*).

    First definition wins: models, sources, and disabled nodes do not overwrite
    an already-registered relation across manifests.
    """
    relations: dict[tuple[str, str], DbtRelation] = {}

    for manifest in manifests:
        for node_id, node in manifest["nodes"].items():
            parsed = _parse_node(node)

            if parsed is None:
                continue

            key, alias, materialization = parsed

            if key not in relations:
                relations[key] = DbtRelation(
                    database=node["database"],
                    schema=key[0],
                    alias=alias,
                    resource_type=node["resource_type"],
                    materialization=materialization,
                    enabled=True,
                    unique_id=node_id,
                )

        for node_id, node in manifest["sources"].items():
            parsed = _parse_node(node)

            if parsed is None:
                continue

            key, alias, materialization = parsed

            if key not in relations:
                relations[key] = DbtRelation(
                    database=node["database"],
                    schema=key[0],
                    alias=alias,
                    resource_type=node["resource_type"],
                    materialization=materialization,
                    enabled=True,
                    unique_id=node_id,
                )

        for node_id, node_list in manifest["disabled"].items():
            node = node_list[0]

            parsed = _parse_node(node)

            if parsed is None:
                continue

            key, alias, materialization = parsed

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
    existing_datasets = {d.dataset_id for d in client.list_datasets()}

    def list_dataset(dataset_id: str) -> list[tuple[tuple[str, str], BqObject]]:
        return [
            (
                (dataset_id, table.table_id),
                BqObject(
                    project=bq_project,
                    dataset=dataset_id,
                    name=table.table_id,
                    table_type=table.table_type,
                ),
            )
            for table in client.list_tables(f"{bq_project}.{dataset_id}")
            if not table.table_id.startswith("_dlt_")
        ]

    bq_objects: dict[tuple[str, str], BqObject] = {}

    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(list_dataset, dataset_id)
            for dataset_id in sorted(datasets & existing_datasets)
        ]

        for future in as_completed(futures):
            bq_objects.update(future.result())

    return bq_objects


def drop_statement(obj: BqObject) -> str:
    obj_type = _DROP_TYPE_MAP.get(obj.table_type, "TABLE")

    return f"DROP {obj_type} IF EXISTS `{obj.project}`.`{obj.dataset}`.`{obj.name}`;"


def main() -> None:
    projects = find_kipp_projects()

    print(f"projects: {', '.join(projects)}", file=sys.stderr)

    manifests = []
    bq_project = None

    for project in projects:
        print(f"parsing {project}...", file=sys.stderr)
        manifest = load_manifest(project)

        manifests.append(manifest)

        if bq_project is None:
            # NOTE: assumes single GCP project
            for node in itertools.chain(
                manifest["nodes"].values(), manifest["sources"].values()
            ):
                if node.get("database"):
                    bq_project = node["database"]
                    break

    if not bq_project:
        print("Error: could not determine BigQuery project ID.", file=sys.stderr)
        sys.exit(1)

    dbt_relations = collect_relations(manifests)

    datasets = {schema for schema, _ in dbt_relations}

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

    sorted_untracked = sorted(untracked, key=lambda o: (o.dataset, o.name))

    rows = []
    for obj in sorted_untracked:
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

    headers = {
        "object": "BigQuery Object",
        "status": "Status",
        "bq_type": "BQ Type",
        "dbt_type": "dbt Type",
    }

    OUTPUT_DIR.mkdir(exist_ok=True)

    audit_path = OUTPUT_DIR / "bq-audit.md"

    audit_path.write_text(
        tabulate(rows, headers=headers, tablefmt="github") + "\n", encoding="utf-8"
    )
    print(f"wrote {audit_path}")

    if sorted_untracked:
        drops_path = OUTPUT_DIR / "bq-drops.sql"

        drops_path.write_text(
            "\n".join(drop_statement(obj) for obj in sorted_untracked) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {drops_path}")


if __name__ == "__main__":
    main()
