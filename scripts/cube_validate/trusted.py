"""Trust that carries from the last trusted run while nothing it rested on moved."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .config import MAPPING_EXCLUDED

FILE = "trusted.json"


def code_fingerprint(pkg: Path) -> str:
    """sha256 over each `*.py` in the package, by file name then bytes."""
    h = hashlib.sha256()
    for f in sorted(Path(pkg).glob("*.py"), key=lambda f: f.name):
        h.update(f.name.encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def mapping_fingerprint(checks_path: Path) -> str:
    """sha256 of the checks file without the sections that record findings."""
    data = yaml.safe_load(Path(checks_path).read_text()) or {}
    kept = {k: v for k, v in data.items() if k not in MAPPING_EXCLUDED}
    text = json.dumps(kept, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def kinds(cells, rows_result) -> set[str]:
    """Each verdict, and each non-match row bucket as "base / cause"."""
    out = {c.verdict for c in cells}
    out |= {
        f"{b['base']} / {b['cause']}"
        for b in rows_result.buckets
        if b["base"] != "match"
    }
    return out


def record(
    root: Path,
    snapshot: str,
    code: str,
    mapping: str,
    kinds: set[str],
    dashboard: str | None = None,
    inherited: set[str] | None = None,
) -> None:
    """Write the trusted record into the dashboard's snapshot folder.

    Args:
        root: The dashboard's snapshot folder.
        snapshot: The trusted snapshot's folder name.
        code: Its code fingerprint.
        mapping: Its mapping fingerprint.
        kinds: Every verdict and bucket it produced.
        dashboard: Its dashboard; defaults to the folder name.
        inherited: The kinds an earlier trusted run had checked, which this
            run's hand checks skipped; empty when it drew a full set. A
            re-analysis of this snapshot picks with it, so its checks stay put.
    """
    root = Path(root)
    (root / FILE).write_text(
        json.dumps(
            {
                "snapshot": snapshot,
                "code": code,
                "mapping": mapping,
                "kinds": sorted(kinds),
                "dashboard": dashboard or root.name,
                "inherited": sorted(inherited or ()),
            },
            indent=2,
        )
    )


def read(root: Path) -> dict | None:
    """The trusted record, or None when no run was trusted yet."""
    p = Path(root) / FILE
    return json.loads(p.read_text()) if p.exists() else None


def fingerprints_match(record: dict | None, code: str, mapping: str) -> bool:
    """Whether the record was made by this code and this mapping."""
    return (
        record is not None and record["code"] == code and record["mapping"] == mapping
    )


def carries(
    record: dict | None,
    code: str,
    mapping: str,
    kinds: set[str],
    dashboard: str | None = None,
) -> bool:
    """Whether the record's trust covers this run.

    Args:
        record: The last trusted run's record, if any.
        code: This run's code fingerprint.
        mapping: This run's mapping fingerprint.
        kinds: Every verdict and bucket this run produced.
        dashboard: This run's dashboard; a record for another one never carries.
    """
    if record is None or not fingerprints_match(record, code, mapping):
        return False
    if dashboard is not None and record.get("dashboard") != dashboard:
        return False
    return kinds <= set(record["kinds"])
