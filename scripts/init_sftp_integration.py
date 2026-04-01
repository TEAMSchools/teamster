# /// script
# requires-python = ">=3.13"
# dependencies = ["paramiko", "python-slugify"]
# ///

import argparse
import csv
import os
import re
import sys
import tempfile
from pathlib import Path

import paramiko
from slugify import slugify

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_sftp_client(resource_name: str, code_location: str) -> paramiko.SFTPClient:
    name = resource_name.upper()
    loc = code_location.upper()

    required_vars = {
        "host": f"{name}_SFTP_HOST",
        "username": f"{name}_SFTP_USERNAME_{loc}",
        "password": f"{name}_SFTP_PASSWORD_{loc}",
    }

    missing = [v for v in required_vars.values() if v not in os.environ]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    host = os.environ[required_vars["host"]]
    username = os.environ[required_vars["username"]]
    password = os.environ[required_vars["password"]]
    port = int(os.environ.get(f"{name}_SFTP_PORT", "22"))

    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)

    client = paramiko.SFTPClient.from_transport(transport)

    if client is None:
        msg = f"Failed to open SFTP session to {host}"
        raise ConnectionError(msg)

    return client


def close_sftp(sftp: paramiko.SFTPClient) -> None:
    channel = sftp.get_channel()

    if channel is not None:
        transport = channel.get_transport()

        if transport is not None:
            transport.close()


def normalize_field_name(header: str) -> str:
    return slugify(text=header, separator="_")


def _to_schema_const(class_name: str) -> str:
    return (
        re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])|(?<=[a-z])(?=[A-Z])", "_", class_name).upper()
        + "_SCHEMA"
    )


def read_csv_headers(file_path: str | Path) -> list[str]:
    with Path(file_path).open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        raw_headers = next(reader)

    return [normalize_field_name(h) for h in raw_headers]


def find_latest_match(
    sftp: paramiko.SFTPClient, path: str, pattern: str | None
) -> str | None:
    matches = [
        attr
        for attr in sftp.listdir_attr(path)
        if not pattern or pattern in attr.filename
    ]
    matches.sort(key=lambda a: a.st_mtime or 0, reverse=True)

    if not matches:
        return None

    filename = matches[0].filename
    return f"{path}/{filename}" if path != "/" else f"/{filename}"


def download_to_temp(
    sftp: paramiko.SFTPClient, path: str, pattern: str | None
) -> Path | None:
    remote_path = find_latest_match(sftp, path, pattern)

    if remote_path is None:
        return None

    fd, tmp_path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    tmp = Path(tmp_path)
    sftp.get(remote_path, str(tmp))

    return tmp


def generate_pydantic_class(class_name: str, fields: list[str]) -> str:
    lines = [
        f"class {class_name}(SFTPFile):",
    ]

    for field in fields:
        if field == "source_file_name":
            continue
        lines.append(f"    {field}: str | None = None")

    return "\n".join(lines)


def get_headers_from_args(args: argparse.Namespace) -> list[str]:
    if args.local:
        return read_csv_headers(args.local)

    if not args.resource or not args.code_location or not args.path:
        print(
            "resource, code_location, and path are required when --local is not used.",
            file=sys.stderr,
        )
        sys.exit(1)

    sftp = get_sftp_client(args.resource, args.code_location)

    try:
        tmp = download_to_temp(sftp, args.path, args.pattern)

        if tmp is None:
            print("No matching file found.", file=sys.stderr)
            sys.exit(1)

        try:
            return read_csv_headers(str(tmp))
        finally:
            tmp.unlink()
    finally:
        close_sftp(sftp)


def cmd_list(args: argparse.Namespace) -> None:
    sftp = get_sftp_client(args.resource, args.code_location)

    try:
        match_count = 0

        for attr in sftp.listdir_attr(args.path):
            filename = attr.filename

            if args.pattern and args.pattern not in filename:
                continue

            match_count += 1
            size_kb = (attr.st_size or 0) / 1024
            print(f"{size_kb:>10.1f} KB  {filename}")

        if match_count == 0:
            pattern_msg = f" matching '{args.pattern}'" if args.pattern else ""
            print(
                f"WARNING: No files found{pattern_msg} in {args.path} "
                f"on {args.code_location}",
                file=sys.stderr,
            )
    finally:
        close_sftp(sftp)


def cmd_download(args: argparse.Namespace) -> None:
    sftp = get_sftp_client(args.resource, args.code_location)

    try:
        remote_path = find_latest_match(sftp, args.path, args.pattern)

        if remote_path is None:
            print("No matching file found.", file=sys.stderr)
            sys.exit(1)

        print(f"Downloading {remote_path} -> {args.output}")
        sftp.get(remote_path, args.output)
        print("Done.")
    finally:
        close_sftp(sftp)


def cmd_codegen(args: argparse.Namespace) -> None:
    headers = get_headers_from_args(args)
    print(generate_pydantic_class(args.class_name, headers))


def _model_name(resource: str, subpath: list[str], asset_name: str) -> str:
    subpath_joined = "__".join(subpath)
    return f"stg_{resource}__{subpath_joined}__{asset_name}"


def _source_name(resource: str, subpath: list[str]) -> str:
    return f"{resource}_{'_'.join(subpath)}"


def _gcs_subpath(resource: str, subpath: list[str]) -> str:
    return f"{resource}/{'/'.join(subpath)}"


def scaffold_pydantic_schema(
    resource: str, subpath: list[str], class_name: str, fields: list[str]
) -> None:
    schema_path = (REPO_ROOT / "src" / "teamster" / "libraries" / resource).joinpath(
        *subpath
    ) / "schema.py"

    existing = schema_path.read_text()

    if f"class {class_name}" in existing:
        print(
            f"  Pydantic schema: {schema_path.relative_to(REPO_ROOT)} (skipped, already exists)"
        )
        return

    class_code = generate_pydantic_class(class_name, fields)
    schema_path.write_text(f"{existing}\n\n{class_code}\n")

    print(f"  Pydantic schema: {schema_path.relative_to(REPO_ROOT)}")


def scaffold_avro_schema(
    resource: str, subpath: list[str], class_name: str, code_locations: list[str]
) -> None:
    schema_const = _to_schema_const(class_name)

    for loc in code_locations:
        schema_path = (
            REPO_ROOT / "src" / "teamster" / "code_locations" / loc / resource
        ).joinpath(*subpath) / "schema.py"

        existing = schema_path.read_text()

        if schema_const in existing:
            print(
                f"  Avro schema: {schema_path.relative_to(REPO_ROOT)} (skipped, already exists)"
            )
            continue

        import_marker = ")\n\npas_options"
        if import_marker not in existing:
            print(
                f"  Avro schema: {schema_path.relative_to(REPO_ROOT)}"
                f" (skipped, unexpected file format)"
            )
            continue

        existing = existing.replace(
            import_marker,
            f"    {class_name},\n)\n\npas_options",
        )

        new_const = (
            f"\n{schema_const} = json.loads(\n"
            f"    py_avro_schema.generate(py_type={class_name}, options=pas_options)\n"
            f")\n"
        )
        existing = existing.rstrip() + "\n" + new_const

        schema_path.write_text(existing)

        print(f"  Avro schema: {schema_path.relative_to(REPO_ROOT)}")


def scaffold_dagster_asset(
    resource: str,
    subpath: list[str],
    class_name: str,
    asset_name: str,
    code_locations: list[str],
) -> None:
    schema_const = _to_schema_const(class_name)
    asset_key_segments = ", ".join(f'"{s}"' for s in [resource, *subpath, asset_name])

    for loc in code_locations:
        assets_path = (
            REPO_ROOT / "src" / "teamster" / "code_locations" / loc / resource
        ).joinpath(*subpath) / "assets.py"

        existing = assets_path.read_text()

        if f"{asset_name} = build_sftp_file_asset" in existing:
            print(
                f"  Asset: {assets_path.relative_to(REPO_ROOT)} (skipped, already exists)"
            )
            continue

        existing = existing.replace(
            ")\nfrom teamster.libraries.sftp",
            f"    {schema_const},\n)\nfrom teamster.libraries.sftp",
        )

        asset_block = (
            f"\n{asset_name} = build_sftp_file_asset(\n"
            f"    asset_key=[CODE_LOCATION, {asset_key_segments}],\n"
            f"    remote_dir_regex=...,  # TODO: fill in remote dir regex\n"
            f"    remote_file_regex=...,  # TODO: fill in regex pattern\n"
            f'    ssh_resource_key="ssh_{resource}",\n'
            f"    avro_schema={schema_const},\n"
            f"    partitions_def=partitions_def,\n"
            f"    ignore_multiple_matches=True,\n"
            f")\n"
        )

        existing = existing.replace(
            "\nassets = [",
            f"{asset_block}\nassets = [",
        )
        existing = existing.replace(
            "\n]\n",
            f"    {asset_name},\n]\n",
        )

        assets_path.write_text(existing)

        print(f"  Asset: {assets_path.relative_to(REPO_ROOT)}")


def scaffold_integration_test(
    resource: str, subpath: list[str], asset_name: str, code_locations: list[str]
) -> None:
    test_path = REPO_ROOT / "tests" / "assets" / f"test_assets_{resource}_sftp.py"
    import_subpath = ".".join(subpath)

    existing = test_path.read_text()
    modified = False

    for loc in code_locations:
        # Use kipptaf for kippnewark (existing convention in test file)
        test_loc = "kipptaf" if loc == "kippnewark" else loc

        # Convention: test name uses first subpath segment only (e.g., mclass)
        func_name = f"test_{resource}_{subpath[0]}_{asset_name}_{test_loc}"

        if func_name in existing:
            continue

        modified = True

        test_block = (
            f"\n\ndef {func_name}():\n"
            f"    from teamster.code_locations.{loc}.{resource}.{import_subpath}.assets import (\n"
            f"        {asset_name},\n"
            f"    )\n"
            f"\n"
            f'    _test_asset(code_location="{test_loc}", asset={asset_name})\n'
        )

        existing = existing.rstrip() + test_block

    if modified:
        test_path.write_text(existing + "\n")
        print(f"  Integration test: {test_path.relative_to(REPO_ROOT)}")
    else:
        print(
            f"  Integration test: {test_path.relative_to(REPO_ROOT)} (skipped, already exists)"
        )


def scaffold_dbt_source(resource: str, subpath: list[str], asset_name: str) -> None:
    sources_path = REPO_ROOT / "src" / "dbt" / resource / "models" / "sources.yml"
    source_name = _source_name(resource, subpath)
    gcs_subpath = _gcs_subpath(resource, subpath)
    asset_key_lines = "".join(
        f"                - {s}\n" for s in [resource, *subpath, asset_name]
    )

    source_entry = (
        f"      - name: {asset_name}\n"
        f"        external:\n"
        f"          location:\n"
        f"            \"{{{{ var('cloud_storage_uri_base')\n"
        f'            }}}}/{gcs_subpath}/{asset_name}/*"\n'
        f"          options:\n"
        f"            connection_name: \"{{{{ var('bigquery_external_connection_name') }}}}\"\n"
        f"            metadata_cache_mode: MANUAL\n"
        f"            max_staleness: INTERVAL 7 DAY\n"
        f"            hive_partition_uri_prefix:\n"
        f"              \"{{{{ var('cloud_storage_uri_base')\n"
        f'              }}}}/{gcs_subpath}/{asset_name}/"\n'
        f"            format: AVRO\n"
        f"            enable_logical_types: true\n"
        f"        config:\n"
        f"          meta:\n"
        f"            dagster:\n"
        f"              asset_key:\n"
        f'                - "{{{{ project_name }}}}"\n'
        f"{asset_key_lines}"
    )

    existing = sources_path.read_text()

    if f"- name: {asset_name}" in existing:
        print(
            f"  dbt source: {sources_path.relative_to(REPO_ROOT)} (skipped, already exists)"
        )
        return

    # Append to end of the matching source block
    source_header = f"  - name: {source_name}"
    if source_header in existing:
        # Find the next source definition after ours to insert before it
        header_pos = existing.index(source_header)
        rest = existing[header_pos + len(source_header) :]
        next_source = rest.find("\n  - name: ")
        if next_source >= 0:
            insert_pos = header_pos + len(source_header) + next_source + 1
            existing = existing[:insert_pos] + source_entry + existing[insert_pos:]
        else:
            existing = existing.rstrip() + "\n" + source_entry
    else:
        existing = existing.rstrip() + "\n" + source_entry

    sources_path.write_text(existing)

    print(f"  dbt source: {sources_path.relative_to(REPO_ROOT)}")


def scaffold_dbt_staging(resource: str, subpath: list[str], asset_name: str) -> None:
    model_name = _model_name(resource, subpath, asset_name)
    source_name = _source_name(resource, subpath)

    staging_dir = (REPO_ROOT / "src" / "dbt" / resource / "models").joinpath(
        *subpath
    ) / "staging"
    props_dir = staging_dir / "properties"
    props_dir.mkdir(parents=True, exist_ok=True)

    sql_path = staging_dir / f"{model_name}.sql"
    yml_path = props_dir / f"{model_name}.yml"

    sql_content = (
        # trunk-ignore(bandit/B608): dbt Jinja template, not executed SQL
        f"select *\n"
        f'from {{{{ source("{source_name}", "{asset_name}") }}}}\n'
        f"-- TODO: add type casts and derived columns\n"
    )

    yml_content = (
        f"models:\n"
        f"  - name: {model_name}\n"
        f"    config:\n"
        f"      contract:\n"
        f"        enforced: false\n"
        f"    # TODO: add columns, then set contract.enforced: true\n"
    )

    if sql_path.exists():
        print(
            f"  dbt staging SQL: {sql_path.relative_to(REPO_ROOT)}"
            f" (skipped, already exists)"
        )
    else:
        sql_path.write_text(sql_content)
        print(f"  dbt staging SQL: {sql_path.relative_to(REPO_ROOT)}")

    if yml_path.exists():
        print(
            f"  dbt staging YAML: {yml_path.relative_to(REPO_ROOT)}"
            f" (skipped, already exists)"
        )
    else:
        yml_path.write_text(yml_content)
        print(f"  dbt staging YAML: {yml_path.relative_to(REPO_ROOT)}")


def scaffold_kipptaf_union(
    resource: str, subpath: list[str], asset_name: str, code_locations: list[str]
) -> None:
    non_kipptaf = [loc for loc in code_locations if loc != "kipptaf"]

    if not non_kipptaf:
        return

    model_name = _model_name(resource, subpath, asset_name)

    source_pkg_dir = REPO_ROOT / "src" / "dbt" / resource / "models"
    staging_match = next(source_pkg_dir.rglob(f"{model_name}.sql"), None)

    if staging_match is None:
        print(f"  kipptaf union: could not find {model_name}.sql in {resource} package")
        return

    source_staging_dir = staging_match.parent
    relative_to_models = source_staging_dir.relative_to(source_pkg_dir)

    kipptaf_models_dir = REPO_ROOT / "src" / "dbt" / "kipptaf" / "models" / resource

    sources_match = next(kipptaf_models_dir.rglob("sources-kipp*.yml"), None)

    if sources_match is not None:
        sources_dir = sources_match.parent
    else:
        sources_dir = kipptaf_models_dir

    for loc in non_kipptaf:
        sources_path = sources_dir / f"sources-{loc}.yml"

        if not sources_path.exists():
            print(
                f"  kipptaf source: {sources_path.relative_to(REPO_ROOT)}"
                f" (skipped, file not found)"
            )
            continue

        existing = sources_path.read_text()

        if model_name in existing:
            print(
                f"  kipptaf source: {sources_path.relative_to(REPO_ROOT)}"
                f" (skipped, already exists)"
            )
            continue

        source_entry = (
            f"      - name: {model_name}\n"
            f"        config:\n"
            f"          meta:\n"
            f"            dagster:\n"
            f"              group: {resource}\n"
            f"              asset_key:\n"
            f"                - {loc}\n"
            f"                - {resource}\n"
            f"                - {model_name}\n"
        )

        existing = existing.rstrip() + "\n" + source_entry

        sources_path.write_text(existing)

        print(f"  kipptaf source: {sources_path.relative_to(REPO_ROOT)}")

    staging_dir = kipptaf_models_dir / relative_to_models
    props_dir = staging_dir / "properties"
    props_dir.mkdir(parents=True, exist_ok=True)

    sql_path = staging_dir / f"{model_name}.sql"
    yml_path = props_dir / f"{model_name}.yml"

    source_names = [f"{loc}_{resource}" for loc in non_kipptaf]

    if sql_path.exists():
        print(
            f"  kipptaf union SQL: {sql_path.relative_to(REPO_ROOT)}"
            f" (skipped, already exists)"
        )
    else:
        relations = ",\n                    ".join(
            f"source(\n"
            f'                        "{sn}",\n'
            f'                        "{model_name}",\n'
            f"                    )"
            for sn in source_names
        )

        sql_content = (
            # trunk-ignore(bandit/B608): dbt Jinja template, not executed SQL
            f"with\n"
            f"    union_relations as (\n"
            f"        {{{{\n"
            f"            dbt_utils.union_relations(\n"
            f"                relations=[\n"
            f"                    {relations},\n"
            f"                ]\n"
            f"            )\n"
            f"        }}}}\n"
            f"    )\n"
            f"\n"
            f"select *\n"
            f"from union_relations\n"
        )

        sql_path.write_text(sql_content)

        print(f"  kipptaf union SQL: {sql_path.relative_to(REPO_ROOT)}")

    if yml_path.exists():
        print(
            f"  kipptaf union YAML: {yml_path.relative_to(REPO_ROOT)}"
            f" (skipped, already exists)"
        )
    else:
        yml_content = f"models:\n  - name: {model_name}\n"

        yml_path.write_text(yml_content)

        print(f"  kipptaf union YAML: {yml_path.relative_to(REPO_ROOT)}")


def cmd_scaffold(args: argparse.Namespace) -> None:
    headers = get_headers_from_args(args)
    subpath = args.source_subpath.split("/")

    print(f"Scaffolding pipeline for {args.class_name}...")
    print(f"  Fields: {len(headers)}")
    print()

    scaffold_pydantic_schema(args.resource, subpath, args.class_name, headers)
    scaffold_avro_schema(args.resource, subpath, args.class_name, args.code_locations)
    scaffold_dagster_asset(
        args.resource, subpath, args.class_name, args.asset_name, args.code_locations
    )
    scaffold_integration_test(
        args.resource, subpath, args.asset_name, args.code_locations
    )
    scaffold_dbt_source(args.resource, subpath, args.asset_name)
    scaffold_dbt_staging(args.resource, subpath, args.asset_name)
    scaffold_kipptaf_union(args.resource, subpath, args.asset_name, args.code_locations)

    model_name = _model_name(args.resource, subpath, args.asset_name)
    source_name = _source_name(args.resource, subpath)
    staging_dir = f"src/dbt/{args.resource}/models/{args.source_subpath}/staging"
    test_file = f"tests/assets/test_assets_{args.resource}_sftp.py"

    print()
    print("Scaffold complete. Developer TODOs:")
    print()
    print("1. Fill in remote_dir_regex and remote_file_regex:")
    for loc in args.code_locations:
        assets_file = f"src/teamster/code_locations/{loc}/{args.resource}/{args.source_subpath}/assets.py"
        print(f"   - {assets_file}")
    print()
    print("2. Run integration test to materialize data:")
    print(f"   $ uv run pytest {test_file} -k {args.asset_name} -v")
    print()
    print("3. Stage external source:")
    for loc in args.code_locations:
        print(
            f"   $ uv run scripts/dbt-sxs.py {loc} --test --select {source_name}.{args.asset_name}"
        )
    print()
    print("4. Add type casts and derived columns:")
    print(f"   - {staging_dir}/{model_name}.sql")
    print()
    print("5. Add column definitions:")
    print(f"   - {staging_dir}/properties/{model_name}.yml")
    print()
    print("6. Build dbt model:")
    for loc in args.code_locations:
        print(f"   $ uv run dbt build -s {model_name} --project-dir src/dbt/{loc}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect and scaffold SFTP integrations"
    )

    # shared positional args for all subcommands
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("resource", help="SFTP resource name (e.g., amplify)")
    common.add_argument(
        "code_location",
        help="Code location for SFTP credentials (e.g., kipptaf, kipppaterson)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser(
        "list", parents=[common], help="List remote files"
    )
    list_parser.add_argument("path", help="Remote directory path")
    list_parser.add_argument("--pattern", help="Filename filter substring")

    # download
    dl_parser = subparsers.add_parser(
        "download", parents=[common], help="Download a sample file"
    )
    dl_parser.add_argument("path", help="Remote directory path")
    dl_parser.add_argument("--pattern", help="Filename filter substring")
    dl_parser.add_argument("--output", required=True, help="Local output path")

    # codegen
    cg_parser = subparsers.add_parser(
        "codegen", help="Generate Pydantic class from CSV headers"
    )
    cg_parser.add_argument("--local", help="Path to a local CSV file")
    cg_parser.add_argument("resource", nargs="?", help="SFTP resource name")
    cg_parser.add_argument(
        "code_location", nargs="?", help="Code location for credentials"
    )
    cg_parser.add_argument("path", nargs="?", help="Remote directory path")
    cg_parser.add_argument("--pattern", help="Filename filter substring")
    cg_parser.add_argument(
        "--class-name", required=True, help="Pydantic class name to generate"
    )

    # scaffold
    sc_parser = subparsers.add_parser(
        "scaffold", help="Generate full pipeline boilerplate"
    )
    sc_parser.add_argument("resource", help="SFTP resource name (e.g., amplify)")
    sc_parser.add_argument("--local", help="Path to a local CSV file")
    sc_parser.add_argument(
        "code_location", nargs="?", help="Code location for credentials"
    )
    sc_parser.add_argument("path", nargs="?", help="Remote directory path")
    sc_parser.add_argument("--pattern", help="Filename filter substring")
    sc_parser.add_argument(
        "--class-name", required=True, help="Pydantic class name to generate"
    )
    sc_parser.add_argument("--asset-name", required=True, help="Snake_case asset name")
    sc_parser.add_argument(
        "--source-subpath",
        required=True,
        help="Slash-separated subpath within resource (e.g., mclass/sftp)",
    )
    sc_parser.add_argument(
        "--code-locations",
        nargs="+",
        required=True,
        help="Code location names (e.g., kippnewark kipppaterson)",
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "codegen":
        cmd_codegen(args)
    elif args.command == "scaffold":
        cmd_scaffold(args)


if __name__ == "__main__":
    main()
