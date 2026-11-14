"""A run's progress in its run folder, so a stopped `run` can resume.

`run-state.json` says which moment the folder's run reads, whether it finished,
and what each process spent. `checkpoints/` holds one file per comparison it
finished: that comparison's slice of the run and the fingerprint it holds for.
Only counts, SQL and fingerprints are written; student rows stay in BigQuery.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .moment import Build

STATE = "run-state.json"
DIR = "checkpoints"
# A triage's finished proofs (`progress.FILE`); cleared with the run it read.
TRIAGE_PROGRESS = "triage-progress.json"


@dataclass(frozen=True)
class Unfinished:
    """A run folder with checkpoints and no finished run."""

    folder: Path
    moment: Build
    last_at: datetime
    done: int
    # The fact table the run read (`ViewConfig.fact`), so a run of another
    # (a `--fact-dataset` dev build) never resumes it.
    fact: str = ""


def _write_json(path: Path, data: dict) -> None:
    """Replace `path` whole, so a stop mid-write keeps the last whole file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _read_state(folder: Path) -> dict | None:
    try:
        return json.loads((folder / STATE).read_text())
    except (OSError, ValueError):
        return None


def _moment_json(moment: Build) -> dict:
    return {
        "start": moment.start.isoformat(),
        "end": moment.end.isoformat(),
        "job_id": moment.job_id,
    }


def start(folder: Path, moment: Build, process: str, fact: str = "") -> None:
    """Mark the folder's run of `fact` unfinished at `moment`, keeping what
    earlier processes spent, and add `process` at $0."""
    spent = (_read_state(folder) or {}).get("spent", {})
    _write_json(
        folder / STATE,
        {
            "moment": _moment_json(moment),
            "fact": fact,
            "finished": False,
            "spent": {**spent, process: spent.get(process, 0.0)},
        },
    )


def finish(folder: Path) -> None:
    """Mark the folder's run finished: a later `run` does not resume it."""
    state = _read_state(folder) or {}
    _write_json(folder / STATE, {**state, "finished": True})


def record_spend(folder: Path, process: str, usd: float) -> None:
    """Record what `process` has spent so far on this run."""
    state = _read_state(folder) or {}
    _write_json(
        folder / STATE, {**state, "spent": {**state.get("spent", {}), process: usd}}
    )


def total_spend(folder: Path) -> float:
    """What every process spent on this run."""
    return sum(((_read_state(folder) or {}).get("spent") or {}).values())


def _file(folder: Path, comparison_id: str) -> Path:
    slug = re.sub(r"[^A-Za-z0-9_-]", "_", comparison_id)
    digest = hashlib.sha256(comparison_id.encode()).hexdigest()[:8]
    return folder / DIR / f"{slug}_{digest}.json"


def write(
    folder: Path, comparison_id: str, fingerprint: str, data: dict, at: datetime
) -> None:
    """Save a finished comparison's slice, replacing any earlier one."""
    _write_json(
        _file(folder, comparison_id),
        {
            "comparison": comparison_id,
            "fingerprint": fingerprint,
            "at": at.isoformat(),
            "slice": data,
        },
    )


def _entries(folder: Path) -> list[dict]:
    out = []
    for path in sorted((folder / DIR).glob("*.json")):
        try:
            out.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            print(f"Checkpoint {path.name} skipped: it cannot be read.")
    return out


def read_all(folder: Path) -> dict[str, tuple[str, dict]]:
    """Each saved comparison's fingerprint and slice."""
    return {e["comparison"]: (e["fingerprint"], e["slice"]) for e in _entries(folder)}


def unfinished(folder: Path) -> Unfinished | None:
    """The folder's run, when it is unfinished and holds a checkpoint."""
    state = _read_state(folder)
    if not state or state.get("finished"):
        return None
    entries = _entries(folder)
    if not entries:
        return None
    m = state["moment"]
    return Unfinished(
        folder=folder,
        moment=Build(
            datetime.fromisoformat(m["start"]),
            datetime.fromisoformat(m["end"]),
            m["job_id"],
        ),
        last_at=max(datetime.fromisoformat(e["at"]) for e in entries),
        done=len(entries),
        fact=state.get("fact", ""),
    )


def find_unfinished(
    root: Path, view: str, fact: str | None = None
) -> Unfinished | None:
    """The view's unfinished run with the latest checkpoint, or None; with
    `fact`, only a run of that fact table."""
    found = [
        u
        for folder in ((root / view).iterdir() if (root / view).is_dir() else [])
        if (u := unfinished(folder)) is not None and fact in (None, u.fact)
    ]
    return max(found, key=lambda u: u.last_at, default=None)


def clear(folder: Path, keep_spend_of: str | None = None) -> None:
    """Remove the folder's checkpoints, run state and triage progress; keep
    its finished results (`run.json`, `result.md`, `triage.json`).

    With `keep_spend_of` (a fact table), what an unfinished run of that fact
    spent stays, so the run that starts here reports the true total even when
    the earlier one stopped before its first checkpoint.
    """
    state = _read_state(folder) or {}
    keep = (
        keep_spend_of is not None
        and not state.get("finished", True)
        and state.get("fact", "") == keep_spend_of
    )
    shutil.rmtree(folder / DIR, ignore_errors=True)
    for name in (STATE, TRIAGE_PROGRESS):
        (folder / name).unlink(missing_ok=True)
    if keep and state.get("spent"):
        _write_json(folder / STATE, {"finished": False, "spent": state["spent"]})
