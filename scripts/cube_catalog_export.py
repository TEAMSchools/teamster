# /// script
# requires-python = ">=3.11"
# dependencies = ["pyjwt>=2.8", "httpx>=0.27"]
# ///
"""Export the Cube semantic-layer catalog for external consumers.

Writes two artifacts, both committed so a model change shows up as a reviewable
diff:

  docs/reference/cube-catalog-meta.json   machine-readable snapshot (parse this)
  docs/reference/cube-semantic-catalog.md the ``## Views`` reference section

The markdown file's hand-written front matter (how-to-query, gotchas, sample
queries) is preserved: this script replaces only the content from the ``## Views``
heading to end of file.

Usage, from the repo root:

    export CUBE_API_SECRET="$(op read 'op://Data Team/Cube Cloud REST API/credential')"
    export CUBE_REST_URL='https://<deployment>.<region>.cubecloudapp.dev/cubejs-api/v1'
    uv run scripts/cube_catalog_export.py

Run it as an identity with network-wide scope. Cube hides every view a caller's
groups do not match, so a narrowly-scoped or unresolved caller gets
``{"cubes": []}`` -- indistinguishable from an undeployed model. This script exits
non-zero on an empty catalog rather than committing one.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

# checkAuth verifies HS256 against CUBEJS_API_SECRET, enforces a 12h maxAge
# derived from iat, and takes the RAW token as the Authorization value -- no
# "Bearer " prefix. All three matter; see docs/guides/cube.md.
TOKEN_TTL_SECONDS = 300

VIEWS_HEADING = "## Views"

# Emit staff_pii last and warn on it: it is listed so an integrator can see the
# view exists and is deliberately outside their scope.
GATED_VIEWS = {"staff_pii"}

GATED_WARNING = """!!! warning "Gated — not available to external integrations"

    This view holds sensitive personal fields and is access-gated per viewer. It
    is listed here so you can see it exists and is not part of your scope. Do not
    design against it.
"""

# Abbreviations that end in a period without ending a sentence. Without this the
# naive "split on the first period" rule truncates a description mid-clause.
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "approx.", "Dr.", "No.")


def mint_token(secret: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "email": os.environ.get("CUBE_EXPORT_EMAIL", ""),
            "iat": now,
            "exp": now + TOKEN_TTL_SECONDS,
        },
        secret,
        algorithm="HS256",
    )


def fetch_meta(rest_url: str, token: str, timeout: float) -> dict[str, Any]:
    url = rest_url.rstrip("/") + "/meta"
    response = httpx.get(url, headers={"Authorization": token}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def first_sentence(text: str | None) -> str:
    """First sentence of a description, for a table cell.

    Descriptions in the model run to several paragraphs; a table needs one line.
    Full text stays in the JSON snapshot, which is what a consumer should parse.
    """
    if not text:
        return ""
    # Only the first line: a description's later paragraphs are usage guidance.
    line = text.strip().split("\n", 1)[0].strip()
    # Walk candidate sentence ends, skipping any that is a known abbreviation.
    for match in re.finditer(r"\.(?:\s|$)", line):
        candidate = line[: match.start() + 1]
        if not any(candidate.endswith(abbr) for abbr in _ABBREVIATIONS):
            return candidate
    return line


def cell(text: str | None) -> str:
    """Escape a value for a markdown table cell."""
    value = first_sentence(text)
    return value.replace("|", r"\|").replace("\n", " ")


def bare(member_name: str, view_name: str) -> str:
    prefix = view_name + "."
    return member_name[len(prefix) :] if member_name.startswith(prefix) else member_name


def render_member_table(members: list[dict[str, Any]], view_name: str) -> list[str]:
    if not members:
        return ["None.", ""]
    lines = ["| Member | Type | Description |", "| ------ | ---- | ----------- |"]
    for member in sorted(members, key=lambda m: bare(m["name"], view_name)):
        name = bare(member["name"], view_name)
        lines.append(
            f"| `{name}` | {member.get('type', '')} | {cell(member.get('description'))} |"
        )
    lines.append("")
    return lines


def render_views(views: list[dict[str, Any]]) -> str:
    # Student views first, then open staff, then gated -- most useful to least.
    def sort_key(view: dict[str, Any]) -> tuple[int, str]:
        name = view["name"]
        tier = 2 if name in GATED_VIEWS else (0 if name.startswith("student") else 1)
        return (tier, name)

    lines: list[str] = [VIEWS_HEADING, ""]
    for view in sorted(views, key=sort_key):
        name = view["name"]
        lines.append(f"### {name}")
        lines.append("")
        if name in GATED_VIEWS:
            lines.append(GATED_WARNING)
        summary = first_sentence(view.get("description"))
        if summary:
            lines.extend([summary, ""])
        lines.append(
            f"Query members as `{name}.<member>`; the table lists bare member names."
        )
        lines.append("")
        lines.append("#### Measures")
        lines.append("")
        lines.extend(render_member_table(view.get("measures", []), name))
        lines.append("#### Dimensions")
        lines.append("")
        lines.extend(render_member_table(view.get("dimensions", []), name))
        lines.append(
            "Full descriptions for every member are in `cube-catalog-meta.json`."
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def splice_views_section(markdown_path: Path, rendered: str) -> None:
    """Replace everything from the ``## Views`` heading onward, preserving the
    hand-written front matter above it."""
    original = markdown_path.read_text(encoding="utf-8")
    index = original.find(VIEWS_HEADING)
    if index == -1:
        raise SystemExit(
            f"{markdown_path} has no '{VIEWS_HEADING}' heading — refusing to guess "
            "where the generated section starts."
        )
    markdown_path.write_text(original[:index] + rendered, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    secret = os.environ.get("CUBE_API_SECRET", "").strip()
    rest_url = os.environ.get("CUBE_REST_URL", "").strip()
    if not secret or not rest_url:
        print(
            "Set CUBE_API_SECRET and CUBE_REST_URL. See this script's docstring.",
            file=sys.stderr,
        )
        return 2

    meta = fetch_meta(rest_url, mint_token(secret), args.timeout)
    views = [cube for cube in meta.get("cubes", []) if cube.get("type") == "view"]

    # Fail loudly rather than committing an empty catalog: an access problem and an
    # undeployed model look identical from here, and only one of them is worth
    # writing to disk.
    if not views:
        print(
            "No views returned. Cube hides every view whose access policy the "
            "caller's groups do not match, so this is far more likely to be an "
            "access problem than an empty model. Nothing written.",
            file=sys.stderr,
        )
        return 1

    json_path = args.repo_root / "docs" / "reference" / "cube-catalog-meta.json"
    markdown_path = args.repo_root / "docs" / "reference" / "cube-semantic-catalog.md"

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(
            {"generated_from": "Cube Cloud production deployment", "views": views},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    splice_views_section(markdown_path, render_views(views))

    measures = sum(len(v.get("measures", [])) for v in views)
    dimensions = sum(len(v.get("dimensions", [])) for v in views)
    print(
        f"{len(views)} views, {measures} measures, {dimensions} dimensions\n"
        f"  {json_path}\n  {markdown_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
