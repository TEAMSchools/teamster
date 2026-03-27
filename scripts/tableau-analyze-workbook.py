# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "defusedxml>=0.7",
#   "requests>=2.32",
#   "pyyaml>=6.0",
# ]
# ///

"""Parse Tableau workbook XML and emit structured JSON with field metadata.

Supports two mutually exclusive input modes:

  --file <path>      Read a local .twb or .twbx file (primary, recommended)
  --exposure <name>  Fetch from Tableau Server via REST API (secondary)

Output is JSON to stdout matching the schema in:
  docs/superpowers/specs/2026-03-27-star-schema-advisor-design.md

Consumed by the /star-schema-advisor slash command.
"""

from __future__ import annotations

import argparse
import getpass
import io
import json
import os
import pathlib
import re
import sys
import zipfile

import defusedxml.ElementTree as ET
import requests
import yaml

EXPOSURES_PATH = pathlib.Path("src/dbt/kipptaf/models/exposures/tableau.yml")
TABLEAU_API_VERSION = "3.20"

_FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")
_LOD_RE = re.compile(r"\{\s*(FIXED|INCLUDE|EXCLUDE)\b", re.IGNORECASE)
# Matches compound Tableau shelf references: [datasource].[field] or
# [datasource].agg:[field]  — captures datasource, optional agg, and field.
_SHELF_REF_RE = re.compile(r"\[([^\]]+)\]\.(?:([A-Za-z]+):)?\[([^\]]+)\]")


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


# ── Datasource helpers ──────────────────────────────────────────────────────


def _is_internal(column) -> bool:
    """Return True for Tableau system fields that should be skipped."""
    name = column.get("name", "")
    caption = column.get("caption", "")
    return not caption or name.startswith("[:") or name == "[Number of Records]"


def _build_calc_name_map(datasource) -> dict[str, str]:
    """Map internal Tableau Calculation_* / *(copy)_* IDs to human captions."""
    name_map: dict[str, str] = {}
    for column in datasource.findall("column"):
        raw_name = column.get("name", "")
        caption = column.get("caption", "")
        name = raw_name.strip("[]")
        if caption and (name.startswith("Calculation_") or "(copy)_" in name):
            name_map[name] = caption
    return name_map


def _resolve_calc_refs(formula: str, name_map: dict[str, str]) -> str:
    """Replace [Calculation_*] references in a formula with human captions."""

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        return f"[{name_map[key]}]" if key in name_map else m.group(0)

    return _FIELD_REF_RE.sub(_sub, formula)


# ── Viz usage extraction ────────────────────────────────────────────────────


def _extract_viz_usage(
    root, datasource_name: str
) -> dict[str, list[dict[str, str | None]]]:
    """Build a map of field_caption -> [{worksheet, role, aggregation}, ...]."""
    usage: dict[str, list[dict[str, str | None]]] = {}

    for worksheet in root.findall(".//worksheet"):
        ws_name = worksheet.get("name", "")

        # Collect datasource-dependency references for this worksheet
        ds_deps = worksheet.findall(".//datasource-dependencies")
        relevant_deps = [
            dep for dep in ds_deps if dep.get("datasource") == datasource_name
        ]

        # Build local column name -> caption map from dependencies
        local_caption_map: dict[str, str] = {}
        for dep in relevant_deps:
            for col in dep.findall("column"):
                col_name = col.get("name", "").strip("[]")
                col_caption = col.get("caption", "")
                if col_caption:
                    local_caption_map[col_name] = col_caption

        # Scan rows (dimensions) in the worksheet
        for row in worksheet.findall(".//rows"):
            _parse_shelf_fields(
                row.text or "",
                datasource_name,
                ws_name,
                "dimension",
                None,
                local_caption_map,
                usage,
            )

        # Scan cols (dimensions) in the worksheet
        for col in worksheet.findall(".//cols"):
            _parse_shelf_fields(
                col.text or "",
                datasource_name,
                ws_name,
                "dimension",
                None,
                local_caption_map,
                usage,
            )

        # Scan mark properties and encodings for measures
        for encoding in worksheet.findall(
            ".//mark-class/..//encoding"
        ) + worksheet.findall(".//encodings//*"):
            _parse_encoding_field(
                encoding, datasource_name, ws_name, local_caption_map, usage
            )

        # Scan pane specifications for measure values
        for pane_spec in worksheet.findall(".//panes/pane"):
            for enc in pane_spec.findall("encodings/*"):
                _parse_encoding_field(
                    enc, datasource_name, ws_name, local_caption_map, usage
                )

    return usage


_AGG_PREFIXES = frozenset(
    {
        "SUM",
        "AVG",
        "MIN",
        "MAX",
        "COUNT",
        "COUNTD",
        "MEDIAN",
        "ATTR",
        "STDEV",
        "VAR",
    }
)


def _parse_shelf_fields(
    shelf_text: str,
    datasource_name: str,
    worksheet_name: str,
    default_role: str,
    default_aggregation: str | None,
    caption_map: dict[str, str],
    usage: dict[str, list[dict[str, str | None]]],
) -> None:
    """Parse a shelf text (rows/cols) for compound field references."""
    for match in _SHELF_REF_RE.finditer(shelf_text):
        ds_part = match.group(1)
        agg_prefix = match.group(2)  # may be None
        field_name = match.group(3)

        if ds_part != datasource_name:
            continue

        agg = default_aggregation
        role = default_role
        if agg_prefix:
            prefix_upper = agg_prefix.upper()
            if prefix_upper in _AGG_PREFIXES:
                agg = prefix_upper
                role = "measure"

        field_caption = caption_map.get(field_name, field_name)

        usage.setdefault(field_caption, []).append(
            {
                "worksheet": worksheet_name,
                "role": role,
                "aggregation": agg,
            }
        )


def _parse_encoding_field(
    element,
    datasource_name: str,
    worksheet_name: str,
    caption_map: dict[str, str],
    usage: dict[str, list[dict[str, str | None]]],
) -> None:
    """Parse an encoding element for field references with aggregation."""
    column = element.get("column")
    if not column:
        return

    match = _SHELF_REF_RE.search(column)
    if not match:
        return

    ds_part = match.group(1)
    agg_prefix = match.group(2)
    field_name = match.group(3)

    if ds_part != datasource_name:
        return

    agg = None
    role = "dimension"
    if agg_prefix:
        prefix_upper = agg_prefix.upper()
        if prefix_upper in _AGG_PREFIXES:
            agg = prefix_upper
            role = "measure"

    field_caption = caption_map.get(field_name, field_name)

    usage.setdefault(field_caption, []).append(
        {
            "worksheet": worksheet_name,
            "role": role,
            "aggregation": agg,
        }
    )


def _dedupe_viz_usage(
    usage_list: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Remove duplicate viz usage entries."""
    seen: set[tuple] = set()
    deduped = []
    for entry in usage_list:
        key = (entry["worksheet"], entry["role"], entry.get("aggregation"))
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    return deduped


# ── Datasource parsing ──────────────────────────────────────────────────────


def list_datasources(twb_bytes: bytes) -> list[dict[str, str | int]]:
    """Return unique datasources with field counts, deduplicated by caption."""
    root = ET.fromstring(twb_bytes)
    seen: set[str] = set()
    sources = []
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters" or caption in seen:
            continue
        seen.add(caption)
        field_count = sum(1 for col in ds.findall("column") if not _is_internal(col))
        sources.append(
            {
                "caption": caption,
                "name": ds.get("name", ""),
                "n_fields": field_count,
            }
        )
    return sources


def parse_datasource(twb_bytes: bytes, datasource_caption: str) -> dict | None:
    """Parse a single datasource into the spec JSON structure."""
    root = ET.fromstring(twb_bytes)

    target_ds = None
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == datasource_caption:
            target_ds = ds
            break

    if target_ds is None:
        return None

    ds_name = target_ds.get("name", "")
    name_map = _build_calc_name_map(target_ds)
    viz_usage = _extract_viz_usage(root, ds_name)

    fields = []
    lod_expressions = []

    for column in target_ds.findall("column"):
        if _is_internal(column):
            continue

        caption = column.get("caption", "")
        calc = column.find("calculation[@class='tableau']")
        formula = None
        is_calculated = False
        contains_lod = False

        if calc is not None:
            raw_formula = calc.get("formula", "")
            if raw_formula:
                formula = _resolve_calc_refs(raw_formula, name_map)
                is_calculated = True
                contains_lod = bool(_LOD_RE.search(formula))

                if contains_lod:
                    lod_expressions.append(
                        {
                            "name": caption,
                            "formula": formula,
                        }
                    )

        field_usage = _dedupe_viz_usage(viz_usage.get(caption, []))

        fields.append(
            {
                "name": caption,
                "datatype": column.get("datatype", "unknown"),
                "formula": formula,
                "is_calculated": is_calculated,
                "contains_lod": contains_lod,
                "viz_usage": field_usage,
            }
        )

    # Parse parameters from the Parameters datasource
    parameters = _parse_parameters(root)

    return {
        "caption": datasource_caption,
        "fields": fields,
        "parameters": parameters,
        "lod_expressions": lod_expressions,
    }


def _parse_parameters(root) -> list[dict[str, str]]:
    """Extract parameters from the Parameters pseudo-datasource."""
    parameters = []
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption != "Parameters":
            continue

        for column in ds.findall("column"):
            param_caption = column.get("caption", "")
            if not param_caption:
                continue

            param = {
                "name": param_caption,
                "datatype": column.get("datatype", "unknown"),
            }

            # Try to get current value from the calculation element
            calc = column.find("calculation[@class='tableau']")
            if calc is not None:
                current_value = calc.get("formula", "")
                if current_value:
                    param["current_value"] = current_value

            parameters.append(param)

    return parameters


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
    """Authenticate to Tableau Server, preferring PAT over password."""
    if not server.lower().startswith("https://"):
        raise SystemExit(
            f"Refusing to send credentials over non-HTTPS connection: {server!r}\n"
            "Ensure TABLEAU_SERVER_ADDRESS starts with https://."
        )

    token_name = os.environ.get("TABLEAU_TOKEN_NAME")
    pat = os.environ.get("TABLEAU_PERSONAL_ACCESS_TOKEN")

    if token_name and pat:
        return signin_pat(server, site, token_name, pat)

    if username:
        password = getpass.getpass(f"Password for {username}: ")
        return signin_password(server, site, username, password)

    raise SystemExit(
        "No auth credentials found. Set TABLEAU_TOKEN_NAME and "
        "TABLEAU_PERSONAL_ACCESS_TOKEN env vars, or pass --username."
    )


def signout(server: str, token: str) -> None:
    """Invalidate the Tableau Server session token (best-effort)."""
    url = f"{server}/api/{TABLEAU_API_VERSION}/auth/signout"
    try:
        requests.post(url, headers={"x-tableau-auth": token}, timeout=10)
    except requests.RequestException:
        pass


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
    safe_name = workbook_name.replace(":", "").replace(",", "")
    url = f"{server}/api/{TABLEAU_API_VERSION}/sites/{site_id}/workbooks"
    resp = requests.get(
        url,
        headers={**_JSON_HEADERS, "x-tableau-auth": token},
        params={"filter": f"name:eq:{safe_name}"},
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
    available = [e["name"] for e in data.get("exposures", [])]
    raise ValueError(
        f"Exposure {exposure_name!r} not found in {EXPOSURES_PATH}.\n"
        f"Available: {available}"
    )


def get_workbook_id_from_exposure(exposure: dict) -> str | None:
    """Extract the Tableau workbook LSID from an exposure's metadata."""
    return (
        exposure.get("config", {})
        .get("meta", {})
        .get("dagster", {})
        .get("asset", {})
        .get("metadata", {})
        .get("id")
    )


# ── Main entry point ───────────────────────────────────────────────────────


def _fetch_from_server(args) -> bytes:
    """Fetch workbook bytes from Tableau Server using exposure metadata."""
    exposure = load_exposure(args.exposure)
    workbook_id = get_workbook_id_from_exposure(exposure)

    if not workbook_id:
        raise SystemExit(
            f"Exposure {args.exposure!r} has no workbook ID in tableau.yml. "
            "Use --file with a local .twbx instead."
        )

    server = args.server
    if not server:
        raise SystemExit("--server is required (or set TABLEAU_SERVER_ADDRESS env var)")

    token, site_id = get_auth_token(server, args.site, args.username)
    try:
        raw = download_workbook_by_id(server, site_id, workbook_id, token)
    finally:
        signout(server, token)

    return extract_twb_bytes_from_bytes(raw)


def _build_output(
    twb_bytes: bytes,
    workbook_name: str,
    source_label: str,
    datasource_filter: str | None,
) -> dict:
    """Build the full JSON output structure."""
    sources = list_datasources(twb_bytes)

    if datasource_filter:
        matches = [
            s
            for s in sources
            if datasource_filter.lower() in str(s.get("caption", "")).lower()
        ]
        if not matches:
            available = [str(s.get("caption", "")) for s in sources]
            raise SystemExit(
                f"No datasource matching {datasource_filter!r}.\nAvailable: {available}"
            )
        sources = matches

    datasources = []
    for src in sources:
        caption = str(src.get("caption", ""))
        parsed = parse_datasource(twb_bytes, caption)
        if parsed:
            datasources.append(parsed)

    return {
        "workbook": workbook_name,
        "source": source_label,
        "datasources": datasources,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Parse Tableau workbook XML and emit structured JSON "
            "with field metadata and viz usage."
        ),
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--file",
        type=pathlib.Path,
        metavar="PATH",
        help="Path to a local .twb or .twbx file",
    )
    source.add_argument(
        "--exposure",
        metavar="NAME",
        help="Exposure name from tableau.yml (Tableau Server API mode)",
    )

    parser.add_argument(
        "--datasource",
        "-d",
        metavar="NAME",
        help="Filter to a specific datasource (case-insensitive substring match)",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List datasources and exit (no full parse)",
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
        help="Username for password auth (PAT preferred)",
    )

    args = parser.parse_args()

    # Obtain twb bytes
    if args.file:
        twb_bytes = extract_twb_bytes(args.file)
        workbook_name = args.file.stem
        source_label = str(args.file)
    else:
        twb_bytes = _fetch_from_server(args)
        workbook_name = args.exposure
        source_label = f"exposure:{args.exposure}"

    # List-only mode
    if args.list_sources:
        sources = list_datasources(twb_bytes)
        result = {
            "workbook": workbook_name,
            "source": source_label,
            "datasources": [
                {"caption": s["caption"], "n_fields": s["n_fields"]} for s in sources
            ],
        }
        json.dump(result, sys.stdout, indent=2)
        print()
        return

    # Full parse
    output = _build_output(twb_bytes, workbook_name, source_label, args.datasource)
    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
