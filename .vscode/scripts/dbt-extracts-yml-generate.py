from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///


sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.dbt_yml_utils import (  # trunk-ignore(pyright/reportMissingImports): runtime sys.path insert
    find_first_select,
    parse_select_columns,
    query_column_types,
    resolve_schema,
    strip_jinja,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFERRALS_PATH = Path(__file__).resolve().parents[1] / ".yml-sync-deferrals.json"

# ---------------------------------------------------------------------------
# Deferral helpers
# ---------------------------------------------------------------------------


def load_deferrals() -> dict:
    """Load deferral state from JSON file. Returns empty dict if missing."""
    if DEFERRALS_PATH.exists():
        with DEFERRALS_PATH.open() as f:
            return json.load(f)
    return {}


def save_deferrals(deferrals: dict) -> None:
    """Persist deferral state to JSON file."""
    DEFERRALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DEFERRALS_PATH.open("w") as f:
        json.dump(deferrals, f, indent=2)
        f.write("\n")


def defer_model(model_name: str, until: str = "next", count: int = 1) -> None:
    """Add or update a deferral entry for a model.

    until="next"  — ask again next commit (count ignored)
    until="count" — skip N commits (count=N)
    """
    deferrals = load_deferrals()
    if until == "next":
        deferrals[model_name] = {"mode": "next"}
    else:
        deferrals[model_name] = {"mode": "count", "remaining": count}
    save_deferrals(deferrals)
    print(f"Deferred YML check for {model_name!r} ({until}, count={count})")
    print(f"Deferral state: {DEFERRALS_PATH}")


# ---------------------------------------------------------------------------
# YML generation
# ---------------------------------------------------------------------------


def generate_yml(sql_path: Path) -> Path:
    """Generate a complete YML property file for a new extract model.

    Parses the first SELECT to get column names (in order), queries
    BigQuery INFORMATION_SCHEMA.COLUMNS for data_types, and writes a
    complete YML with contract enforcement and a uniqueness test stub.

    Returns the path to the written YML file.
    """
    sql_path = Path(sql_path).resolve()

    if not sql_path.exists():
        print(f"Error: SQL file not found: {sql_path}", file=sys.stderr)
        sys.exit(1)

    model_name = sql_path.stem

    # Parse SQL columns
    sql_text = sql_path.read_text(encoding="utf-8")
    try:
        stripped = strip_jinja(sql_text)
        body = find_first_select(stripped)
        sql_columns = parse_select_columns(body)
    except ValueError as exc:
        print(f"Error: Could not parse SQL in {sql_path.name}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not sql_columns:
        print(f"Error: No columns found in {sql_path.name}", file=sys.stderr)
        sys.exit(1)

    # Resolve BigQuery schema and query column types
    try:
        rel_path = sql_path.relative_to(REPO_ROOT)
        schema = resolve_schema(rel_path, repo_root=REPO_ROOT)
    except Exception as exc:
        print(
            f"Warning: Could not resolve schema for {sql_path.name}: {exc}",
            file=sys.stderr,
        )
        schema = None

    bq_types: dict[str, str] = {}
    if schema is not None:
        bq_types = query_column_types(model_name, schema)

    # Build the uniqueness test stub using the first two columns
    combo_cols = sql_columns[:2]

    # Build columns list
    columns = []
    for col_name in sql_columns:
        col: dict = {"name": col_name}
        if col_name in bq_types:
            col["data_type"] = bq_types[col_name]
        else:
            col["data_type"] = ""
        columns.append(col)

    # Assemble the YAML structure (preserve key order via dict)
    model_doc: dict = {
        "name": model_name,
        "config": {"contract": {"enforced": True}},
        "description": "TODO: set the correct unique key columns in data_tests below",
        "data_tests": [
            {
                "dbt_utils.unique_combination_of_columns": {
                    "arguments": {"combination_of_columns": combo_cols},
                    "config": {"store_failures": True},
                }
            }
        ],
        "columns": columns,
    }
    data = {"models": [model_doc]}

    # Determine output path
    yml_path = sql_path.parent / "properties" / f"{model_name}.yml"
    yml_path.parent.mkdir(parents=True, exist_ok=True)

    # Dump to YAML — sort_keys=False preserves insertion order
    with yml_path.open("w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    print(f"Generated: {yml_path}")
    print("TODO: review the data_tests section and set the correct unique key columns")

    return yml_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a complete dbt properties YML for a new extract model, "
            "or defer the YML check for a model."
        )
    )
    parser.add_argument(
        "sql_file",
        metavar="SQL_FILE",
        help="Path to the dbt extract SQL model file",
    )
    parser.add_argument(
        "--defer",
        action="store_true",
        help="Defer the YML check instead of generating",
    )
    defer_group = parser.add_mutually_exclusive_group()
    defer_group.add_argument(
        "--defer-until",
        metavar="WHEN",
        default="next",
        choices=["next"],
        help="Ask again next commit (default: next)",
    )
    defer_group.add_argument(
        "--defer-for",
        metavar="N",
        type=int,
        help="Skip N commits before asking again",
    )

    args = parser.parse_args()

    sql_path = Path(args.sql_file)
    model_name = sql_path.stem

    if args.defer:
        if args.defer_for is not None:
            defer_model(model_name, until="count", count=args.defer_for)
        else:
            defer_model(model_name, until=args.defer_until)
    else:
        generate_yml(sql_path)


if __name__ == "__main__":
    main()
