# /// script
# requires-python = ">=3.13"
# dependencies = ["paramiko"]
# ///

import argparse
import csv
import os
import re
import sys
import tempfile
from pathlib import Path

import paramiko

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_sftp_client(resource_name: str) -> paramiko.SFTPClient:
    name = resource_name.upper()
    host = os.environ[f"{name}_SFTP_HOST"]
    username = os.environ[f"{name}_SFTP_USERNAME"]
    password = os.environ[f"{name}_SFTP_PASSWORD"]
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
    name = header.strip().lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name


def read_csv_headers(file_path: str) -> list[str]:
    with open(file_path, newline="") as f:
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
    return None


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

    sftp = get_sftp_client(args.resource)

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
    sftp = get_sftp_client(args.resource)

    try:
        for attr in sftp.listdir_attr(args.path):
            filename = attr.filename

            if args.pattern and args.pattern not in filename:
                continue

            size_kb = (attr.st_size or 0) / 1024
            print(f"{size_kb:>10.1f} KB  {filename}")
    finally:
        close_sftp(sftp)


def cmd_download(args: argparse.Namespace) -> None:
    sftp = get_sftp_client(args.resource)

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


def scaffold_pydantic_schema(resource: str, class_name: str, fields: list[str]) -> None:
    schema_path = (
        REPO_ROOT
        / "src"
        / "teamster"
        / "libraries"
        / resource
        / "mclass"
        / "sftp"
        / "schema.py"
    )

    class_code = generate_pydantic_class(class_name, fields)

    existing = schema_path.read_text()
    schema_path.write_text(f"{existing}\n\n{class_code}\n")

    print(f"  Pydantic schema: {schema_path.relative_to(REPO_ROOT)}")


def scaffold_avro_schema(
    resource: str, class_name: str, code_locations: list[str]
) -> None:
    schema_const = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", class_name).upper() + "_SCHEMA"

    for loc in code_locations:
        schema_path = (
            REPO_ROOT
            / "src"
            / "teamster"
            / "code_locations"
            / loc
            / resource
            / "mclass"
            / "sftp"
            / "schema.py"
        )

        existing = schema_path.read_text()

        # Add import
        existing = existing.replace(
            ")\n\npas_options",
            f"    {class_name},\n)\n\npas_options",
        )

        # Add schema constant
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
    class_name: str,
    asset_name: str,
    code_locations: list[str],
) -> None:
    schema_const = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", class_name).upper() + "_SCHEMA"

    for loc in code_locations:
        assets_path = (
            REPO_ROOT
            / "src"
            / "teamster"
            / "code_locations"
            / loc
            / resource
            / "mclass"
            / "sftp"
            / "assets.py"
        )

        existing = assets_path.read_text()

        # Add schema import
        existing = existing.replace(
            ")\nfrom teamster.libraries.sftp",
            f"    {schema_const},\n)\nfrom teamster.libraries.sftp",
        )

        # Add asset definition before the assets list
        asset_block = (
            f"\n{asset_name} = build_sftp_file_asset(\n"
            f'    asset_key=[CODE_LOCATION, "{resource}", "mclass", "sftp", "{asset_name}"],\n'
            f'    remote_dir_regex=r"/PM",\n'
            f"    remote_file_regex=...,  # TODO: fill in regex pattern\n"
            f'    ssh_resource_key="ssh_{resource}",\n'
            f"    avro_schema={schema_const},\n"
            f"    partitions_def=partitions_def,\n"
            f"    ignore_multiple_matches=True,\n"
            f")\n"
        )

        # Add to assets list
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
    resource: str, asset_name: str, code_locations: list[str]
) -> None:
    test_path = REPO_ROOT / "tests" / "assets" / f"test_assets_{resource}_sftp.py"

    existing = test_path.read_text()

    for loc in code_locations:
        # Use kipptaf for kippnewark (existing convention in test file)
        test_loc = "kipptaf" if loc == "kippnewark" else loc

        func_name = f"test_{resource}_mclass_{asset_name}_{test_loc}"
        import_loc = loc

        test_block = (
            f"\n\ndef {func_name}():\n"
            f"    from teamster.code_locations.{import_loc}.{resource}.mclass.sftp.assets import (\n"
            f"        {asset_name},\n"
            f"    )\n"
            f"\n"
            f'    _test_asset(code_location="{test_loc}", asset={asset_name})\n'
        )

        existing = existing.rstrip() + test_block

    test_path.write_text(existing + "\n")

    print(f"  Integration test: {test_path.relative_to(REPO_ROOT)}")


def scaffold_dbt_source(resource: str, asset_name: str) -> None:
    sources_path = REPO_ROOT / "src" / "dbt" / resource / "models" / "sources.yml"

    source_entry = (
        f"      - name: {asset_name}\n"
        f"        external:\n"
        f"          location:\n"
        f"            \"{{{{ var('cloud_storage_uri_base')\n"
        f'            }}}}/{resource}/mclass/sftp/{asset_name}/*"\n'
        f"          options:\n"
        f"            connection_name: \"{{{{ var('bigquery_external_connection_name') }}}}\"\n"
        f"            metadata_cache_mode: MANUAL\n"
        f"            max_staleness: INTERVAL 7 DAY\n"
        f"            hive_partition_uri_prefix:\n"
        f"              \"{{{{ var('cloud_storage_uri_base')\n"
        f'              }}}}/{resource}/mclass/sftp/{asset_name}/"\n'
        f"            format: AVRO\n"
        f"            enable_logical_types: true\n"
        f"        config:\n"
        f"          meta:\n"
        f"            dagster:\n"
        f"              asset_key:\n"
        f'                - "{{{{ project_name }}}}"\n'
        f"                - {resource}\n"
        f"                - mclass\n"
        f"                - sftp\n"
        f"                - {asset_name}\n"
    )

    existing = sources_path.read_text()

    # Find the end of the amplify_mclass_sftp source block by locating
    # the next source definition
    marker = "  - name: amplify_mclass_api"
    existing = existing.replace(marker, source_entry + marker)

    sources_path.write_text(existing)

    print(f"  dbt source: {sources_path.relative_to(REPO_ROOT)}")


def scaffold_dbt_staging(resource: str, asset_name: str) -> None:
    model_name = f"stg_{resource}__mclass__sftp__{asset_name}"

    staging_dir = (
        REPO_ROOT / "src" / "dbt" / resource / "models" / "mclass" / "sftp" / "staging"
    )
    props_dir = staging_dir / "properties"
    props_dir.mkdir(parents=True, exist_ok=True)

    sql_path = staging_dir / f"{model_name}.sql"
    yml_path = props_dir / f"{model_name}.yml"

    sql_content = (
        f"select *\n"
        f'from {{{{ source("{resource}_mclass_sftp", "{asset_name}") }}}}\n'
        f"-- TODO: add type casts and derived columns\n"
    )

    yml_content = (
        f"models:\n"
        f"  - name: {model_name}\n"
        f"    config:\n"
        f"      contract:\n"
        f"        enforced: true\n"
        f"    # TODO: add columns\n"
    )

    sql_path.write_text(sql_content)
    yml_path.write_text(yml_content)

    print(f"  dbt staging SQL: {sql_path.relative_to(REPO_ROOT)}")
    print(f"  dbt staging YAML: {yml_path.relative_to(REPO_ROOT)}")


def cmd_scaffold(args: argparse.Namespace) -> None:
    headers = get_headers_from_args(args)

    print(f"Scaffolding pipeline for {args.class_name}...")
    print(f"  Fields: {len(headers)}")
    print()

    scaffold_pydantic_schema(args.resource, args.class_name, headers)
    scaffold_avro_schema(args.resource, args.class_name, args.code_locations)
    scaffold_dagster_asset(
        args.resource, args.class_name, args.asset_name, args.code_locations
    )
    scaffold_integration_test(args.resource, args.asset_name, args.code_locations)
    scaffold_dbt_source(args.resource, args.asset_name)
    scaffold_dbt_staging(args.resource, args.asset_name)

    model_name = f"stg_{args.resource}__mclass__sftp__{args.asset_name}"
    staging_dir = f"src/dbt/{args.resource}/models/mclass/sftp/staging"
    test_file = f"tests/assets/test_assets_{args.resource}_sftp.py"

    print()
    print("Scaffold complete. Developer TODOs:")

    for loc in args.code_locations:
        assets_file = (
            f"src/teamster/code_locations/{loc}/{args.resource}/mclass/sftp/assets.py"
        )
        print(f"  1. Fill in remote_file_regex: {assets_file}")

    print(f"  2. Add type casts and derived columns: {staging_dir}/{model_name}.sql")
    print(f"  3. Add column definitions: {staging_dir}/properties/{model_name}.yml")
    print(f"  4. Run integration test to materialize data: {test_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect and scaffold SFTP integrations"
    )

    parser.add_argument("resource", help="SFTP resource name (e.g., amplify)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    list_parser = subparsers.add_parser("list", help="List remote files")
    list_parser.add_argument("path", help="Remote directory path")
    list_parser.add_argument("--pattern", help="Filename filter substring")

    # download
    dl_parser = subparsers.add_parser("download", help="Download a sample file")
    dl_parser.add_argument("path", help="Remote directory path")
    dl_parser.add_argument("--pattern", help="Filename filter substring")
    dl_parser.add_argument("--output", required=True, help="Local output path")

    # codegen
    cg_parser = subparsers.add_parser(
        "codegen", help="Generate Pydantic class from CSV headers"
    )
    cg_parser.add_argument("path", nargs="?", help="Remote directory path")
    cg_parser.add_argument("--pattern", help="Filename filter substring")
    cg_parser.add_argument("--local", help="Path to a local CSV file")
    cg_parser.add_argument(
        "--class-name", required=True, help="Pydantic class name to generate"
    )

    # scaffold
    sc_parser = subparsers.add_parser(
        "scaffold", help="Generate full pipeline boilerplate"
    )
    sc_parser.add_argument("path", nargs="?", help="Remote directory path")
    sc_parser.add_argument("--pattern", help="Filename filter substring")
    sc_parser.add_argument("--local", help="Path to a local CSV file")
    sc_parser.add_argument(
        "--class-name", required=True, help="Pydantic class name to generate"
    )
    sc_parser.add_argument("--asset-name", required=True, help="Snake_case asset name")
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
