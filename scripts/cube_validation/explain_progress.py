"""A sort's finished explanations, so a stopped sort skips them when run again.

`triage-progress.json` sits in the run folder beside `run.json`. Each finished
explanation's outcome is kept under a key of what it ran on: the explanation, the
comparison and bucket, both sides' SQL, and the open items it covered. Only
counts are kept.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from .checkpoints import TRIAGE_PROGRESS, write_json

FILE = TRIAGE_PROGRESS


def key(
    explanation_fingerprint: str,
    comparison_id: str,
    bucket: str,
    sql_fingerprints: dict[str, str],
    open_keys: Iterable[str],
) -> str:
    """What an explanation's outcome holds for. Any change runs the explanation
    again: an edited explanation, other SQL, or another set of open items
    (`reapply` changes which groups are open)."""
    return hashlib.sha256(
        json.dumps(
            [
                explanation_fingerprint,
                comparison_id,
                bucket,
                sql_fingerprints,
                sorted(open_keys),
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()


def load(folder: Path) -> dict[str, dict]:
    """Every kept outcome by key; none when the file is missing or unreadable."""
    try:
        return json.loads((folder / FILE).read_text())
    except (OSError, ValueError):
        return {}


def save(folder: Path, key: str, outcome: dict) -> None:
    """Keep one explanation's outcome, replacing the file whole so a stop mid-write
    keeps the last whole file."""
    write_json(folder / FILE, {**load(folder), key: outcome})
