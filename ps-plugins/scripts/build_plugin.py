#!/usr/bin/env python3
"""Build an installable PowerSchool plugin zip, and validate it before writing.

Usage:
    python3 scripts/build_plugin.py                  # build every plugin
    python3 scripts/build_plugin.py gradebook-audit  # build one

Writes dist/<plugin_name>_v<version>.zip.

The validation matters more than the packaging. Every page path referenced in
plugin.xml and permissions_root/*.xml must resolve to a real file inside the
package. A path pointing at a folder that doesn't exist fails silently in
PowerSchool -- the nav link 404s and permission mappings bind to nothing, with no
error at install or enable time. That bug reached this repo once, when the
WEB_ROOT/admin/gradebookaudit/ folder level was lost in migration. This script
turns it into a build failure instead.

Standard library only, so it runs anywhere with python3 and needs no install.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile

# The only XML this script parses is plugin.xml and its siblings, which are
# repo-controlled files, not untrusted input. defusedxml would also break the
# standard-library-only constraint this script is built under.
# trunk-ignore(bandit/B405): repo-controlled XML, not untrusted input
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"

# Resolved from the plugin directory so the script works from any cwd.
DBT_U_EXPECTATIONS = (
    REPO.parent
    / "src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__u_expectations.sql"
)
SKILL_DIR = REPO / "skills" / "gradebook-expectations-upload"

# Documentation and repo furniture never belong in a plugin package -- PS only
# needs plugin.xml and the *_root/WEB_ROOT trees.
EXCLUDE_DIRS = {"docs", ".git", "__pycache__"}
EXCLUDE_FILES = {"README.md", ".DS_Store"}

# Matches the page paths PS resolves against WEB_ROOT, e.g.
# "/admin/gradebookaudit/gradebook_expectations.html"
PAGE_PATH = re.compile(r"""["'](/(?:admin|teachers|guardian)/[^"']+\.html)["']""")


def find_plugins() -> list[Path]:
    return sorted(p.parent for p in REPO.glob("*/plugin.xml"))


def plugin_meta(plugin_xml: Path) -> tuple[str, str]:
    # trunk-ignore(bandit/B314): repo-controlled XML, not untrusted input
    root = ET.parse(plugin_xml).getroot()
    name = root.get("name") or plugin_xml.parent.name
    version = root.get("version") or "0.0"
    return name, version


def referenced_paths(src: Path) -> set[str]:
    """Every page path the plugin's XML expects PS to serve."""
    refs: set[str] = set()
    for xml in [src / "plugin.xml", *sorted((src / "permissions_root").glob("*.xml"))]:
        if xml.exists():
            refs |= set(PAGE_PATH.findall(xml.read_text()))
    return refs


def stage(src: Path, dest: Path) -> None:
    for item in sorted(src.iterdir()):
        if item.name in EXCLUDE_DIRS or item.name in EXCLUDE_FILES:
            continue
        if item.is_dir():
            shutil.copytree(
                item,
                dest / item.name,
                ignore=shutil.ignore_patterns(*EXCLUDE_DIRS, *EXCLUDE_FILES),
            )
        else:
            shutil.copy2(item, dest / item.name)


def validate(staged: Path, refs: set[str]) -> list[str]:
    errors = []

    if not (staged / "plugin.xml").exists():
        errors.append("plugin.xml missing from package root (PS requires it there)")

    for ref in sorted(refs):
        # PS serves WEB_ROOT as the document root, so /admin/x.html lives at
        # WEB_ROOT/admin/x.html inside the package.
        target = staged / "WEB_ROOT" / ref.lstrip("/")
        if not target.is_file():
            errors.append(
                f"{ref} is referenced in XML but WEB_ROOT{ref} is not in the package"
            )

    # An orphaned page is not fatal -- pages reached only by a relative link from
    # another page legitimately have no XML reference -- but a whole missing
    # directory usually shows up here first, so it's worth surfacing.
    web_root = staged / "WEB_ROOT"
    if web_root.exists():
        packaged = {
            "/" + str(p.relative_to(web_root)) for p in web_root.rglob("*.html")
        }
        for orphan in sorted(packaged - refs):
            print(f"  note: {orphan} is packaged but not referenced in any XML")

    return errors


# PowerSchool stamps these onto every U_ table. The named query does not list
# them because the list page does not show them, so they are expected to appear
# on the dbt side and nowhere else. Without this exemption the contract check
# fails on its first run against a correct pair.
PS_AUDIT_COLUMNS = {"whocreated", "whencreated", "whomodified", "whenmodified"}

COLUMN_TAG = re.compile(r'<column\s+column="[^."]+\.([^"]+)"')


def named_query_columns(plugin_dir: Path) -> set[str]:
    """Every column the plugin's named queries declare on u_expectations."""
    columns: set[str] = set()
    for xml in sorted((plugin_dir / "queries_root").glob("*.xml")):
        columns |= set(COLUMN_TAG.findall(xml.read_text()))
    return columns


def dbt_model_columns(sql_path: Path) -> set[str]:
    """Column names the dbt staging model projects.

    The model enumerates its columns, so the names are readable without a dbt
    parse. Backticks around reserved words (`quarter`) are stripped. A
    full-line `--` comment or a blank line is skipped before it's tested
    against the FROM clause, so a comment that happens to contain the word
    "from" (e.g. "-- computed from the raw PS export") can't be mistaken for
    it; an inline trailing `-- ...` comment on a column line is dropped before
    the column name is extracted.

    Assumes the model is a single `select ... from ...` with no leading CTE. A
    `with x as (select ... from ...)` before the final select would stop the
    walk at the CTE's own FROM and derive the wrong column set. That fails the
    contract check loudly rather than passing a wrong one, so it is a known
    limit, not a silent hole -- but widen this parser rather than work around
    it if the staging model ever gains a CTE.
    """
    columns: set[str] = set()
    for line in sql_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(("select", "--")):
            continue
        if line.lower().startswith("from "):
            break
        if "--" in line:
            line = line.split("--", 1)[0].strip()
        line = line.rstrip(",")
        name = line.split(" as ")[-1] if " as " in line else line
        columns.add(name.strip().strip("`"))
    return columns


def check_column_contract(plugin_dir: Path, sql_path: Path) -> list[str]:
    """The plugin's declared columns must all exist in the dbt model."""
    declared = named_query_columns(plugin_dir)
    modelled = dbt_model_columns(sql_path)

    errors = [
        f"{c} is declared in a named query but the dbt model does not project it"
        for c in sorted(declared - modelled)
    ]
    errors += [
        f"{c} is in the dbt model but no named query declares it"
        for c in sorted(modelled - declared - PS_AUDIT_COLUMNS)
    ]
    return errors


# The import page validates an uploaded file against this literal. It is the
# authoritative header: a file that does not match is rejected outright with
# "Header row does not match template", and nothing imports.
CSV_EXPECTED = re.compile(r"var\s+expected\s*=\s*\[([^\]]+)\]")


def plugin_csv_header(plugin_dir: Path) -> list[str]:
    """The lower-cased column names the plugin's import validator accepts."""
    page = plugin_dir / "WEB_ROOT/admin/gradebookaudit/gradebook_expectations.html"
    match = CSV_EXPECTED.search(page.read_text())
    if match is None:
        raise ValueError(
            f"no `var expected = [...]` CSV validator found in {page.name}; "
            "the import page changed shape and this check needs updating"
        )
    return [v.strip().strip("'\"") for v in match.group(1).split(",")]


def check_csv_header_contract(plugin_dir: Path, skill_dir: Path) -> list[str]:
    """Every place that states the header must state the one the plugin accepts.

    Both reference files are checked, not just one: a reader who opens
    `sheets.md` and copies the header from there never sees `csv-format.md`,
    so a stale copy in either file sends someone to build a file the import
    page rejects.
    """
    header = ",".join(plugin_csv_header(plugin_dir))
    problems = []

    for name in ("csv-format.md", "sheets.md"):
        documented = skill_dir / "references" / name
        if not documented.is_file():
            problems.append(f"{documented} is missing; it must state the header")
            continue

        lines = (
            line.strip().lower().replace(", ", ",")
            for line in documented.read_text().splitlines()
        )
        if not any(line == header for line in lines):
            problems.append(
                f"references/{name} does not contain the header the plugin "
                f"accepts: {header}"
            )
    return problems


def build(plugin_dir: Path) -> Path | None:
    name, version = plugin_meta(plugin_dir / "plugin.xml")
    slug = plugin_dir.name.replace("-", "_")
    print(f"\n=== {name} v{version} ({plugin_dir.name}) ===")

    refs = referenced_paths(plugin_dir)
    print(f"  {len(refs)} page path(s) referenced in XML")

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "pkg"
        staged.mkdir()
        stage(plugin_dir, staged)

        errors = validate(staged, refs)
        errors += check_column_contract(plugin_dir, DBT_U_EXPECTATIONS)
        errors += check_csv_header_contract(plugin_dir, SKILL_DIR)
        if errors:
            print("\n  BUILD FAILED:")
            for e in errors:
                print(f"    - {e}")
            return None

        DIST.mkdir(exist_ok=True)
        out = DIST / f"{slug}_v{version}.zip"
        if out.exists():
            out.unlink()

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(staged.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(staged))

        with zipfile.ZipFile(out) as z:
            count = len(z.namelist())
        print("  validated: all XML paths resolve")
        print(
            f"  wrote {out.relative_to(REPO)} ({count} files, {out.stat().st_size:,} bytes)"
        )
        return out


def main() -> int:
    wanted = sys.argv[1:]
    plugins = find_plugins()
    if wanted:
        plugins = [p for p in plugins if p.name in wanted]
        missing = set(wanted) - {p.name for p in plugins}
        for m in sorted(missing):
            print(f"error: no plugin.xml found in {m}/", file=sys.stderr)
        if missing:
            return 2

    if not plugins:
        print("error: no plugins found", file=sys.stderr)
        return 2

    failed = [p.name for p in plugins if build(p) is None]
    if failed:
        print(f"\n{len(failed)} plugin(s) failed to build: {', '.join(failed)}")
        return 1

    print(f"\nBuilt {len(plugins)} plugin(s) into dist/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
