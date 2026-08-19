"""Render the staff launch page from the catalog in this directory.

Four functions, in order: load, select, validate, render. Nothing here
writes to the filesystem — render() returns a string and the MkDocs hook
decides where it goes. That is what keeps the tests free of temp files
and what stops `mkdocs serve` rebuilding itself in a loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent

ID_RE = re.compile(r"^[a-z0-9_]+$")

# The nine values documented in README.md, mapped to display labels.
SYSTEMS = {
    "tableau": "Tableau",
    "appsheet": "AppSheet",
    "zendesk": "Zendesk",
    "google-sheet": "Google Sheet",
    "google-slides": "Google Slides",
    "google-form": "Google Form",
    "google-doc": "Google Doc",
    "apps-script": "Apps Script",
    "other": "Other",
}

STATUSES = {"needs-review", "verified"}
AUDIENCES = {"teachers", "leaders", "ops", "region"}

# Region accents come from the KIPP NJ | Miami design system. `all` is a
# legal value on a normal entry but never on a family member.
REGIONS = {
    "newark": ("Newark", "var(--kipp-blue)"),
    "camden": ("Camden", "var(--kipp-green)"),
    "miami": ("Miami", "var(--kipp-orange)"),
    "paterson": ("Paterson", "var(--kipp-red)"),
}
REGION_VALUES = set(REGIONS) | {"all"}


class CatalogError(Exception):
    """Every validation problem found, not just the first one."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(
            f"{len(errors)} problem(s) in the launch catalog:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )


@dataclass(frozen=True)
class Catalog:
    entries: list[dict]
    config: dict
    template: str


def load(root: Path = HERE) -> Catalog:
    """Read links.yml, groups.yml and template.html from `root`."""
    entries = yaml.safe_load((root / "links.yml").read_text()) or []
    config = yaml.safe_load((root / "groups.yml").read_text()) or {}
    template = (root / "template.html").read_text()
    return Catalog(entries=entries, config=config, template=template)
