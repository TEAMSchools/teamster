# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "defusedxml>=0.7",
#   "requests>=2.32",
#   "pyyaml>=6.0",
# ]
# ///

import argparse
import getpass
import io
import os
import pathlib
import zipfile

import defusedxml.ElementTree as ET
import requests
import yaml

EXPOSURES_PATH = pathlib.Path("src/dbt/kipptaf/models/exposures/tableau.yml")
TABLEAU_API_VERSION = "3.20"


# ── XML extraction ──────────────────────────────────────────────────────────


def extract_twb_bytes(path: pathlib.Path) -> bytes:
    """Return the raw .twb XML bytes from a .twbx zip or a plain .twb file."""
    if path.suffix == ".twbx":
        with zipfile.ZipFile(path) as zf:
            twb_name = next(n for n in zf.namelist() if n.endswith(".twb"))
            return zf.read(twb_name)
    return path.read_bytes()


def extract_twb_bytes_from_bytes(raw: bytes) -> bytes:
    """Extract .twb XML bytes from in-memory .twbx zip bytes."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        twb_name = next(n for n in zf.namelist() if n.endswith(".twb"))
        return zf.read(twb_name)


def parse_calculated_fields(twb_bytes: bytes) -> list[dict]:
    """Return user-created calculated fields from .twb XML bytes."""
    root = ET.fromstring(twb_bytes)
    fields = []

    for column in root.iter("column"):
        calc = column.find("calculation[@class='tableau']")
        if calc is None:
            continue

        name = column.get("name", "")
        caption = column.get("caption", "")

        # skip Tableau internals
        if not caption or name.startswith("[:") or name == "[Number of Records]":
            continue

        fields.append(
            {
                "name": caption,
                "datatype": column.get("datatype", "unknown"),
                "formula": calc.get("formula", ""),
            }
        )

    return fields


# ── Tableau Server REST API ─────────────────────────────────────────────────


def signin_pat(server: str, site: str, token_name: str, pat: str) -> tuple[str, str]:
    """Return (token, site_id) using Personal Access Token auth."""
    url = f"{server}/api/{TABLEAU_API_VERSION}/auth/signin"
    payload = {
        "credentials": {
            "personalAccessTokenName": token_name,
            "personalAccessTokenSecret": pat,
            "site": {"contentUrl": site},
        }
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["credentials"]["token"], data["credentials"]["site"]["id"]


def signin_password(
    server: str, site: str, username: str, password: str
) -> tuple[str, str]:
    """Return (token, site_id) using username/password auth."""
    url = f"{server}/api/{TABLEAU_API_VERSION}/auth/signin"
    payload = {
        "credentials": {
            "name": username,
            "password": password,
            "site": {"contentUrl": site},
        }
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["credentials"]["token"], data["credentials"]["site"]["id"]


def get_auth_token(server: str, site: str, username: str | None) -> tuple[str, str]:
    """
    Authenticate to Tableau Server.

    Prefers PAT from TABLEAU_TOKEN_NAME + TABLEAU_PERSONAL_ACCESS_TOKEN env
    vars. Falls back to username/password (prompts via getpass) when --username
    is supplied and PAT env vars are absent.
    """
    token_name = os.environ.get("TABLEAU_TOKEN_NAME")
    pat = os.environ.get("TABLEAU_PERSONAL_ACCESS_TOKEN")

    if token_name and pat:
        return signin_pat(server, site, token_name, pat)

    if username:
        password = getpass.getpass(f"Password for {username}: ")
        return signin_password(server, site, username, password)

    raise SystemExit(
        "No auth credentials found. Either set TABLEAU_TOKEN_NAME and "
        "TABLEAU_PERSONAL_ACCESS_TOKEN environment variables, or pass --username."
    )


def download_workbook_by_id(
    server: str, site_id: str, workbook_id: str, token: str
) -> bytes:
    """Download a workbook .twbx by its LSID and return the raw bytes."""
    url = (
        f"{server}/api/{TABLEAU_API_VERSION}"
        f"/sites/{site_id}/workbooks/{workbook_id}/content"
    )
    resp = requests.get(url, headers={"x-tableau-auth": token}, stream=True, timeout=60)
    resp.raise_for_status()
    return resp.content


def find_workbook_id_by_name(
    server: str, site_id: str, workbook_name: str, token: str
) -> str:
    """Look up a workbook's ID by name via the REST API."""
    url = f"{server}/api/{TABLEAU_API_VERSION}/sites/{site_id}/workbooks"
    resp = requests.get(
        url,
        headers={"x-tableau-auth": token},
        params={"filter": f"name:eq:{workbook_name}"},
        timeout=30,
    )
    resp.raise_for_status()
    workbooks = resp.json().get("workbooks", {}).get("workbook", [])
    if not workbooks:
        raise ValueError(f"No workbook found with name: {workbook_name!r}")
    return workbooks[0]["id"]


# ── Exposure lookup ─────────────────────────────────────────────────────────


def load_exposure(exposure_name: str) -> dict:
    """Return the exposure dict for a given name from tableau.yml."""
    data = yaml.safe_load(EXPOSURES_PATH.read_text())
    for exposure in data.get("exposures", []):
        if exposure["name"] == exposure_name:
            return exposure
    raise ValueError(
        f"Exposure {exposure_name!r} not found in {EXPOSURES_PATH}.\n"
        f"Available: {[e['name'] for e in data.get('exposures', [])]}"
    )


def get_workbook_id_from_exposure(exposure: dict) -> str | None:
    return (
        exposure.get("config", {})
        .get("meta", {})
        .get("dagster", {})
        .get("asset", {})
        .get("metadata", {})
        .get("id")
    )


def get_depends_on_from_exposure(exposure: dict) -> list[str]:
    return exposure.get("depends_on", [])


# ── Output ──────────────────────────────────────────────────────────────────


def print_results(
    fields: list[dict],
    workbook_label: str,
    depends_on: list[str] | None = None,
) -> None:
    print(f"\n## Calculated Fields: {workbook_label}\n")

    if depends_on:
        print("### dbt models (from exposure depends_on)\n")
        for dep in depends_on:
            print(f"  - {dep}")
        print()

    if not fields:
        print("No user-created calculated fields found.\n")
        return

    print("| Field Name | Data Type | Formula |")
    print("|---|---|---|")
    for f in fields:
        formula = f["formula"].replace("\n", " ").replace("|", "\\|")
        print(f"| {f['name']} | {f['datatype']} | {formula} |")

    print(f"\nTotal: {len(fields)} calculated fields\n")


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract calculated fields from a Tableau workbook.",
        add_help=True,
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--file",
        type=pathlib.Path,
        metavar="PATH",
        help="Path to a local .twbx or .twb file",
    )
    source.add_argument(
        "--exposure",
        metavar="NAME",
        help=(
            "Exposure name from src/dbt/kipptaf/models/exposures/tableau.yml "
            "(e.g. gradebook_and_gpa_dashboard). Looks up the workbook LSID "
            "and depends_on models automatically."
        ),
    )
    source.add_argument(
        "--workbook",
        metavar="NAME",
        help="Tableau Server workbook name (manual fallback — requires --server)",
    )

    server_group = parser.add_argument_group("Tableau Server options")
    server_group.add_argument(
        "--server",
        metavar="URL",
        default=os.environ.get("TABLEAU_SERVER_ADDRESS"),
        help="Tableau Server base URL (default: $TABLEAU_SERVER_ADDRESS)",
    )
    server_group.add_argument(
        "--site",
        metavar="NAME",
        default=os.environ.get("TABLEAU_SITE_ID", ""),
        help="Site name (default: $TABLEAU_SITE_ID)",
    )
    server_group.add_argument(
        "--username",
        metavar="EMAIL",
        help=(
            "Username for password auth. Omit if TABLEAU_TOKEN_NAME and "
            "TABLEAU_PERSONAL_ACCESS_TOKEN env vars are set (preferred)."
        ),
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Print exposure metadata only — no download or file parsing",
    )

    args = parser.parse_args()

    depends_on: list[str] = []

    # ── Local file mode ──────────────────────────────────────────────────
    if args.file:
        twb_bytes = extract_twb_bytes(args.file)
        fields = parse_calculated_fields(twb_bytes)
        print_results(fields, args.file.stem)
        return

    # ── Exposure mode ────────────────────────────────────────────────────
    if args.exposure:
        exposure = load_exposure(args.exposure)
        workbook_label = exposure.get("label", args.exposure)
        workbook_id = get_workbook_id_from_exposure(exposure)
        depends_on = get_depends_on_from_exposure(exposure)

        if args.list_only:
            print(f"\n## Exposure: {workbook_label}")
            print(f"  Workbook LSID : {workbook_id or '(not set)'}")
            print("  depends_on    :")
            for dep in depends_on:
                print(f"    - {dep}")
            print()
            return

        if not workbook_id:
            parser.error(
                f"Exposure {args.exposure!r} has no workbook ID in tableau.yml. "
                "Use --workbook instead."
            )

        if not args.server:
            parser.error("--server is required (or set TABLEAU_SERVER_ADDRESS env var)")

        token, site_id = get_auth_token(args.server, args.site, args.username)
        raw = download_workbook_by_id(args.server, site_id, workbook_id, token)
        twb_bytes = extract_twb_bytes_from_bytes(raw)
        fields = parse_calculated_fields(twb_bytes)
        print_results(fields, workbook_label, depends_on)
        return

    # ── Manual server mode ───────────────────────────────────────────────
    if args.workbook:
        if not args.server:
            parser.error("--server is required (or set TABLEAU_SERVER_ADDRESS env var)")

        token, site_id = get_auth_token(args.server, args.site, args.username)
        workbook_id = find_workbook_id_by_name(
            args.server, site_id, args.workbook, token
        )
        raw = download_workbook_by_id(args.server, site_id, workbook_id, token)
        twb_bytes = extract_twb_bytes_from_bytes(raw)
        fields = parse_calculated_fields(twb_bytes)
        print_results(fields, args.workbook)


if __name__ == "__main__":
    main()
