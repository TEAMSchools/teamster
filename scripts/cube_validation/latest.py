"""Each comparison's latest result, kept apart from any one run folder.

A validation is the latest result of each confirmed comparison, each at its
own moment. `compare` copies a comparison's slice here as it finishes and composes
`run.json` from every comparison's copy. Results are kept per fact dataset
(`folder`), so a dev build's run (`--fact-dataset`) never replaces or joins
production's. A copy, not a pointer to a run
folder: `checkpoints.clear` on a restart at the same moment would delete a
slice a pointer still names. Only counts, SQL and fingerprints are written;
student rows stay in BigQuery.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import checkpoints
from .config import Comparison, fingerprint_data
from .moment import Build

DIR = "latest"


@dataclass(frozen=True)
class Latest:
    """One comparison's latest result.

    `fingerprint` is its `pipeline.checkpoint_fingerprint` when it ran, and
    `entry` its `entry_fingerprint`. `data` is its `Sides.to_json()` slice,
    with the dimension tables Cube read that changed during its build under
    `changed_dims`. `fact` is the `dataset.table` it read.
    """

    moment: Build
    fingerprint: str
    entry: str
    ran_at: str
    data: dict
    fact: str = ""


def folder(view_dir: Path, fact: str) -> Path:
    """Where the view's results of `fact`'s dataset are kept."""
    return view_dir / DIR / fact.split(".", 1)[0]


def entry_fingerprint(comparison: Comparison) -> str:
    """The comparison's config entry, its rebuild check (`rebuild_check`)
    included, as `config.fingerprint_data` reads it."""
    return hashlib.sha256(
        json.dumps(
            fingerprint_data(comparison),
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()


def _file(results: Path, comparison_id: str) -> Path:
    # A comparison id need not be a safe file name; the digest keeps 2 ids that
    # slug alike apart.
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", comparison_id)
    digest = hashlib.sha256(comparison_id.encode()).hexdigest()[:8]
    return results / f"{slug}_{digest}.json"


def write(results: Path, comparison_id: str, result: Latest) -> None:
    """Replace the comparison's latest result in `results` (`folder`), whole."""
    checkpoints.write_json(
        _file(results, comparison_id),
        {
            "comparison": comparison_id,
            "fact": result.fact,
            "moment": result.moment.to_json(),
            "fingerprint": result.fingerprint,
            "entry": result.entry,
            "ran_at": result.ran_at,
            "data": result.data,
        },
    )


def add_formula_check(results: Path, comparison_id: str, check: dict) -> None:
    """Keep a formula check (`formula.Check.to_json`) beside the comparison's
    latest result in `results` (`folder`), replacing any earlier one.

    The check names the result it checked by fingerprint, so a newer result
    written over this file drops it, and one kept elsewhere never counts. With
    no result to keep it beside, it is dropped: the next `compare` writes a
    result no older check fits.

    Raises:
        ValueError: The check is of another comparison.
    """
    if (other := check.get("comparison")) != comparison_id:
        raise ValueError(f"the formula check checks {other}, not {comparison_id}")
    path = _file(results, comparison_id)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return
    data["data"]["formula_check"] = check
    checkpoints.write_json(path, data)


def read_all(results: Path, fact: str) -> dict[str, Latest]:
    """Every comparison's latest result of `fact` in `results` (`folder`), by id.

    A file that cannot be read is skipped and named; its comparison then
    reads as never compared. So does a result of another fact in the same
    dataset.
    """
    out: dict[str, Latest] = {}
    for path in sorted(results.glob("*.json")):
        try:
            e = json.loads(path.read_text())
            out[e["comparison"]] = Latest(
                moment=Build.from_json(e["moment"]),
                fingerprint=e["fingerprint"],
                entry=e["entry"],
                ran_at=e["ran_at"],
                data=e["data"],
                fact=e.get("fact", ""),
            )
        except (OSError, ValueError, KeyError, TypeError):
            print(f"Latest result {path.name} skipped: it cannot be read.")
    return {cid: r for cid, r in out.items() if r.fact == fact}
