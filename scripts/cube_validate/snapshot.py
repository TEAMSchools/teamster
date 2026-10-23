"""Snapshot folders: everything one capture froze, and what analysis wrote."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

SNAPSHOT_ROOT = Path.home() / ".cache" / "cube-validate"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


@dataclass(frozen=True)
class Snapshot:
    dir: Path

    @property
    def twbx(self) -> Path:
        return self.dir / "live.twbx"

    @property
    def extract(self) -> Path:
        return self.dir / "extract.hyper"

    @property
    def cube(self) -> Path:
        return self.dir / "cube.hyper"

    @property
    def cube_parts(self) -> Path:
        p = self.dir / "cube_parts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def answers(self) -> Path:
        return self.dir / "answers.json"

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def analysis(self) -> Path:
        p = self.dir / "analysis"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def export_path(self, cut_id: str, sheet: str) -> Path:
        p = self.dir / "exports" / slug(cut_id) / f"{slug(sheet)}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def new_snapshot(
    dashboard: str, now: dt.datetime, tag: str = "", root: Path = SNAPSHOT_ROOT
) -> Snapshot:
    name = now.strftime("%Y-%m-%dT%H%M") + (f"-{tag}" if tag else "")
    d = Path(root) / dashboard / name
    d.mkdir(parents=True, exist_ok=False)
    return Snapshot(d)


def latest_snapshot(dashboard: str, root: Path = SNAPSHOT_ROOT) -> Snapshot:
    base = Path(root) / dashboard
    dirs = (
        sorted(p for p in base.iterdir() if p.is_dir() and p.name != "plan")
        if base.exists()
        else []
    )
    if not dirs:
        raise FileNotFoundError(f"no snapshot for {dashboard} under {base}")
    return Snapshot(dirs[-1])


def read_manifest(snap: Snapshot) -> dict:
    return (
        json.loads(snap.manifest_path.read_text())
        if snap.manifest_path.exists()
        else {}
    )


def write_manifest(snap: Snapshot, m: dict) -> None:
    snap.manifest_path.write_text(json.dumps(m, indent=2, sort_keys=True, default=str))


# Written once by a capture: a copied snapshot keeps them, a new capture never
# repeats them.
CAPTURE_FIELDS = ("extract_at", "extract_refreshed", "clock_before", "review_copy")


def capture_id(m: dict) -> str | None:
    """sha256 of the manifest's capture fields, or None when it records none."""
    kept = {k: m[k] for k in CAPTURE_FIELDS if m.get(k)}
    if not kept:
        return None
    text = json.dumps(kept, sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()
