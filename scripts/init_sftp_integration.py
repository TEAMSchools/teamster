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


def find_first_match(
    sftp: paramiko.SFTPClient, path: str, pattern: str | None
) -> str | None:
    for attr in sftp.listdir_attr(path):
        if pattern and pattern not in attr.filename:
            continue
        return f"{path}/{attr.filename}" if path != "/" else f"/{attr.filename}"
    return None


def download_to_temp(
    sftp: paramiko.SFTPClient, path: str, pattern: str | None
) -> Path | None:
    remote_path = find_first_match(sftp, path, pattern)

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
        remote_path = find_first_match(sftp, args.path, args.pattern)

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


def cmd_scaffold(args: argparse.Namespace) -> None:
    raise NotImplementedError("scaffold subcommand not yet implemented")


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
