# model-support skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `.claude/skills/model-support/`, a three-mode skill (document,
update, QA) for dbt model families, walk-tested per
`superpowers:writing-skills`.

**Architecture:** An ICM-shaped entry `SKILL.md` that routes each step to one
file under `references/`, plus three Python helper scripts under `scripts/` with
pytest coverage. RED baselines run first, without the skill; walk tests run
last, with it.

**Tech Stack:** Markdown skill files, Python 3 standard library only (scripts),
pytest, trunk.

**Spec:** `docs/superpowers/specs/2026-09-24-model-support-skill-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill`
  (abbreviated `$WT` below; write it out in full in every command, since hook
  Rule 7 blocks uppercase shell variables). Every git call is
  `git -C <worktree>`.
- Open every file under `.claude/skills/` with the Read tool, never `cat` (root
  CLAUDE.md, _Tooling_). `.claude/rules/claude-md-editing.md` applies to every
  skill line: each line names a decision Claude makes differently; no
  tombstones; bold only for lines a skimmer must not miss.
- Frontmatter `description` starts "Use when…" and lists triggers only, never
  the workflow (`superpowers:writing-skills`, CSO).
- Never call the Tableau MCP or load `tableau-workbook-xml` without warning the
  user and getting a go-ahead.
- Sheet handoffs: whole tab or block, tab-separated file in the session
  scratchpad, handed over as a path with the sheet link and tab name.
- No PII in git or GitHub. Aggregates without small cells only.
- Walk-test pass: the entry file plus at most two more reads.
- Scripts: standard library only; run through `uv run`.
- Lint every changed file before pushing:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd in the worktree.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Review Focus

1. A family with no exposure at all (an `int_` model feeding a process nobody
   declared). Expected: the skill asks the user who consumes it and suggests
   adding the exposure, rather than guessing the branch. Pinned in Task 5
   (intake-and-inventory text) and walk test W1's checklist.
2. An exposure set that mixes Tableau and a Google Sheet on the same family.
   Expected: both outline branches, one section per consumer. Pinned in Task 5.
3. `split_skill.py` on a skill with `##` inside a fenced block, including a
   `~~~` fence and a fence with an info string. Expected: those lines stay in
   their section, lines in = lines out. Pinned in Task 2 tests.
4. `comment_only_diff.py` on SQL containing `--` inside a string literal
   (`'--'`, `"a -- b"`). Expected: the string is not treated as a comment, so a
   change inside it is reported as a logic change. Pinned in Task 4 tests.
5. QA requested on a family with no reference doc. Expected: the skill runs the
   inventory step first, then QA. Pinned in Task 7 (qa-mode text) and walk test
   W5.

---

### Task 1: RED baselines (no skill)

**Files:**

- Create: `<session scratchpad>/red-baseline.md` (not committed)

**Interfaces:**

- Produces: the baseline failure list that Tasks 5-8 must each address, and that
  the PR body's "For Claude" section cites.

- [ ] **Step 1: Dispatch two cold Sonnet subagents in parallel, one message**

Model `sonnet`. Neither prompt names `model-support`. Prompt A:

```text
You are working in the teamster repo at /workspaces/teamster (read-only for
this task). Planning only: no scripts, queries, git, or edits. Do the reading
yourself; no sub-agents.

Task from the user: "Document the athletic eligibility tracker so the next
owner can run it. It's rpt_gsheets__athletic_eligibility and whatever feeds
it."

Return, under 400 words: (1) every file you Read, in order; (2) your concrete
plan, step by step, including what you would write, where, and how you would
verify each claim; (3) what you would ask the user before starting.
```

Prompt B:

```text
You are working in the teamster repo at /workspaces/teamster (read-only for
this task). Planning only: no scripts, queries, git, or edits. Do the reading
yourself; no sub-agents.

Task from the user: "I refactored int_tableau__college_assessment_roster_scores
for readability. Nothing should change on the CARAT dashboard. Can you check
prod values will still match?"

Return, under 400 words: (1) every file you Read, in order; (2) your concrete
plan, step by step; (3) what you would ask the user before starting.
```

- [ ] **Step 2: Score each response against this checklist and write the result
      to `red-baseline.md`**

For each item, record hit (the failure happened), avoided, or not applicable:

```text
A1 asks for source material (docs, PDFs, notes)
A2 asks about Google Sheet upkeep processes
A3 proposes a family boundary and waits, instead of auditing shared upstreams
   (int_extracts__student_enrollments, base_powerschool__final_grades)
A4 picks a process outline (sheet consumer), not a dashboard outline
A5 plans a cold review of doc claims against the SQL
A6 plans uniqueness tests checked against prod first
A7 plans description-only YAML edits with a diff check
A8 proposes (or asks about) a family skill rather than always/never creating one
B1 diffs dev against prod on the view key, both directions
B2 ties each difference to a SQL change
B3 goes to the warehouse first; Tableau only with a warning
B4 accounts for dev-build traps (--defer, stale dev tables)
B5 keeps student-level differences out of GitHub
```

Expected: most A and B items are hits. If a subagent avoids an item, note what
it read that taught it; the skill need not repeat that source's content, only
link to it.

- [ ] **Step 3: Report the baseline to the user in one short message** (no
      commit; the file stays in scratch).

---

### Task 2: `split_skill.py` with tests

**Files:**

- Create: `$WT/.claude/skills/model-support/scripts/split_skill.py`
- Create: `$WT/tests/skills/__init__.py` (empty)
- Create: `$WT/tests/skills/test_model_support_scripts.py`

**Interfaces:**

- Produces:
  `split_sections(text: str, mapping: dict[str, str], default: str) -> dict[str, list[str]]`
  — keys are destination file names, values are lines (with newline endings) in
  source order. `mapping` keys are exact `## ` heading texts (without the `## `
  prefix). Lines before the first `## ` heading go to `default`. A `## ` heading
  missing from `mapping` raises `KeyError` naming it.
- CLI: `split_skill.py SOURCE MAPPING_JSON OUTDIR` — writes each destination
  under OUTDIR (overwriting), prints `lines in: N, lines out: N`, exits 1 if the
  counts differ.

- [ ] **Step 1: Write the failing tests**

`````python
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
`````

- [ ] **Step 2: Run to verify failure**

Run:
`VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill run pytest /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill/tests/skills/test_model_support_scripts.py -q 2>&1 | tail -n 15`

Expected: 3 errors, `FileNotFoundError` / `No such file` for `split_skill.py`.

- [ ] **Step 3: Implement**

```python
"""Split an oversized skill file into references, verbatim, by `## ` heading.

Usage: split_skill.py SOURCE MAPPING_JSON OUTDIR

MAPPING_JSON maps each `## ` heading text to a destination path relative to
OUTDIR, plus an optional "_default" key for lines before the first heading
(default: SKILL.md). Every source line lands in exactly one destination.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FENCE = re.compile(r"^(`{3,}|~{3,})")


def split_sections(
    text: str, mapping: dict[str, str], default: str
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    dest = default
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not line[
                len(marker) :
            ].strip():
                fence = None
        elif fence is None and line.startswith("## "):
            heading = line[3:].strip()
            if heading not in mapping:
                raise KeyError(f"unmapped heading: {heading}")
            dest = mapping[heading]
        out.setdefault(dest, []).append(line)
    return out


def main(argv: list[str]) -> int:
    source, mapping_path, outdir = Path(argv[1]), Path(argv[2]), Path(argv[3])
    mapping = json.loads(mapping_path.read_text())
    default = mapping.pop("_default", "SKILL.md")
    text = source.read_text()
    out = split_sections(text, mapping, default)
    for dest, lines in out.items():
        path = outdir / dest
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines))
    lines_in = len(text.splitlines(keepends=True))
    lines_out = sum(len(v) for v in out.values())
    print(f"lines in: {lines_in}, lines out: {lines_out}")
    return 0 if lines_in == lines_out else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run to verify pass**

Same command as Step 2. Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill add .claude/skills/model-support/scripts/split_skill.py tests/skills/__init__.py tests/skills/test_model_support_scripts.py
git -C /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill commit -m "feat(model-support): add a verbatim skill splitter with line accounting" -m "Refs #5434" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `check_links.py` with tests

The spec names `check_links.sh`; this plan makes it Python so it can share the
pytest file. Same job, same location.

**Files:**

- Create: `$WT/.claude/skills/model-support/scripts/check_links.py`
- Modify: `$WT/tests/skills/test_model_support_scripts.py` (append)

**Interfaces:**

- Produces:
  `find_broken_links(paths: list[Path]) -> list[tuple[Path, int, str]]` — scans
  every `*.md` file under each path (file or directory), returns
  `(file, line_number, target)` for each relative link target that does not
  exist. Skips `http:`, `https:`, `mailto:`, pure `#anchor` links, and anything
  inside fenced code. Strips `#fragment` before resolving; resolves relative to
  the file's directory.
- CLI: `check_links.py PATH...` — prints `file:line: target` per broken link,
  exits 1 if any.

- [ ] **Step 1: Append the failing tests**

````python
def test_check_links_reports_only_broken_relative_links(tmp_path):
    links = _load("check_links")
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "goals.md").write_text("# Goals\n")
    (tmp_path / "SKILL.md").write_text(
        "[ok](references/goals.md)\n"
        "[ok anchor](references/goals.md#goals)\n"
        "[web](https://example.com/x)\n"
        "[self](#top)\n"
        "[broken](references/missing.md)\n"
        "```text\n[in fence](nowhere.md)\n```\n"
    )
    broken = links.find_broken_links([tmp_path])
    assert broken == [(tmp_path / "SKILL.md", 5, "references/missing.md")]
````

- [ ] **Step 2: Run to verify failure** — same pytest command as Task 2 Step 2.
      Expected: 1 error for `check_links.py` missing, 3 passed.

- [ ] **Step 3: Implement**

```python
"""Report relative markdown links whose targets do not exist.

Usage: check_links.py PATH...   (files or directories; scans *.md)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
SKIP = ("http:", "https:", "mailto:", "#")


def _md_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        files.extend(sorted(path.rglob("*.md")) if path.is_dir() else [path])
    return files


def find_broken_links(paths: list[Path]) -> list[tuple[Path, int, str]]:
    broken: list[tuple[Path, int, str]] = []
    for md in _md_files(paths):
        in_fence = False
        for number, line in enumerate(md.read_text().splitlines(), start=1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for target in LINK.findall(line):
                if target.startswith(SKIP):
                    continue
                if not (md.parent / target.split("#", 1)[0]).exists():
                    broken.append((md, number, target))
    return broken


def main(argv: list[str]) -> int:
    broken = find_broken_links([Path(p) for p in argv[1:]])
    for md, number, target in broken:
        print(f"{md}:{number}: {target}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run to verify pass.** Expected: `4 passed`.

- [ ] **Step 5: Commit** — `git -C <worktree> add` the script and the test file;
      message
      `feat(model-support): add a relative-link checker for skills and docs`,
      then `Refs #5434` and the co-author line, as in Task 2.

---

### Task 4: `comment_only_diff.py` with tests

**Files:**

- Create: `$WT/.claude/skills/model-support/scripts/comment_only_diff.py`
- Modify: `$WT/tests/skills/test_model_support_scripts.py` (append)

**Interfaces:**

- Produces: `strip_comments(sql: str) -> str` — removes `-- …` to end of line,
  `/* … */`, and `{# … #}`, leaving anything inside `'…'`, `"…"`, or `` `…` ``
  untouched; then collapses all whitespace runs to one space and strips.
  `is_comment_only(old: str, new: str) -> bool`.
- CLI: `comment_only_diff.py OLD_SQL NEW_SQL` — prints `comment-only` and exits
  0, or prints `LOGIC CHANGE` and exits 1. To compare against main:
  `git -C <worktree> show origin/main:<path> > <scratchpad>/old.sql`.

- [ ] **Step 1: Append the failing tests**

```python
def test_comment_only_edit_is_detected():
    diff = _load("comment_only_diff")
    old = "select a, -- old note\n    b\nfrom t /* block */\n{# jinja note #}\n"
    new = "select a,\n    b -- new note\nfrom t\n"
    assert diff.is_comment_only(old, new)


def test_logic_edit_is_detected():
    diff = _load("comment_only_diff")
    assert not diff.is_comment_only("select a from t", "select b from t")


def test_dashes_inside_strings_are_not_comments():
    diff = _load("comment_only_diff")
    old = "select '--' as sep, \"a -- b\" as label from t"
    new = "select '-' as sep, \"a -- b\" as label from t"
    assert "'--'" in diff.strip_comments(old)
    assert not diff.is_comment_only(old, new)
```

- [ ] **Step 2: Run to verify failure.** Expected: 3 errors for the missing
      script, 4 passed.

- [ ] **Step 3: Implement**

```python
"""Prove a SQL edit is comment-only by comparing comment-stripped tokens.

Usage: comment_only_diff.py OLD_SQL NEW_SQL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

QUOTES = "'\"`"


def strip_comments(sql: str) -> str:
    out: list[str] = []
    i, n = 0, len(sql)
    quote: str | None = None
    while i < n:
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(sql[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
        elif ch in QUOTES:
            quote = ch
            out.append(ch)
            i += 1
        elif sql.startswith("--", i):
            end = sql.find("\n", i)
            i = n if end == -1 else end
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        elif sql.startswith("{#", i):
            end = sql.find("#}", i + 2)
            i = n if end == -1 else end + 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def is_comment_only(old: str, new: str) -> bool:
    return strip_comments(old) == strip_comments(new)


def main(argv: list[str]) -> int:
    old, new = Path(argv[1]).read_text(), Path(argv[2]).read_text()
    if is_comment_only(old, new):
        print("comment-only")
        return 0
    print("LOGIC CHANGE")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run to verify pass.** Expected: `7 passed`.

- [ ] **Step 5: Commit** — message
      `feat(model-support): add a comment-only SQL diff check`, then
      `Refs #5434` and the co-author line.

---

### Task 5: references for document-mode intake, inventory, and the doc

**Files:**

- Create: `$WT/.claude/skills/model-support/references/intake-and-inventory.md`
- Create: `$WT/.claude/skills/model-support/references/reference-doc.md`

**Interfaces:**

- Consumes: the spec's _Document mode flow_ steps 1-3 and _Doc outlines_.
- Produces: section headings that `SKILL.md` (Task 8) links to by file name:
  `intake-and-inventory.md` and `reference-doc.md`.

- [ ] **Step 1: Write `intake-and-inventory.md`** with these sections, in this
      order, and no others:

1. `# Intake and inventory` — one line: document mode steps 1-2; stop after the
   boundary is confirmed.
2. `## Intake` — ask, in one message: (a) source material, accepted three ways
   (a file dropped in the session scratchpad; a public URL, read with WebFetch;
   an org Google Drive file shared with the Codespaces account, read through the
   Drive connector), plus a superpowers spec if the model was designed through
   brainstorming; (b) whether the family has Google Sheet upkeep (examples:
   CARAT goal updates, season regeneration, College Board ID tagging); (c) who
   owns the family now and who inherits it. Granola and other claude.ai
   connectors may need authorizing in claude.ai settings; if one is unavailable,
   ask for an export to scratch instead.
3. `## Find the consumers` — grep `src/dbt/*/models/exposures/*.yml` for the
   model names. Branch table: Tableau exposure → dashboard outline; Google
   Sheet, extract, or other → process outline; both → both outlines, one section
   per consumer; none → ask the user who consumes it and suggest adding the
   exposure (see `src/dbt/kipptaf/CLAUDE.md` → Exposures). Reading the exposure
   YAML is local; do not open Tableau.
4. `## Propose the boundary` — walk parents from each exposed model
   (`rg -o 'ref\("[^"]+"\)'` on each `.sql`, `find src/dbt -name '<model>.sql'`
   to locate each, reading the current project's copy first per
   `src/dbt/CLAUDE.md`). Keep a model when every child it has is inside the
   family (`rg -l 'ref\("<model>"\)' src/dbt` lists children). Present the list
   as a table (model, layer, in/out, why) and wait for the user's confirmation.
   Shared upstreams get one line in the doc: "reads X for Y, joined on Z".
5. `## Measure what exists` — existing doc under `docs/models/`, existing skill
   under `.claude/skills/`; line counts per heading with
   `awk '/^#{2,4} /{if(h)print n"\t"h; h=$0; n=0} {n++} END{print n"\t"h}' <file>`.
   Mark as cut candidates: one-time checks, change logs, "Resolved —" notes,
   stale counts. Note which dashboard views or process steps have no
   explanation.

- [ ] **Step 2: Write `reference-doc.md`** with these sections:

1. `# Reference doc` — audience: the next owner and the family skill; the page
   is public on GitHub.
2. `## Outline` — shared opening (What it is → How it fits together, with a
   diagram → Terms → Where the data comes from: source and owner), the dashboard
   middle (per view: What it shows / Grain / Reads / Worth knowing), the process
   middle (What triggers it → Inputs → Steps → Outputs: where they land and who
   reads them → Who runs it and when), shared close (Supporting models → Inputs:
   Google Sheets and others → Decisions → Known issues, need to fix → Yearly
   upkeep).
3. `## What to cut` — one-time before/after measurements (move to the family
   skill if it cites them), "Resolved —" and "used to" narration, tombstones,
   counts that go stale ("27 students" → "a few dozen"), evidence tables.
4. `## Public-page rules` — no internal sheet URLs or IDs ("ask the data team"),
   no emails, no student data, no small-cell counts; no standalone bold line as
   a heading (MD036, `docs/CLAUDE.md`); add the page to the `mkdocs.yml` nav
   under `Models`.
5. `## Cold review` — required for a new doc and for every edited section. Ask
   the user before dispatching; they may skip a trivial edit. Dispatch one Opus
   subagent with this prompt, verbatim apart from the placeholders:

   ```text
   You are reviewing a project manual as the person about to inherit the
   project. Read <absolute doc path> in full (or, for an update, only these
   sections: <section names>). Then spot-check at least 10 specific factual
   claims against the code under <absolute worktree path>/src/dbt.
   Prioritise grain, which models read which, join keys and partitions,
   filters, and denominators. Do the reading yourself; no sub-agents; no edits.
   Report: wrong or overstated claims with file:line evidence; where a
   newcomer gets lost; what reads like a check dump or change log; anything
   inappropriate for a public page.
   ```

   Verify each flag against the SQL yourself before editing. Fix every confirmed
   one.

6. `## Repoint links` — after renaming sections, grep the skills for the old
   names (`rg -n '_<Old section>_|reference doc' .claude/skills`) and run
   `scripts/check_links.py` on the skill and the doc.

- [ ] **Step 3: Lint and link-check**

```bash
cd /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/model-support/references/intake-and-inventory.md .claude/skills/model-support/references/reference-doc.md </dev/null 2>&1 | tail -n 5 && uv run python .claude/skills/model-support/scripts/check_links.py .claude/skills/model-support
```

Expected: `No issues`; the link checker prints nothing and exits 0.

- [ ] **Step 4: Commit** — message
      `feat(model-support): add intake, inventory, and reference-doc guides`.

---

### Task 6: references for the YAML audit, tests, and known issues

**Files:**

- Create: `$WT/.claude/skills/model-support/references/yaml-audit.md`
- Create: `$WT/.claude/skills/model-support/references/tests-and-issues.md`

**Interfaces:**

- Consumes: the spec's document steps 4-6.
- Produces: files linked from `SKILL.md` by name.

- [ ] **Step 1: Write `yaml-audit.md`** with sections:

1. `# YAML audit` — descriptions only; the SQL is the source of truth over the
   doc. Read `.claude/rules/dbt-yaml.md` first (it loads on the first YAML
   read).
2. `## Sizing` — inline for about five models or fewer; otherwise split the
   family into groups of about six (staging, intermediate, views) and dispatch
   one Opus subagent per group, in parallel, in one message.
3. `## The audit prompt` — verbatim:

   ```text
   Audit dbt YAML descriptions against the SQL for these models: <list, each
   with its absolute .sql and properties .yml path under <worktree>>. Do the
   edits yourself; no sub-agents. Edit descriptions only: never SQL, tests,
   config, contains_pii, contract, data_type, or column names. The SQL is the
   source of truth over any doc. Never change a test to match a description
   or the reverse: flag the disagreement instead. Remove change-log narration,
   stale counts, TODOs, and issue refs (#1234) from descriptions. Then run,
   from <worktree>, trunk check --force --no-fix on each edited file and
   uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>.
   Report: per file a one-line summary; FLAGS with file:line evidence (column
   lists that don't match the SQL, missing uniqueness tests, wrong grains);
   lint and parse results verbatim.
   ```

4. `## Verify the diff yourself` —
   `git -C <worktree> diff -U0 -- '*.yml' | rg '^[+-].*(data_type|data_tests|severity|combination_of_columns|contains_pii|materialized|- name:)'`
   must show only intentional changes, each listed in the commit message. Then
   `uv run dbt parse --no-partial-parse --project-dir <worktree>/src/dbt/<project>`.
5. `## Flags` — the reviewers' flags are the most valuable output; each goes to
   `tests-and-issues.md` or to "Known issues, need to fix".

- [ ] **Step 2: Write `tests-and-issues.md`** with sections:

1. `# Tests and known issues`
2. `## Propose tests from the model` — per model: the grain's key gets `unique`
   or `dbt_utils.unique_combination_of_columns` (required on every staging,
   intermediate, and `rpt_` model, `.claude/rules/dbt-models.md`); `not_null` on
   key columns except `generate_surrogate_key` output; `accepted_values` on
   low-cardinality categorical columns (status, region, test type);
   `relationships` to the parent model's key where the join is a lookup. Present
   as a table (model, test, column, why, prod result) and wait for approval.
3. `## Check against prod first` — rows vs distinct keys:

   ```sql
   select count(*) as n_rows, count(distinct to_json_string(struct(<key cols>))) as n_keys
   from `teamster-332318.<dataset>.<model>`
   ```

   Through the BigQuery MCP (SELECT-only). Staging tests need
   `config: severity: error`; the kipptaf default is warn.

4. `## A test that fails today` — still add it (it warns); put the cause in the
   doc's "Known issues, need to fix" with the query that shows it, aggregates
   only.
5. `## "Probably harmless" gets a query` — every suspected-harmless oddity is
   checked: an arbitrary `row_number` pick is harmless only if every column
   consumers read is constant within the partition (`count(distinct <col>)` per
   partition = 1); dead rows are harmless only if the consumer never reads them
   (group in the consumer). Record each check in the commit message.
6. `## SQL comments` — stale counts and "after this PR" narration in SQL
   comments are removed; prove it with `scripts/comment_only_diff.py`; warn the
   user that a comment edit marks the model `state:modified`, so dbt Cloud CI
   rebuilds its descendants.

- [ ] **Step 3: Lint and link-check** — same command shape as Task 5 Step 3, on
      the two new files. Expected: clean.

- [ ] **Step 4: Commit** — message
      `feat(model-support): add YAML-audit and tests guides`.

---

### Task 7: references for the family skill, update mode, and QA mode

**Files:**

- Create: `$WT/.claude/skills/model-support/references/model-skill.md`
- Create: `$WT/.claude/skills/model-support/references/update-mode.md`
- Create: `$WT/.claude/skills/model-support/references/qa-mode.md`

**Interfaces:**

- Consumes: spec document step 7, _Update mode flow_, _QA mode flow_; scripts
  from Tasks 2-4 by path.
- Produces: files linked from `SKILL.md`; the walk-test prompt that Task 9
  reuses verbatim.

- [ ] **Step 1: Write `model-skill.md`** with sections:

1. `# The family skill`
2. `## Propose, then ask` — list what a skill would hold for this family from
   what inventory found: sheet-upkeep procedures, yearly rollover (grep the
   family SQL for `current_academic_year` and hard-coded years), recurring QA
   checks, questions people ask about the numbers, before/after history. If
   none, say so and propose no skill. Wait for the user.
3. `## Shape` — ICM inside the repo convention: `SKILL.md` (frontmatter
   `description` starting "Use when…" with triggers and model names; rules that
   apply to every task; a route-by-task table sending each task to one
   reference; a "why did this number change" table if the family has one; the
   sheet-handoff contract; a scripts list) and `references/*.md`, one per task
   area. Worked examples: `.claude/skills/tableau-workbook-xml/` and, once PR
   #5542 merges, `.claude/skills/carat-dashboard/`. Standardize on
   `references/`, not `reference/`.
4. `## Restructuring an oversized skill` — write a mapping JSON (each `## `
   heading → destination; `_default` for the entry), run
   `uv run python .claude/skills/model-support/scripts/split_skill.py <SKILL.md> <mapping.json> <skill dir>`
   (it must print equal lines in and out), then fix cross-file `_Section_`
   pointers and relative links (`../scripts/`, `../../../../docs/`), then
   `scripts/check_links.py <skill dir>`. Then trim the entry to routing.
5. `## Walk test` — required for a new skill and for every edited skill file, on
   a task that uses the edit. Ask before dispatching. Cold Sonnet, planning
   only, prompt verbatim:

   ```text
   Walk test of a Claude Code skill. Entry file: <abs path>. Read it with the
   Read tool, then read only what it routes you to. Do the reading yourself;
   no sub-agents. Planning only: no scripts, queries, git, or edits. Task:
   <realistic user request>. Return, under 300 words: (1) every file you Read,
   in order, with line ranges; (2) your concrete steps; (3) anything unclear,
   missing, or mis-pointed.
   ```

   Pass: the entry plus at most two more reads. Fixes that worked on CARAT:
   merge a reference every task needed together; add an explicit "this overrides
   step N of X" link; name where a doc section stops ("read X and Y, stop at
   heading Z"). Re-run until it passes.

- [ ] **Step 2: Write `update-mode.md`** with sections:

1. `# Update mode`
2. `## Find what moved` —
   `git -C <worktree> diff --stat origin/main...HEAD -- <family paths>`; if the
   family has no reference doc yet, stop and run document mode.
3. `## Change → re-run` — the spec's four-row table, each row expanded to the
   exact reference file to follow (column → `yaml-audit.md` + `reference-doc.md`
   sections that name it + `tests-and-issues.md`; join/filter/grain → prod grain
   check from `tests-and-issues.md`, then `qa-mode.md` refactor parity if values
   may move; new view/tab/model → `intake-and-inventory.md` boundary check + a
   new doc section + a new skill route; comment only →
   `scripts/comment_only_diff.py` and the CI warning).
4. `## Subagent checks after every update` — cold review of every edited doc
   section (`reference-doc.md` → Cold review); walk test of every edited
   family-skill file (`model-skill.md` → Walk test). Ask before each dispatch.

- [ ] **Step 3: Write `qa-mode.md`** with sections:

1. `# QA mode` — start from the family's reference doc for grains, keys, and
   known issues; if there is none, run `intake-and-inventory.md` first. If the
   family skill has its own QA procedure, link straight to that reference file,
   never to the family's `SKILL.md` (CARAT:
   `.claude/skills/carat-dashboard/references/official-scores-qa.md`), follow
   it, and skip the generic checks. Going through the family's entry file costs
   a third read and fails the walk test.
2. `## New data landed` — the five comparisons from the spec, each with a query
   shape; previous load via
   `FOR SYSTEM_TIME AS OF timestamp_sub(current_timestamp(), interval <n> hour)`
   (7 days back at most; one timestamp per query, so run before and now as
   separate queries); same point last year via `academic_year - 1`. Label every
   finding expected (with the reason) or needs a look.
3. `## Refactor parity` — build the changed `rpt_` views in dev (invoke
   `dbt-local-dev` first for `--defer` and stale-dev traps) or read the CI
   schema (`dbt_cloud_pr_<job>_<pr>_*`). Diff on the view key, both directions:

   ```sql
   select 'only_in_dev' as side, count(*) as n
   from (
       select <key cols> from `<dev relation>`
       except distinct
       select <key cols> from `<prod relation>`
   )
   union all
   select 'only_in_prod', count(*)
   from (
       select <key cols> from `<prod relation>`
       except distinct
       select <key cols> from `<dev relation>`
   )
   ```

   Then, on matched keys, count rows where each column differs
   (`countif(d.<col> is distinct from p.<col>)`), grouped by school and term.
   Tie each difference to a hunk of the SQL diff; label it regression or
   intended.

4. `## Tableau (opt-in)` — only when the warehouse diff is clean and the user
   needs proof the dashboard itself matches. Say it costs a lot of tokens and
   wait for a yes before any Tableau MCP call or loading `tableau-workbook-xml`.
5. `## Where results go` — student-level rows stay in the terminal and the
   session scratchpad; GitHub gets aggregates without small cells
   (`.claude/rules/ferpa-pii.md`).

- [ ] **Step 4: Lint and link-check** the three files. Expected: clean.

- [ ] **Step 5: Commit** — message
      `feat(model-support): add family-skill, update-mode, and QA-mode guides`.

---

### Task 8: the entry `SKILL.md`

**Files:**

- Create: `$WT/.claude/skills/model-support/SKILL.md`

**Interfaces:**

- Consumes: every reference file name from Tasks 5-7 and script names from Tasks
  2-4.

- [ ] **Step 1: Write `SKILL.md`**, target under 120 lines, exactly this
      structure:

```markdown
---
name: model-support
description: >-
  Use when documenting a dbt model family for handover (a dashboard's lineage or
  a process model such as a Google Sheet extract), updating a documented
  family's reference doc, YAML, tests, or skill after a model change, or QA-ing
  prod values after new data lands or after a refactor that should not change
  them. Triggers: "document this model", "update the docs for", "write a
  reference doc", "restructure this skill", "check prod values", "did the
  refactor change anything", "new scores landed", or a docs/models page or
  family skill that no longer matches the SQL.
---

# Model support

Three modes for one dbt model family: document, update, QA. Pick the mode from
the request; if unclear, ask.

## Rules for every mode

- No Tableau MCP call and no `tableau-workbook-xml` load without warning the
  user about the token cost and getting a yes. QA goes to the warehouse first.
- Sheet changes go out as the whole tab or block, as a tab-separated file in the
  session scratchpad, handed over as a path with the sheet link and tab name.
  Never comma-separated; never pasted into chat.
- Read the source the user is editing (a Sheets external through ADC from
  Python), not a reshaped staging table.
- State a pipeline behavior only from code or a before/after observation, never
  from a timestamp.
- Read the whole block before flagging a bug in it.
- No doc claim ships without the cold review; no skill edit ships without a walk
  test. Ask before each dispatch.
- Student-level rows stay in the terminal and scratch.

## Route by step

| Mode     | Step                                   | Read                               |
| -------- | -------------------------------------- | ---------------------------------- |
| Document | 1-2 Intake, consumers, boundary        | references/intake-and-inventory.md |
| Document | 3 Reference doc and cold review        | references/reference-doc.md        |
| Document | 4 YAML descriptions                    | references/yaml-audit.md           |
| Document | 5-6 Tests, known issues, SQL comments  | references/tests-and-issues.md     |
| Document | 7 Family skill, restructure, walk test | references/model-skill.md          |
| Update   | Any change to a documented family      | references/update-mode.md          |
| QA       | New data or refactor parity            | references/qa-mode.md              |

Document mode runs steps 1-8 in order; step 8 is below.

## Step 8: close out

Trunk on every changed file (`--force --no-fix`),
`uv run dbt parse --no-partial-parse`, commits that state what was verified,
push, PR. Tell the user every judgment call they might disagree with.

## Scripts

- `scripts/split_skill.py` — verbatim split of an oversized skill.
- `scripts/check_links.py` — relative links that do not resolve.
- `scripts/comment_only_diff.py` — prove a SQL edit is comment-only.

## Acceptance for a run

Walk tests pass (entry plus at most two reads); the cold review finds no wrong
claims after fixes; the YAML diff is description-only apart from listed
intentional changes; `dbt parse` and trunk pass; every missing uniqueness test
is added or listed as a known issue.
```

Make the route-table links real markdown links
(`[intake-and-inventory.md](references/intake-and-inventory.md)`) and script
names links to `scripts/…`.

- [ ] **Step 2: Lint, link-check, line count**

```bash
cd /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/model-support/SKILL.md </dev/null 2>&1 | tail -n 5 && uv run python .claude/skills/model-support/scripts/check_links.py .claude/skills/model-support && wc -l .claude/skills/model-support/SKILL.md
```

Expected: clean, no broken links, under 120 lines.

- [ ] **Step 3: Commit** — message
      `feat(model-support): add the routing entry file`.

---

### Task 9: GREEN walk tests and fixes

**Files:**

- Modify: any file under `$WT/.claude/skills/model-support/` that a walk test
  shows mis-pointed.

- [ ] **Step 1: Dispatch five cold Sonnet walk tests in one message**, using the
      walk-test prompt from `model-skill.md` → Walk test with entry
      `/workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill/.claude/skills/model-support/SKILL.md`.
      Tasks:

```text
W1 "Document the athletic eligibility tracker (rpt_gsheets__athletic_eligibility)
   so the next owner can run it."
W2 "I added a column to rpt_gsheets__athletic_eligibility. Update everything
   that documents it."
W3 "The dibels-dashboard skill is 3,000 lines. Restructure it so sessions
   actually read it."
W4 "New official SAT scores landed for CARAT. Check the prod values make sense."
W5 "I refactored int_students__athletic_eligibility for readability; it has no
   reference doc yet. Check prod values won't change."
```

- [ ] **Step 2: Score each.** Pass: SKILL.md plus at most two more reads, and
      the plan hits the matching RED checklist items from Task 1 (W1: A1-A8; W5:
      B1-B5 and the inventory-first rule). Every read counts, including files in
      a family's own skill. W4 passes only by reading SKILL.md, `qa-mode.md`,
      and CARAT's `official-scores-qa.md` directly.

- [ ] **Step 3: Fix every failure** in the file the walk test names (merge
      references, add a pointer, name a stopping heading). Re-lint and
      re-link-check the edited files.

- [ ] **Step 4: Re-run only the failed walk tests.** Repeat Steps 3-4 until all
      five pass.

- [ ] **Step 5: Commit** — message `fix(model-support): close walk-test gaps`
      with each fix and the final read counts per walk test in the body.

---

### Task 10: open the PR

- [ ] **Step 1: Full checks**

```bash
cd /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only origin/main...HEAD) </dev/null 2>&1 | tail -n 5 && VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill run pytest /workspaces/teamster/.worktrees/GabyRangelB/feat/claude-document-the-model-skill/tests/skills -q 2>&1 | tail -n 5
```

Expected: `No issues`; `7 passed`.

- [ ] **Step 2: Push** — `git -C <worktree> push`.

- [ ] **Step 3: Open a draft PR** with `mcp__github__create_pull_request`, body
      from `.github/pull_request_template.md`: plain-language Summary; Reviewer
      Notes naming the judgment calls (Python link checker instead of `.sh`,
      matching all 10 existing skill scripts; `tests/skills/` is the first test
      coverage for skill scripts and runs locally only, since `pytest.yaml`
      covers `tests/launch/**` alone; five-model inline threshold; QA's Tableau
      opt-in); `Refs #5434` (not `Closes`: acceptance needs the athletic
      eligibility run); a "For Claude" fold-out with the RED baseline summary
      and walk-test read counts. Draft until the athletic eligibility PR's real
      run passes and its fixes land here. End the body with the Claude Code
      attribution line.

- [ ] **Step 4: Verify** the returned title, body, and draft state match intent.
