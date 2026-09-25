from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SKILL_SCRIPTS = (
    Path(__file__).resolve().parents[2] / ".claude/skills/model-support/scripts"
)


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SOURCE = """---
name: demo
---

# Demo

Intro line.

## Goals

Goal text.

```sql
## not a heading (backtick fence)
```

### Sub of goals

~~~text
## not a heading (tilde fence)
~~~

## Gotchas

````markdown
```
## still not a heading (nested fence)
```
````

Last line.
"""


def test_split_routes_sections_and_keeps_fenced_hashes():
    split = _load("split_skill")
    out = split.split_sections(
        SOURCE,
        {"Goals": "references/goals.md", "Gotchas": "references/gotchas.md"},
        default="SKILL.md",
    )
    assert "Intro line.\n" in out["SKILL.md"]
    goals = "".join(out["references/goals.md"])
    assert "## not a heading (backtick fence)" in goals
    assert "## not a heading (tilde fence)" in goals
    assert "### Sub of goals" in goals
    gotchas = "".join(out["references/gotchas.md"])
    assert "## still not a heading (nested fence)" in gotchas
    assert "Last line." in gotchas


def test_split_accounts_for_every_line():
    split = _load("split_skill")
    out = split.split_sections(
        SOURCE,
        {"Goals": "references/goals.md", "Gotchas": "references/gotchas.md"},
        default="SKILL.md",
    )
    assert sum(len(v) for v in out.values()) == len(SOURCE.splitlines(keepends=True))


def test_split_rejects_unmapped_heading():
    split = _load("split_skill")
    with pytest.raises(KeyError, match="Gotchas"):
        split.split_sections(SOURCE, {"Goals": "g.md"}, default="SKILL.md")
