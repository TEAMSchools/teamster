"""Prove a dbt YAML edit changed descriptions only.

Usage: yaml_description_diff.py OLD_YML NEW_YML

Loads both files, drops every `description` key at any depth, and compares.
Prints each path that differs and exits 1, or prints `description-only` and
exits 0. To compare against main:
git -C <worktree> show origin/main:<path> > <scratchpad>/old.yml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k != "description"}
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


def _diff(old: Any, new: Any, path: str, out: list[str]) -> None:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new), key=str):
            _diff(old.get(key), new.get(key), f"{path}.{key}", out)
    elif isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        for index, (a, b) in enumerate(zip(old, new, strict=True)):
            _diff(a, b, f"{path}[{index}]", out)
    elif old != new:
        out.append(path or ".")


def non_description_changes(old_text: str, new_text: str) -> list[str]:
    out: list[str] = []
    old = _strip(yaml.safe_load(old_text))
    new = _strip(yaml.safe_load(new_text))
    _diff(old, new, "", out)
    return out


def main(argv: list[str]) -> int:
    changes = non_description_changes(
        Path(argv[1]).read_text(), Path(argv[2]).read_text()
    )
    for change in changes:
        print(change)
    if changes:
        return 1
    print("description-only")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
