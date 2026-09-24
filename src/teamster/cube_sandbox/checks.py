"""Repo-level consistency, with no credentials and no warehouse read.

Comparing model and snapshot within one commit is what makes this work on a
refresh pull request: the snapshot was computed from the model as it stood
when the refresh ran, so a model change landing meanwhile would otherwise
merge a commit whose halves disagree. Holding the invariant at every commit
means the pinned pair is consistent for free, because the pin is a commit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teamster.cube_sandbox import manifest, model, personas, snapshot

CUBE_ROOT = Path("src/cube")


def missing_columns(referenced: dict[str, set[str]], snap: dict[str, Any]) -> list[str]:
    tables = snap["tables"]
    return sorted(
        f"{table}.{column}"
        for table, columns in referenced.items()
        for column in columns
        if column not in tables.get(table, {})
    )


def missing_tables(tables: set[str], snap: dict[str, Any]) -> list[str]:
    """Tables the model reads that the snapshot has never seen.

    Separate from missing_columns because the fix is different: a whole
    table absent means the refresh never introspected it, not that one
    column drifted.
    """
    return sorted(tables - set(snap["tables"]))


def stale_manifest(cube_root: Path = CUBE_ROOT) -> str | None:
    """The committed manifest, if it no longer matches what build() emits.

    Generated-and-committed files drift silently. Every coverage result is
    asserted against this contract, so a stale one makes every later pass
    meaningless.
    """
    fresh = manifest._dump(
        manifest.build(
            snap=snapshot.load(),
            referenced=model.referenced_columns(cube_root),
            key_columns=model.key_columns(cube_root),
            policy_columns=model.policy_columns(cube_root),
            not_null=manifest.dbt_not_null(manifest.MARTS_ROOT),
            scopes=model.scope_values(cube_root / "access.js"),
            people=personas.load(manifest.PERSONAS_PATH),
        )
    )
    committed = manifest.MANIFEST_PATH.read_text()
    if fresh == committed:
        return None
    return (
        f"{manifest.MANIFEST_PATH} is stale: regenerate with "
        "`uv run python -m teamster.cube_sandbox.manifest`"
    )


def run(cube_root: Path = CUBE_ROOT) -> list[str]:
    """Every consistency failure, as lines a human can act on."""
    snap = snapshot.load()
    problems = [
        f"table absent from snapshot: {t}"
        for t in missing_tables(model.table_set(cube_root), snap)
    ]
    problems += [
        f"column absent from snapshot: {c}"
        for c in missing_columns(model.referenced_columns(cube_root), snap)
    ]
    if stale := stale_manifest(cube_root):
        problems.append(stale)
    return problems


def main() -> int:
    problems = run()
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} consistency failure(s)")
        return 1
    print("model, snapshot and manifest agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
