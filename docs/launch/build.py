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


def _tier_one(catalog: Catalog) -> list[str]:
    errors: list[str] = []
    entries = catalog.entries
    config = catalog.config

    if not isinstance(entries, list):
        return ["links.yml must be a list of entries"]

    group_ids = {g["id"] for g in config.get("groups") or []}

    seen: set[str] = set()
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"links.yml entry {i} is not a mapping")
            continue

        where = entry.get("name") or entry.get("id") or f"entry {i}"

        entry_id = entry.get("id")
        if not entry_id:
            errors.append(f"{where}: missing `id`")
        elif not ID_RE.match(str(entry_id)):
            errors.append(f"{where}: `id` {entry_id!r} must match ^[a-z0-9_]+$")
        elif entry_id in seen:
            errors.append(f"{where}: duplicate `id` {entry_id!r}")
        else:
            seen.add(entry_id)

        if not (entry.get("name") or "").strip():
            errors.append(f"{where}: missing `name`")

        url = entry.get("url")
        if not url:
            errors.append(f"{where}: missing `url`")
        elif not str(url).startswith("https://"):
            errors.append(f"{where}: `url` must be https")

        system = entry.get("system")
        if system not in SYSTEMS:
            errors.append(f"{where}: unknown `system` {system!r}")

        status = entry.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: `status` must be one of {sorted(STATUSES)}")

        access = entry.get("access")
        if access is not None and access != "limited":
            errors.append(f"{where}: `access` may only be 'limited', got {access!r}")

        for region in entry.get("regions") or []:
            if region not in REGION_VALUES:
                errors.append(f"{where}: unknown region {region!r}")

        group = entry.get("group")
        if not group:
            errors.append(f"{where}: missing `group`")
        elif group not in group_ids:
            errors.append(f"{where}: unknown `group` {group!r}")

    for key in ("groups", "families", "promos"):
        if key not in config:
            errors.append(f"groups.yml is missing the `{key}` key")

    names = {e.get("name") for e in entries if isinstance(e, dict)}

    for family in config.get("families") or []:
        if family.get("group") not in group_ids:
            errors.append(
                f"family {family.get('id')!r} names unknown group "
                f"{family.get('group')!r}"
            )
        for member in family.get("members") or []:
            if member not in names:
                errors.append(
                    f"family {family.get('id')!r} names missing tool {member!r}"
                )

    for promo in config.get("promos") or []:
        url = (promo.get("url") or "").strip()
        if not url or url == "#":
            errors.append(f"promo {promo.get('label')!r} has no destination")

    return errors


def select(catalog: Catalog) -> list[dict]:
    """Entries that publish. Partitions only — never short-circuits."""
    return [
        e
        for e in catalog.entries
        if isinstance(e, dict) and e.get("status") == "verified"
    ]


def _tier_two(catalog: Catalog, verified: list[dict]) -> list[str]:
    errors: list[str] = []
    family_members = {
        member
        for family in catalog.config.get("families") or []
        for member in family.get("members") or []
    }

    for entry in verified:
        where = entry.get("name") or entry.get("id") or "<unnamed>"

        if not (entry.get("description") or "").strip():
            errors.append(f"{where}: verified entries need a `description`")

        audiences = entry.get("audiences") or []
        if not audiences:
            errors.append(f"{where}: needs a non-empty `audiences` list")
        for audience in audiences:
            if audience not in AUDIENCES:
                errors.append(f"{where}: unknown audience {audience!r}")

        guide = entry.get("guide")
        if guide and not str(guide).startswith("https://"):
            errors.append(f"{where}: `guide` must be https")

        if entry.get("name") in family_members:
            regions = entry.get("regions") or []
            if len(regions) != 1 or regions[0] not in REGIONS:
                errors.append(
                    f"{where}: a family member needs exactly one region "
                    f"from {sorted(REGIONS)}, got {regions!r}"
                )

    return errors


def validate(catalog: Catalog, verified: list[dict]) -> list[str]:
    """Tier 1 over everything; tier 2 over the verified subset."""
    return _tier_one(catalog) + _tier_two(catalog, verified)
