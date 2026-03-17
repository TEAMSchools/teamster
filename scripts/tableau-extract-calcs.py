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
import sys
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


def _is_internal(column) -> bool:
    name = column.get("name", "")
    caption = column.get("caption", "")
    return not caption or name.startswith("[:") or name == "[Number of Records]"


def _extract_fields(datasource) -> list[dict]:
    fields = []
    for column in datasource.findall("column"):
        calc = column.find("calculation[@class='tableau']")
        if calc is None or _is_internal(column):
            continue
        fields.append(
            {
                "name": column.get("caption"),
                "datatype": column.get("datatype", "unknown"),
                "formula": calc.get("formula", ""),
            }
        )
    return fields


def list_datasources(twb_bytes: bytes) -> list[dict]:
    """
    Return unique datasources with calc counts, deduplicated by caption.
    Only the first occurrence of each caption is kept (subsequent copies are
    per-worksheet duplicates with no calcs). Skips 'Parameters'.
    """
    root = ET.fromstring(twb_bytes)
    seen: set[str] = set()
    sources = []
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters" or caption in seen:
            continue
        seen.add(caption)
        sources.append({"caption": caption, "n_calcs": len(_extract_fields(ds))})
    return sources


def parse_calculated_fields(
    twb_bytes: bytes, datasource: str | None = None
) -> list[dict]:
    """
    Return user-created calculated fields from .twb XML bytes.

    If datasource is given, restrict to the first datasource whose caption
    contains that string (case-insensitive). Otherwise returns fields from
    all non-Parameters datasources (deduplicated).
    """
    root = ET.fromstring(twb_bytes)
    seen: set[str] = set()
    fields = []

    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters" or caption in seen:
            continue
        seen.add(caption)

        if datasource and datasource.lower() not in caption.lower():
            continue

        fields.extend(_extract_fields(ds))

    return fields


# ── Tableau Server REST API ─────────────────────────────────────────────────


_JSON_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


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
    resp = requests.post(url, json=payload, headers=_JSON_HEADERS, timeout=30)
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
    resp = requests.post(url, json=payload, headers=_JSON_HEADERS, timeout=30)
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
        headers={**_JSON_HEADERS, "x-tableau-auth": token},
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


def print_datasource_picker(sources: list[dict], workbook_label: str) -> None:
    print(f"\n## Data sources in: {workbook_label}\n")
    print(f"  {'Data Source':<55} Calcs")
    print(f"  {'-' * 55} -----")
    for s in sources:
        print(f"  {s['caption']:<55} {s['n_calcs']}")
    print(
        "\nRe-run with --datasource / -d to filter to one source, e.g.:\n"
        "  ... -d 'gradebook_gpa_cumulative'\n"
    )


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


# ── Interactive mode ─────────────────────────────────────────────────────────


def _pick(prompt: str, options: list[str]) -> str:
    """Print a numbered list and return the chosen item."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i:>2}. {opt}")
    while True:
        raw = input("\nEnter number or name: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        else:
            matches = [o for o in options if raw.lower() in o.lower()]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                print(f"  Ambiguous — matched: {matches}")
                continue
        print(
            f"  Invalid choice. Enter a number (1–{len(options)}) or a name substring."
        )


def run_interactive() -> None:
    """Guided prompt sequence when the script is run with no arguments."""
    print("\nTableau → dbt upstream extractor")
    print("=" * 40)

    # ── Step 1: pick an exposure ─────────────────────────────────────────
    data = yaml.safe_load(EXPOSURES_PATH.read_text())
    exposures = data.get("exposures", [])
    exposure_names = [e["name"] for e in exposures]
    chosen_exposure_name = _pick(
        "Which Tableau workbook? (exposure name)", exposure_names
    )
    exposure = next(e for e in exposures if e["name"] == chosen_exposure_name)
    workbook_label = exposure.get("label", chosen_exposure_name)
    workbook_id = get_workbook_id_from_exposure(exposure)
    depends_on = get_depends_on_from_exposure(exposure)

    if not workbook_id:
        raise SystemExit(
            f"\nExposure {chosen_exposure_name!r} has no workbook ID in tableau.yml.\n"
            "Ask a data engineer to add the Tableau LSID to the exposure config."
        )

    # ── Step 2: authenticate & download ─────────────────────────────────
    server = os.environ.get("TABLEAU_SERVER_ADDRESS")
    site = os.environ.get("TABLEAU_SITE_ID", "")
    if not server:
        server = input("\nTableau Server URL: ").strip()

    print(f"\nConnecting to {server} …")
    token, site_id = get_auth_token(server, site, username=None)
    print("Downloading workbook …")
    raw = download_workbook_by_id(server, site_id, workbook_id, token)
    twb_bytes = extract_twb_bytes_from_bytes(raw)

    # ── Step 3: pick a datasource ────────────────────────────────────────
    sources = list_datasources(twb_bytes)
    source_labels = [f"{s['caption']}  ({s['n_calcs']} calcs)" for s in sources]
    chosen_label = _pick("Which data source?", source_labels)
    chosen_caption = sources[source_labels.index(chosen_label)]["caption"]

    # ── Step 4: extract and print ────────────────────────────────────────
    fields = parse_calculated_fields(twb_bytes, chosen_caption)
    print_results(fields, workbook_label, depends_on)


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract calculated fields from a Tableau workbook.",
        add_help=True,
    )

    if len(sys.argv) == 1:
        run_interactive()
        return

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
        "--datasource",
        "-d",
        metavar="NAME",
        help=(
            "Filter to a specific data source (case-insensitive substring match "
            "on the datasource caption). Omit to see a list of available sources."
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
        if not args.datasource:
            print_datasource_picker(list_datasources(twb_bytes), args.file.stem)
            return
        fields = parse_calculated_fields(twb_bytes, args.datasource)
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
        if not args.datasource:
            print_datasource_picker(list_datasources(twb_bytes), workbook_label)
            return
        fields = parse_calculated_fields(twb_bytes, args.datasource)
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
        if not args.datasource:
            print_datasource_picker(list_datasources(twb_bytes), args.workbook)
            return
        fields = parse_calculated_fields(twb_bytes, args.datasource)
        print_results(fields, args.workbook)


if __name__ == "__main__":
    main()
