# Academic & Gradebook Health Suite Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Landing Page` dashboard to the Academic & Gradebook Health
Suite workbook as its first tab and default view, built as `.twb` XML, without
changing any byte of the five existing dashboards.

**Architecture:** One Python edit script clones existing worksheets into `LP - `
prefixed copies, appends one dashboard, one dashboard window, one hidden window
per new sheet, nine `nav-action` elements, three URL actions and two
datasource-level calculations, then writes the file back. Every insertion is
anchored and asserted to match exactly once. A new checker, `check_additive.py`,
strips every addition back out and requires the remainder to be byte-identical
to the base. The two existing checkers, `repack.py` and the credentialed pytest
template do the rest, and the review copy publishes to a temp project only.

**Tech Stack:** Tableau `.twb` XML (source-build 2025.1.9), Python 3 under
`uv run`, `tableauserverclient` under pytest, `docs/tableau-xml/scripts/`,
Pillow for crops, trunk for lint.

**Spec:**
`docs/superpowers/specs/2026-09-10-academic-health-launch-page-design.md`
**Issue:** [#5235](https://github.com/TEAMSchools/teamster/issues/5235)

## Global Constraints

- The user runs the build only after an explicit go command. Nothing in this
  plan publishes to Production. The review target is `GPA-monitor-temp`,
  `c74d8e08-b856-4430-a759-ebacb061e376`, unless the user names another
  non-production project before Task 8.
- Worktree:
  `/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-academic-health-launch-page`.
  Every repo file path below is relative to it. Every `git` call is
  `git -C <worktree>`. Scratch files live in
  `/workspaces/teamster/.claude/scratch/tableau/lp/`, referred to as `$lp`
  below; it is gitignored.
- Workbook: `Academic & Gradebook Health Suite`, luid
  `b3c14d67-3130-46ac-82a0-0637a5cc2da5`. Dashboard name `Landing Page`. Every
  new worksheet name starts with `LP - `.
- The five existing dashboards, their worksheets, parameters, actions and
  windows are not edited. New URL actions are added; the nine existing
  `GPA Roster` actions are not touched.
- Read and write the `.twb` with `encoding="utf-8", newline=""`. The file is
  CRLF. Every substitution anchors on a unique string and asserts one match
  before and the expected count after. Parse with `ET.fromstring` before
  writing, for well-formedness only; never write ElementTree's output.
- Inside `<formatted-text>` a line break is its own run, `<run>Æ&#10;</run>`,
  byte-exact. Field tokens in a mark label go in `<![CDATA[<[ds].[inst]>]]>`. A
  parameter token goes only in a worksheet `<title>`, never in a mark label or a
  dashboard text zone.
- Every new worksheet keeps the clone's `<simple-id>` structure but gets a new
  uuid, keeps `<aggregation value='true' />`, and drops any
  `<repository-location>` so it can carry `<layout-options>`.
- Zone units: 1 px wide = 100000 / 1366 = 73.206 units, 1 px tall = 100000 /
  1500 = 66.667 units. `fixed-size` is in pixels along the parent's flow axis
  and never exceeds the zone's stored pixel size.
- Credentialed steps run as a throwaway `tests/test_zz_lp_*.py` under
  `uv run pytest -s`, copied from `docs/tableau-xml/scripts/tsc_session.py`, and
  are deleted after. Exit codes are read through a redirect, never a pipe.
- `uv` is at `~/.local/bin/uv`; it is not on `$PATH` in this Codespace.
- Lint before pushing:
  `cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- Logging, every task: append every lesson, trap, surprise and dead end to
  `docs/tableau-xml/lessons/2026-09-10-landing-page/lessons.md` in the entry
  format already there (heading, Verified or Inferred mark, what was observed,
  what to do instead), and copy every Python file the task writes, including
  throwaway `tests/test_zz_*.py` files before they are deleted and every scratch
  script under `$lp/`, into
  `docs/tableau-xml/lessons/2026-09-10-landing-page/scripts/`. Both are
  committed with the task. The user uses this log to improve the skill.
- The default view is the dashboard window carrying `maximized='true'` in
  `<windows>`, not the first window. Making `Landing Page` the default means
  removing that attribute from the `Gradebook Teacher View` window and setting
  it on the new window. That single attribute is the one sanctioned edit to an
  existing element; `check_additive.py` normalizes it out before comparing, and
  a dedicated assertion checks exactly one maximized window exists and it is
  `Landing Page`.

---

### Task 1: Pull the fresh base and prove the checkers pass on it

**Files:**

- Create: `tests/test_zz_lp_pull.py` (throwaway, deleted at the end of the task)
- Create: `$lp/base.twbx`, `$lp/base.twb`, `$lp/base-meta.txt`

**Interfaces:**

- Produces: `$lp/base.twb` (the untouched reference every later task diffs
  against), `$lp/base.twbx` (the repack donor), `$lp/base-meta.txt` (revision,
  `updated_at`, `show_tabs`, live view names).

- [ ] **Step 1: Write the pull test**

```python
"""Throwaway: pull the suite workbook, record its state, unpack the .twb."""

import os
import re
import zipfile
from pathlib import Path

import tableauserverclient as tsc

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
LP.mkdir(parents=True, exist_ok=True)
LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"
PREVIOUS = Path("/workspaces/teamster/.claude/scratch/tableau/landing/aghs.twb")


def test_pull() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(LUID)
        server.workbooks.populate_views(wb)
        server.workbooks.populate_revisions(wb)
        revision = max(int(r.revision_number) for r in wb.revisions)
        got = Path(server.workbooks.download(LUID, filepath=str(LP / "base"), include_extract=True))
    if got != LP / "base.twbx":
        got.replace(LP / "base.twbx")
    if (LP / "base.twbx").stat().st_size < 20_000_000:
        raise RuntimeError("extract missing from download")
    with zipfile.ZipFile(LP / "base.twbx") as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (LP / "base.twb").write_bytes(z.read(name))
    meta = [
        f"revision={revision}",
        f"updated_at={wb.updated_at}",
        f"show_tabs={wb.show_tabs}",
        f"default_view_id={wb.default_view_id}",
        "live_views=" + "|".join(v.name for v in wb.views),
    ]
    (LP / "base-meta.txt").write_text("\n".join(meta) + "\n")
    print("\n".join(meta))

    new = (LP / "base.twb").read_text(encoding="utf-8", newline="")
    old = PREVIOUS.read_text(encoding="utf-8", newline="")
    for label, pat in (
        ("worksheets", r"<worksheet name='([^']*)'"),
        ("dashboards", r"<dashboard [^>]*name='([^']*)'"),
        ("parameters", r"name='(\[Parameter [^\]]*\])'"),
        ("actions", r"<(?:nav-)?action caption='([^']*)'"),
    ):
        a, b = set(re.findall(pat, old)), set(re.findall(pat, new))
        print(f"DIFF {label}: removed={sorted(a - b)} added={sorted(b - a)}")
```

- [ ] **Step 2: Run it and read the diff lines**

Run:
`cd /workspaces/teamster && ~/.local/bin/uv run pytest tests/test_zz_lp_pull.py -s -q 2>&1 | tail -20`

Expected: `1 passed`, `base.twbx` over 20 MB, and four `DIFF` lines. If any
`removed=` or `added=` list is non-empty, stop and report it to the user before
Task 2: the owner republished after the spec was written, and the change has to
be understood first. Empty lists mean the 2026-09-10 08:17 base is still live.

- [ ] **Step 3: Baseline the checkers against the untouched base**

```bash
cd /workspaces/teamster && lp=.claude/scratch/tableau/lp
~/.local/bin/uv run python docs/tableau-xml/scripts/check_twb.py $lp/base.twb --ref $lp/base.twb >$lp/o-twb-base.txt 2>&1; echo "check_twb rc=$?"
for d in "Academic Health Home" "Academic Health Schools" "Cumulative GPA Monitor" "Gradebook School Rollup" "Gradebook Teacher View"; do
  ~/.local/bin/uv run python docs/tableau-xml/scripts/check_geometry.py $lp/base.twb "$d" --baseline $lp/base.twb >"$lp/o-geo-base-${d// /_}.txt" 2>&1; echo "geometry [$d] rc=$?"
done
```

Expected: every `rc=0`. A non-zero here is a checker bug against this file, not
a workbook bug; record it and continue, because the same failure will appear on
the edited file and must be discounted there.

- [ ] **Step 4: Delete the throwaway test**

```bash
rm -f /workspaces/teamster/tests/test_zz_lp_pull.py
```

No commit: nothing under the worktree changed.

---

### Task 2: Write `check_additive.py` and prove it has teeth

**Files:**

- Create: `docs/tableau-xml/scripts/check_additive.py`
- Modify: `docs/tableau-xml/scripts/README.md` (add one section)

**Interfaces:**

- Produces:
  `check_additive.py <edited.twb> <base.twb> --sheet-prefix "LP - " --dashboard "Landing Page" --calc-prefix "Calculation_76" --action-prefix "LP_"`.
  Exit 0 when stripping the named additions from the edited file leaves it
  byte-identical to the base. Exit 1 with a unified diff excerpt otherwise.

- [ ] **Step 1: Write the checker**

```python
"""check_additive.py: prove an edit only ADDED things.

Strips every addition the edit is allowed to make, then requires the remainder
to be byte-identical to the base. Text surgery, not ElementTree, so an
unmutated file round-trips byte-exact.

    uv run python check_additive.py edited.twb base.twb \
        --sheet-prefix "LP - " --dashboard "Landing Page" \
        --calc-prefix Calculation_76 --action-prefix LP_
"""

import argparse
import difflib
import re
import sys


def strip_elements(text: str, pattern: str) -> tuple[str, int]:
    """Remove whole elements matching a regex; the regex must consume the
    element from its leading indentation through its trailing newline."""
    new, n = re.subn(pattern, "", text, flags=re.S)
    return new, n


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("edited")
    p.add_argument("base")
    p.add_argument("--sheet-prefix", required=True)
    p.add_argument("--dashboard", required=True)
    p.add_argument("--calc-prefix", required=True)
    p.add_argument("--action-prefix", required=True)
    a = p.parse_args()

    edited = open(a.edited, encoding="utf-8", newline="").read()
    base = open(a.base, encoding="utf-8", newline="").read()
    sp = re.escape(a.sheet_prefix)
    db = re.escape(a.dashboard)
    cp = re.escape(a.calc_prefix)
    ap = re.escape(a.action_prefix)

    removed = {}
    # order matters only for readability; each pattern is independent
    patterns = {
        "worksheets": rf"[ \t]*<worksheet name='{sp}[^']*'>.*?</worksheet>\r?\n",
        "dashboard": rf"[ \t]*<dashboard [^>]*name='{db}'>.*?</dashboard>\r?\n",
        "dashboard-window": rf"[ \t]*<window class='dashboard'[^>]*name='{db}'[^>]*>.*?</window>\r?\n",
        "sheet-windows": rf"[ \t]*<window class='worksheet'[^>]*name='{sp}[^']*'[^>]*>.*?</window>\r?\n",
        "nav-actions": rf"[ \t]*<nav-action [^>]*name='\[{ap}[^\]]*\]'>.*?</nav-action>\r?\n",
        "url-actions": rf"[ \t]*<action [^>]*name='\[{ap}[^\]]*\]'>.*?</action>\r?\n",
        "calcs": rf"[ \t]*<column [^>]*name='\[{cp}\d+\]'[^>]*>.*?</column>\r?\n",
    }
    for label, pat in patterns.items():
        edited, n = strip_elements(edited, pat)
        removed[label] = n

    # the one sanctioned edit to an existing element: the default-view marker
    # moves between dashboard windows. Normalize it out on both sides, and
    # require that the edited file still has exactly one.
    if edited.count(" maximized='true'") not in (0, 1) or base.count(" maximized='true'") != 1:
        print("FAIL: expected exactly one maximized window in each file")
        return 1
    edited = edited.replace(" maximized='true'", "")
    base = base.replace(" maximized='true'", "")

    print("stripped:", removed)
    if edited == base:
        print("OK: remainder is byte-identical to base")
        return 0
    diff = difflib.unified_diff(
        base.splitlines(keepends=True), edited.splitlines(keepends=True),
        "base", "edited-minus-additions", n=2,
    )
    out = list(diff)
    print(f"FAIL: {len(out)} diff lines; first 60:")
    sys.stdout.writelines(out[:60])
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it base-against-base and confirm it passes trivially**

```bash
cd /workspaces/teamster && lp=.claude/scratch/tableau/lp
~/.local/bin/uv run python docs/tableau-xml/scripts/check_additive.py $lp/base.twb $lp/base.twb --sheet-prefix "LP - " --dashboard "Landing Page" --calc-prefix Calculation_76 --action-prefix LP_ >$lp/o-add-0.txt 2>&1; echo "rc=$?"; tail -2 $lp/o-add-0.txt
```

Expected: `rc=0`, every `stripped` count `0`.

- [ ] **Step 3: Build a mutant that touches an existing dashboard and confirm
      the checker fails**

```bash
cd /workspaces/teamster && lp=.claude/scratch/tableau/lp
~/.local/bin/uv run python docs/tableau-xml/scripts/mutate.py $lp/base.twb $lp/ctrl.twb "Gradebook School Rollup" control; cmp $lp/base.twb $lp/ctrl.twb && echo CONTROL_OK
~/.local/bin/uv run python docs/tableau-xml/scripts/mutate.py $lp/base.twb $lp/mut-1.twb "Gradebook School Rollup" set-attr 10 show-title true
~/.local/bin/uv run python docs/tableau-xml/scripts/check_additive.py $lp/mut-1.twb $lp/base.twb --sheet-prefix "LP - " --dashboard "Landing Page" --calc-prefix Calculation_76 --action-prefix LP_ >$lp/o-add-mut.txt 2>&1; echo "rc=$?"
```

Expected: `CONTROL_OK`, then `rc=1` on the mutant with a diff naming zone
`id='10'`. If `rc=0`, the checker is blind and must be fixed before anything
else.

- [ ] **Step 4: Document it in the scripts README**

Append after the `repack.py` section of `docs/tableau-xml/scripts/README.md`:

````markdown
## `check_additive.py`

For an edit whose contract is "additive only". Strips every element the edit was
allowed to add (worksheets by name prefix, one dashboard and its window, hidden
windows by the same prefix, `nav-action` and `action` elements by name prefix,
datasource columns by calculation-name prefix) and requires the remainder to be
byte-identical to the base.

```bash
uv run python check_additive.py <edited.twb> <base.twb> --sheet-prefix "LP - " \
  --dashboard "Landing Page" --calc-prefix Calculation_76 --action-prefix LP_
```

Prove it has teeth the same way as the others: `mutate.py set-attr` on any zone
of an existing dashboard must make it fail.
````

- [ ] **Step 5: Lint and commit**

```bash
wt=/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-academic-health-launch-page
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/tableau-xml/scripts/check_additive.py docs/tableau-xml/scripts/README.md </dev/null
git -C $wt add docs/tableau-xml/scripts/check_additive.py docs/tableau-xml/scripts/README.md
git -C $wt commit -m "feat(tableau-xml): add check_additive.py for additive-only workbook edits

Refs #5235

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The edit script skeleton, the two goal calculations, and the first assertion

**Files:**

- Create: `$lp/build_lp.py` (scratch; the whole build lives here and grows task
  by task)
- Create: `$lp/assert_lp.py` (scratch; the assertion script, grows with it)
- Produces: `$lp/out.twb`

**Interfaces:**

- Produces: `build_lp.py` helpers used by every later task:
  `sub_once(text, anchor, replacement) -> str` (asserts exactly one match),
  `insert_before(text, anchor, block) -> str`,
  `insert_after(text, anchor, block) -> str`, `new_uuid() -> str` (uppercase,
  braced), `crlf(block: str) -> str` (converts a Python triple-quoted block to
  CRLF and strips the leading newline).
- Produces: the two calculation names `[Calculation_7600000000000000001]`
  (caption `LP Students still needed (region)`) and
  `[Calculation_7600000000000000002]` (caption `LP Gap to goal (region)`) on
  datasource `federated.0n798br073i5kb170j6l90uiv50a`.

- [ ] **Step 1: Confirm the new names are unused**

```bash
grep -c "Calculation_76" /workspaces/teamster/.claude/scratch/tableau/lp/base.twb
```

Expected: `0`. If not, pick the next free prefix and use it everywhere the plan
says `Calculation_76`, including the `--calc-prefix` argument.

- [ ] **Step 2: Write the assertion for this task first**

```python
"""assert_lp.py: assertions on out.twb, one function per task, all run every time."""

import re
import sys

OUT = "/workspaces/teamster/.claude/scratch/tableau/lp/out.twb"
GOAL_DS = "federated.0n798br073i5kb170j6l90uiv50a"


def load() -> str:
    return open(OUT, encoding="utf-8", newline="").read()


def count(text: str, pat: str) -> int:
    return len(re.findall(pat, text, flags=re.S))


def task3(t: str) -> None:
    ds = re.search(rf"<datasource caption='[^']*' inline='true' name='{GOAL_DS}'.*?</datasource>", t, re.S).group(0)
    for name, cap in (
        ("Calculation_7600000000000000001", "LP Students still needed \\(region\\)"),
        ("Calculation_7600000000000000002", "LP Gap to goal \\(region\\)"),
    ):
        assert count(ds, rf"<column caption='{cap}' [^>]*name='\[{name}\]'") == 1, name
        assert count(t, rf"\[{name}\]") >= 1
    assert "gpa_goal_proportion_region" in ds
    assert "Parameter 3" not in re.search(r"name='\[Calculation_7600000000000000001\]'.*?</column>", ds, re.S).group(0)


CHECKS = [task3]

if __name__ == "__main__":
    text = load()
    failed = 0
    for fn in CHECKS:
        try:
            fn(text)
            print(f"PASS {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc!r}")
    sys.exit(1 if failed else 0)
```

- [ ] **Step 3: Run the assertion against a copy of the base and confirm it
      fails**

```bash
lp=/workspaces/teamster/.claude/scratch/tableau/lp; cp $lp/base.twb $lp/out.twb
cd /workspaces/teamster && ~/.local/bin/uv run python $lp/assert_lp.py >$lp/o-assert.txt 2>&1; echo "rc=$?"; cat $lp/o-assert.txt
```

Expected: `rc=1`, `FAIL task3`.

- [ ] **Step 4: Write the build script skeleton with the calc insertion**

```python
"""build_lp.py: additive edit of the suite workbook. Run from the main checkout:
    ~/.local/bin/uv run python /workspaces/teamster/.claude/scratch/tableau/lp/build_lp.py
Reads base.twb, writes out.twb. Every step asserts its anchors."""

import re
import uuid
import xml.etree.ElementTree as ET  # trunk-ignore(bandit/B405): parse-only well-formedness check on a file we wrote
from pathlib import Path

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
BASE = LP / "base.twb"
OUT = LP / "out.twb"

GOAL_DS = "federated.0n798br073i5kb170j6l90uiv50a"   # rpt_tableau__gpa_goal_progress
GRADES_DS = "federated.1ikycy21f3ow4k1eazzbx1iah2yl"  # rpt_tableau__student_course_grades+
GB_DS = "federated.16ubt9s0rwp4cw14hwm3e1xmc56p"      # rpt_tableau__gradebook_audit


def crlf(block: str) -> str:
    """Triple-quoted Python block -> CRLF text, leading newline dropped."""
    return block.lstrip("\n").replace("\r\n", "\n").replace("\n", "\r\n")


def new_uuid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def sub_once(text: str, anchor: str, replacement: str) -> str:
    n = text.count(anchor)
    if n != 1:
        raise RuntimeError(f"anchor matched {n} times, expected 1: {anchor[:80]!r}")
    return text.replace(anchor, replacement)


def insert_before(text: str, anchor: str, block: str) -> str:
    return sub_once(text, anchor, block + anchor)


def insert_after(text: str, anchor: str, block: str) -> str:
    return sub_once(text, anchor, anchor + block)


def element(text: str, open_pat: str, close_tag: str) -> str:
    """Return the first element whose opening tag matches open_pat (regex)."""
    m = re.search(open_pat, text)
    if not m:
        raise RuntimeError(f"no element for {open_pat!r}")
    end = text.index(close_tag, m.start()) + len(close_tag)
    return text[m.start():end]


# ---------------------------------------------------------------- task 3
def add_goal_calcs(t: str) -> str:
    """Two region-goal variants of the existing goal pair, on the goals source.
    The originals read the org or region goal by p_Region; these read the
    region goal only, so a region row compares against its own goal."""
    anchor = ("      <column caption='Gap to goal (pts)' datatype='real' "
              "name='[Calculation_3466859908724272046]' role='measure' type='quantitative'>")
    block = crlf("""
      <column caption='LP Students still needed (region)' datatype='real' name='[Calculation_7600000000000000001]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='// LP copy of [Students still needed] with the p_Region branch removed&#10;IF [Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10;   &gt;= AVG([gpa_goal_proportion_region])&#10;THEN 0&#10;ELSE ROUND(AVG([gpa_goal_proportion_region]) * [Calculation_4693780698737655073])&#10;     - [Calculation_9485136151529756033]&#10;END' />
      </column>
      <column caption='LP Gap to goal (region)' datatype='real' name='[Calculation_7600000000000000002]' role='measure' type='quantitative'>
        <calculation class='tableau' formula='// LP copy of [Gap to goal (pts)] with the p_Region branch removed&#10;([Calculation_9485136151529756033] / [Calculation_4693780698737655073]&#10; - AVG([gpa_goal_proportion_region])) * 100' />
      </column>
""")
    return insert_before(t, anchor, block)


STEPS = [add_goal_calcs]


def main() -> None:
    t = BASE.read_text(encoding="utf-8", newline="")
    if "\r\n" not in t:
        raise RuntimeError("base is not CRLF; stop")
    for step in STEPS:
        before = len(t)
        t = step(t)
        print(f"{step.__name__}: +{len(t) - before} bytes")
    ET.fromstring(t.encode("utf-8"))  # well-formed or raise
    OUT.write_text(t, encoding="utf-8", newline="")
    print(f"wrote {OUT} ({len(t)} chars)")


if __name__ == "__main__":
    main()
```

The `Gap to goal (pts)` column sits inside the goals datasource's top-level
`<column>` list (line 1300 area of the base). The anchor includes its exact
attribute string, so it cannot match the worksheet-level copies, which carry
different indentation.

- [ ] **Step 5: Run the build, then the assertion, then check_additive**

```bash
lp=/workspaces/teamster/.claude/scratch/tableau/lp; cd /workspaces/teamster
~/.local/bin/uv run python $lp/build_lp.py >$lp/o-build.txt 2>&1; echo "build rc=$?"; tail -3 $lp/o-build.txt
~/.local/bin/uv run python $lp/assert_lp.py >$lp/o-assert.txt 2>&1; echo "assert rc=$?"; cat $lp/o-assert.txt
~/.local/bin/uv run python docs/tableau-xml/scripts/check_additive.py $lp/out.twb $lp/base.twb --sheet-prefix "LP - " --dashboard "Landing Page" --calc-prefix Calculation_76 --action-prefix LP_ >$lp/o-add.txt 2>&1; echo "additive rc=$?"
~/.local/bin/uv run python docs/tableau-xml/scripts/check_twb.py $lp/out.twb --ref $lp/base.twb >$lp/o-twb.txt 2>&1; echo "check_twb rc=$?"
```

Expected: all four `rc=0`, `PASS task3`, `stripped: {... 'calcs': 2 ...}`.

No commit: scratch only.

---

### Task 4: Clone the title sheet and the four network tiles

**Files:**

- Modify: `$lp/build_lp.py` (add `clone_worksheet`, `add_window`, the title step
  and the four tile steps)
- Modify: `$lp/assert_lp.py` (add `task4`)

**Interfaces:**

- Produces: `clone_worksheet(t, src_name, new_name, edits) -> str` where `edits`
  is a list of `(anchor, replacement)` pairs applied inside the clone only, each
  asserted to match once inside the clone.
- Produces: `add_window(t, sheet_name) -> str` which appends
  `<window class='worksheet' hidden='true' name='...'>` with a fresh uuid at the
  end of `<windows>`.
- Produces worksheets `LP - Title`, `LP - Tile Y1 GPA`,
  `LP - Tile Course Failures`, `LP - Tile Cumulative GPA`,
  `LP - Tile Gradebook Health`.

- [ ] **Step 1: Add the assertion**

```python
def task4(t: str) -> None:
    for name in ("LP - Title", "LP - Tile Y1 GPA", "LP - Tile Course Failures",
                 "LP - Tile Cumulative GPA", "LP - Tile Gradebook Health"):
        ws = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
        assert ws, f"missing worksheet {name}"
        w = ws.group(0)
        assert "<repository-location" not in w, name
        assert "<aggregation value='true' />" in w, name
        assert count(w, r"<simple-id uuid=") == 1, name
        assert count(t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'") == 1, name
    y1 = re.search(r"<worksheet name='LP - Tile Y1 GPA'>.*?</worksheet>", t, re.S).group(0)
    assert "Calculation_4005670422414364681" not in y1   # Region Filter gone
    assert "[none:hos:nk]" not in y1 and "[none:school_level:nk]" not in y1
    assert "<layout-options>" in y1 and "[Parameters].[Parameter 4]" in y1  # MP in title
    assert "<Data Update Time>" in y1
    gb = re.search(r"<worksheet name='LP - Tile Gradebook Health'>.*?</worksheet>", t, re.S).group(0)
    assert "[none:region:nk]' filter-group" not in gb and "[none:school:nk]' filter-group" not in gb
    assert "[Parameters].[Parameter 1 1]" in re.search(r"<layout-options>.*?</layout-options>", gb, re.S).group(0)
    title = re.search(r"<worksheet name='LP - Title'>.*?</worksheet>", t, re.S).group(0)
    assert "Landing Page" in title and "| Home" not in title
    # uuids are unique across the file
    ids = re.findall(r"<simple-id uuid='([^']*)'", t)
    assert len(ids) == len(set(ids)), "duplicate simple-id"
```

Add `task4` to `CHECKS`. Run `assert_lp.py` against the current `out.twb`:
expected `FAIL task4`.

- [ ] **Step 2: Add the clone and window helpers to build_lp.py**

```python
# ---------------------------------------------------------------- helpers, task 4
def worksheet_block(t: str, name: str) -> str:
    return element(t, rf"    <worksheet name='{re.escape(name)}'>", "    </worksheet>\r\n")


def clone_worksheet(t: str, src_name: str, new_name: str, edits: list[tuple[str, str]]) -> str:
    src = worksheet_block(t, src_name)
    new = src.replace(f"<worksheet name='{src_name}'>", f"<worksheet name='{new_name}'>", 1)
    # drop repository-location so <layout-options> is legal
    new = re.sub(r"      <repository-location [^>]*/>\r\n", "", new, count=1)
    # fresh simple-id
    new = re.sub(r"<simple-id uuid='[^']*' />", f"<simple-id uuid='{new_uuid()}' />", new, count=1)
    for anchor, repl in edits:
        n = new.count(anchor)
        if n != 1:
            raise RuntimeError(f"[{new_name}] edit anchor matched {n}: {anchor[:80]!r}")
        new = new.replace(anchor, repl)
    # insert right after the source worksheet, so <worksheets> stays grouped
    return insert_after(t, src, new)


def add_window(t: str, sheet_name: str) -> str:
    block = crlf(f"""
    <window class='worksheet' hidden='true' name='{sheet_name}'>
      <cards>
        <edge name='left'>
          <strip size='160'>
            <card type='pages' />
            <card type='filters' />
            <card type='marks' />
          </strip>
        </edge>
      </cards>
      <simple-id uuid='{new_uuid()}' />
    </window>
""")
    return insert_before(t, "  </windows>\r\n", block)


def drop_filter(ws_edits: list, ds: str, inst: str) -> None:
    """Queue removal of one categorical filter and its slice for a clone.
    The filter element form varies (filter-group attr or not, one-line
    groupfilter or a nested union), so this matches by regex at apply time."""
    ws_edits.append(("__DROP_FILTER__", f"{ds}|{inst}"))


def apply_drop_filters(block: str, drops: list[tuple[str, str]]) -> str:
    for ds, inst in drops:
        pat = (rf"          <filter class='categorical' column='\[{re.escape(ds)}\]\.\[{re.escape(inst)}\]'[^>]*>"
               rf".*?</filter>\r\n")
        block, n = re.subn(pat, "", block, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"filter not found: {ds} {inst}")
        slice_line = f"            <column>[{ds}].[{inst}]</column>\r\n"
        if block.count(slice_line) != 1:
            raise RuntimeError(f"slice not found once: {inst}")
        block = block.replace(slice_line, "")
    return block
```

Because `drop_filter` needs regex rather than a literal anchor, extend
`clone_worksheet` so that edits whose anchor is `"__DROP_FILTER__"` are
collected and passed to `apply_drop_filters(new, drops)` before the literal
edits run. Keep the one-match assertion on every literal edit.

- [ ] **Step 3: Add the title step**

```python
# ---------------------------------------------------------------- task 4: title
def add_title(t: str) -> str:
    t = clone_worksheet(t, "Y1 Landing - Title", "LP - Title", [
        ("<run bold='true' fontalignment='0' fontsize='16'>Academic Health</run>",
         "<run bold='true' fontalignment='0' fontsize='16'>Academic &amp; Gradebook Health</run>"),
        ("<run fontalignment='0' fontsize='16'> | Home</run>",
         "<run fontalignment='0' fontsize='16'> | Landing Page</run>"),
        ("<![CDATA[This tab shows the change of Y1 GPA throughout each of the terms . Y1 values are weighted. This tab last updated on <Data Update Time> PST.]]>",
         "Middle and high schools in Camden, Newark and Paterson. One place to see the headline numbers and find the right tab."),
    ])
    return add_window(t, "LP - Title")
```

- [ ] **Step 4: Add the four tile steps**

Each tile is a clone of its BAN sheet with the region restriction removed, a
`<layout-options>` block inserted before `<table>` carrying the title (with the
parameter token) and the caption (with the data update time), and the mark
label's first line replaced by the tile name. The `Y1 Landing` BAN sheets have
no `<layout-options>`, so the block is inserted at the very start of the
element.

```python
TITLE_STYLE = "fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'"


def layout_options(title_runs: str, caption: str) -> str:
    return crlf(f"""
      <layout-options>
        <title>
          <formatted-text>
{title_runs}
          </formatted-text>
        </title>
        <caption>
          <formatted-text>
            <run fontcolor='#8c8c8c' fontsize='8' italic='true'><![CDATA[{caption} Updated <Data Update Time>.]]></run>
          </formatted-text>
        </caption>
      </layout-options>
""")


def add_tile_y1(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Weighted Y1 GPA · marking period <[Parameters].[Parameter 4]> · middle and high schools]]></run>",
        "Students with a Y1 GPA this marking period.")
    edits = [
        ("<worksheet name='LP - Tile Y1 GPA'>\r\n      <table>", "<worksheet name='LP - Tile Y1 GPA'>\r\n" + lo + "      <table>"),
        ("<run fontname='Tableau Regular' fontsize='10'>% At/Above 3.0</run>",
         "<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 weighted Y1 GPA</run>"),
    ]
    drop_filter(edits, GRADES_DS, "none:Calculation_4005670422414364681:nk")  # Region Filter
    drop_filter(edits, GRADES_DS, "none:hos:nk")
    drop_filter(edits, GRADES_DS, "none:school_level:nk")
    t = clone_worksheet(t, "Y1 Landing - BAN Network ≥3.0", "LP - Tile Y1 GPA", edits)
    return add_window(t, "LP - Tile Y1 GPA")


def add_tile_failures(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Y1 grades · marking period <[Parameters].[Parameter 4]> · middle and high schools]]></run>",
        "Students with a Y1 failing-course count.")
    edits = [
        ("<worksheet name='LP - Tile Course Failures'>\r\n      <table>", "<worksheet name='LP - Tile Course Failures'>\r\n" + lo + "      <table>"),
        ("<run fontname='Tableau Regular' fontsize='10'>% Failing 2+</run>",
         "<run fontname='Tableau Regular' fontsize='13'>% failing 2 or more courses</run>"),
    ]
    drop_filter(edits, GRADES_DS, "none:Calculation_4005670422414364681:nk")
    drop_filter(edits, GRADES_DS, "none:hos:nk")
    drop_filter(edits, GRADES_DS, "none:school_level:nk")
    t = clone_worksheet(t, "Y1 Landing - BAN Network Failing ≥2", "LP - Tile Course Failures", edits)
    return add_window(t, "LP - Tile Course Failures")


def add_tile_cumulative(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Unweighted cumulative GPA · <[Parameters].[Parameter 11]> · high schools only]]></run>",
        "HS students with a cumulative GPA.")
    edits = [
        ("<worksheet name='LP - Tile Cumulative GPA'>\r\n      <table>", "<worksheet name='LP - Tile Cumulative GPA'>\r\n" + lo + "      <table>"),
        ("<run fontname='Tableau Regular' fontsize='13'>At 3.0+ cumulative</run>",
         "<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 unweighted cumulative GPA</run>"),
    ]
    drop_filter(edits, GOAL_DS, "none:Calculation_5742832717263693013:nk")  # Region filter (goals source)
    t = clone_worksheet(t, "GPA - BAN % 3.0+", "LP - Tile Cumulative GPA", edits)
    return add_window(t, "LP - Tile Cumulative GPA")


def add_tile_gradebook(t: str) -> str:
    lo = layout_options(
        f"            <run {TITLE_STYLE}><![CDATA[Health basis: <[Parameters].[Parameter 1 1]> · current quarter · middle and high schools]]></run>",
        "Teachers with at least one audited section this quarter.")
    edits = [
        ("<worksheet name='LP - Tile Gradebook Health'>\r\n      <table>", "<worksheet name='LP - Tile Gradebook Health'>\r\n" + lo + "      <table>"),
        ("<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='16'>Network</run>",
         "<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='13'>% of teachers with a healthy gradebook</run>"),
    ]
    drop_filter(edits, GB_DS, "none:region:nk")
    drop_filter(edits, GB_DS, "none:school:nk")
    drop_filter(edits, GB_DS, "none:school_level:nk")
    t = clone_worksheet(t, "BAN Network", "LP - Tile Gradebook Health", edits)
    return add_window(t, "LP - Tile Gradebook Health")


STEPS = [add_goal_calcs, add_title, add_tile_y1, add_tile_failures, add_tile_cumulative, add_tile_gradebook]
```

Before running, confirm each mark-label anchor string is byte-exact by grepping
the base for it. The cumulative tile's first label run and the Region filter
calc name on the goals source must be read from `GPA - BAN % 3.0+` in `base.twb`
(the plan quotes what the 2026-09-10 base held; a republish could have changed
them). The cumulative tile's students-still-needed and gap lines are not on
`GPA - BAN % 3.0+`; they stay in the tile's tooltip via the sheet's existing
tooltip, and the network value of `Students still needed` is shown by adding a
second text run that references
`[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_5262281088199017638:qk]`
only if that column-instance already exists in the clone's
`datasource-dependencies`. If it does not, add the `<column>` and
`<column-instance>` lines copied verbatim from `GPA - BAN Students needed`
before referencing it, and add the `<text column=...>` encoding line. Assert all
three insertions match once.

- [ ] **Step 5: Run build, assert, checkers**

Same four commands as Task 3 Step 5. Expected: all `rc=0`, `PASS task3`,
`PASS task4`, `stripped` shows `worksheets: 5`, `sheet-windows: 5`.

---

### Task 5: The region strip sheets

**Files:**

- Modify: `$lp/build_lp.py` (four strip steps)
- Modify: `$lp/assert_lp.py` (add `task5`)

**Interfaces:**

- Produces worksheets `LP - Strip Y1 GPA`, `LP - Strip Course Failures`,
  `LP - Strip Cumulative GPA`, `LP - Strip Gradebook Health`, each with `region`
  on rows, sorted ascending, and a two-line label: value, then the one-week
  delta where the source has one.

- [ ] **Step 1: Add the assertion**

```python
def task5(t: str) -> None:
    for name, ds in (("LP - Strip Y1 GPA", GRADES_DS), ("LP - Strip Course Failures", GRADES_DS),
                     ("LP - Strip Cumulative GPA", GOAL_DS), ("LP - Strip Gradebook Health", GB_DS)):
        w = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
        assert w, name
        w = w.group(0)
        assert f"<rows>[{ds}].[none:region:nk]</rows>" in w, name
        assert f"name='[none:region:nk]'" in w, name
        assert count(t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'") == 1
    cum = re.search(r"<worksheet name='LP - Strip Cumulative GPA'>.*?</worksheet>", t, re.S).group(0)
    assert "Calculation_7600000000000000001" in cum   # region-goal variant, not the p_Region one
```

Add to `CHECKS`; run; expected `FAIL task5`.

- [ ] **Step 2: Add the strip steps**

Each strip sheet is a clone of the matching tile (so the region filters are
already gone and the layout-options are already present), with `<rows />`
replaced by the region instance, the title replaced by a short header, the
caption removed, and the label cut to two lines.

```python
def strip_from_tile(t: str, tile: str, name: str, ds: str, label_edits: list[tuple[str, str]], extra: list[tuple[str, str]] | None = None) -> str:
    edits = [
        ("        <rows />", f"        <rows>[{ds}].[none:region:nk]</rows>"),
        *label_edits,
        *(extra or []),
    ]
    t = clone_worksheet(t, tile, name, edits)
    # the region column-instance must exist in the clone; the tiles that had
    # a region filter kept the instance line even though the filter is gone.
    w = worksheet_block(t, name)
    if f"name='[none:region:nk]'" not in w:
        inst = (f"            <column-instance column='[region]' derivation='None' name='[none:region:nk]' pivot='key' type='nominal' />\r\n")
        col = "            <column caption='Region' datatype='string' name='[region]' role='dimension' type='nominal' />\r\n"
        anchor = f"          <datasource-dependencies datasource='{ds}'>\r\n"
        if w.count(anchor) != 1:
            raise RuntimeError(f"{name}: dependencies anchor")
        w2 = w.replace(anchor, anchor + col + inst)
        t = sub_once(t, w, w2)
    # strip the caption block entirely: the strip has no room for it
    w = worksheet_block(t, name)
    w2, n = re.subn(r"        <caption>.*?</caption>\r\n", "", w, count=1, flags=re.S)
    if n != 1:
        raise RuntimeError(f"{name}: caption")
    t = sub_once(t, w, w2)
    return add_window(t, name)


def add_strips(t: str) -> str:
    t = strip_from_tile(t, "LP - Tile Y1 GPA", "LP - Strip Y1 GPA", GRADES_DS, [
        ("<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 weighted Y1 GPA</run>",
         "<run fontname='Tableau Regular' fontsize='9'>Y1 GPA at or above 3.0</run>"),
    ])
    t = strip_from_tile(t, "LP - Tile Course Failures", "LP - Strip Course Failures", GRADES_DS, [
        ("<run fontname='Tableau Regular' fontsize='13'>% failing 2 or more courses</run>",
         "<run fontname='Tableau Regular' fontsize='9'>Failing 2 or more</run>"),
    ])
    t = strip_from_tile(t, "LP - Tile Cumulative GPA", "LP - Strip Cumulative GPA", GOAL_DS, [
        ("<run fontname='Tableau Regular' fontsize='13'>% at or above 3.0 unweighted cumulative GPA</run>",
         "<run fontname='Tableau Regular' fontsize='9'>Cumulative GPA at or above 3.0</run>"),
    ], extra=[
        # region-goal variant replaces the p_Region-aware one wherever the tile referenced it
        ("[usr:Calculation_5262281088199017638:qk]", "[usr:Calculation_7600000000000000001:qk]"),
    ])
    t = strip_from_tile(t, "LP - Tile Gradebook Health", "LP - Strip Gradebook Health", GB_DS, [
        ("<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='13'>% of teachers with a healthy gradebook</run>",
         "<run fontcolor='#ffffff' fontname='Tableau Medium' fontsize='9'>Healthy gradebooks</run>"),
    ])
    return t
```

The swap of `Calculation_5262281088199017638` for the region variant on the
cumulative strip only applies if Task 4 added that reference to the tile; if it
did not, drop the `extra` list and instead add the `<column>`,
`<column-instance>` and `<text column=...>` lines for
`Calculation_7600000000000000001` the same way Task 4 describes, copying the
column-instance form `[usr:Calculation_7600000000000000001:qk]`.

Add `add_strips` to `STEPS` after the tiles.

- [ ] **Step 3: Run build, assert, checkers**

Same commands. Expected: `PASS task5`, `worksheets: 9`, `sheet-windows: 9`.

---

### Task 6: Directory cards, help-guide slots, and the Miami footnote sheet

**Files:**

- Modify: `$lp/build_lp.py`
- Modify: `$lp/assert_lp.py` (add `task6`)

**Interfaces:**

- Produces worksheets `LP - Card Home`, `LP - Card Schools`,
  `LP - Card Monitor`, `LP - Card Rollup`, `LP - Card Teacher`, and
  `LP - Guide Home`, `LP - Guide Schools`, `LP - Guide Monitor`,
  `LP - Guide Rollup`, `LP - Guide Teacher`.
- The card bodies are clones of `Y1 Landing - Title`, not of
  `Sheet Card - expectations`: the Title sheet is already a static text mark
  with no filters, while the Sheet Card carries two action filters bound to the
  Teacher View that would have to be stripped. Task 10 updates the spec line.

- [ ] **Step 1: Add the assertion**

```python
CARDS = ["Home", "Schools", "Monitor", "Rollup", "Teacher"]


def task6(t: str) -> None:
    for c in CARDS:
        for kind in ("Card", "Guide"):
            name = f"LP - {kind} {c}"
            w = re.search(rf"<worksheet name='{re.escape(name)}'>.*?</worksheet>", t, re.S)
            assert w, name
            w = w.group(0)
            assert "<filter " not in w, f"{name} carries a filter"
            assert "[Parameters]" not in re.search(r"<customized-label>.*?</customized-label>", w, re.S).group(0), name
            assert count(t, rf"<window class='worksheet' hidden='true' name='{re.escape(name)}'") == 1
        g = re.search(rf"<worksheet name='LP - Guide {c}'>.*?</worksheet>", t, re.S).group(0)
        assert "Help guide: coming soon" in g
        assert "underline='true'" not in g
    schools = re.search(r"<worksheet name='LP - Card Schools'>.*?</worksheet>", t, re.S).group(0)
    assert "Shows student names" in schools
    home = re.search(r"<worksheet name='LP - Card Home'>.*?</worksheet>", t, re.S).group(0)
    assert "Shows student names" not in home
```

Add to `CHECKS`; run; expected `FAIL task6`.

- [ ] **Step 2: Card copy as data**

```python
CARD_COPY = {
    "Home": dict(
        tab="Academic Health Home",
        q="How is this year's weighted GPA and course-failure picture moving, by school, school level and subject?",
        grain="School", scope="MS and HS. Camden, Newark, Paterson",
        built="Regional and school leaders", names=False),
    "Schools": dict(
        tab="Academic Health Schools",
        q="Where is failure concentrated by teacher, and which students near the 2.0 and 3.0 cusps need office hours?",
        grain="School, teacher, student", scope="MS and HS",
        built="School leaders, APs, counselors", names=True),
    "Monitor": dict(
        tab="Cumulative GPA Monitor",
        q="Are HS cohorts on track for the unweighted cumulative GPA goal by year end, and who sits just below 3.0?",
        grain="Grade, school, student", scope="HS only. Camden and Newark",
        built="KIPP Forward, HS leaders", names=True),
    "Rollup": dict(
        tab="Gradebook School Rollup",
        q="What share of teachers have healthy gradebooks, by school and manager?",
        grain="School, manager, teacher", scope="MS and HS. Camden, Newark, Paterson MS",
        built="School leaders, instructional coaches", names=False),
    "Teacher": dict(
        tab="Gradebook Teacher View",
        q="What does my own gradebook need before the quarter closes?",
        grain="Teacher, section", scope="Your own sections",
        built="Teachers", names=False),
}
```

- [ ] **Step 3: Add the card and guide steps**

```python
BR = "                <run>Æ&#10;</run>\r\n"


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&apos;")


def card_label(c: dict) -> str:
    lines = [
        f"                <run fontcolor='#57c0e9' fontname='Tableau Semibold' fontsize='12' underline='true'>{esc(c['tab'])}</run>\r\n",
        BR,
        f"                <run fontcolor='#ffffff' fontname='Tableau Regular' fontsize='9'>{esc(c['q'])}</run>\r\n",
        BR, BR,
        f"                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Grain: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['grain'])}</run>\r\n",
        BR,
        f"                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Scope: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['scope'])}</run>\r\n",
        BR,
        f"                <run fontcolor='#b9c7e6' fontname='Tableau Semibold' fontsize='8'>Built for: </run>\r\n",
        f"                <run fontcolor='#ffffff' fontsize='8'>{esc(c['built'])}</run>\r\n",
    ]
    if c["names"]:
        lines += [BR, "                <run fontcolor='#f28e2b' fontname='Tableau Semibold' fontsize='8'>Shows student names</run>\r\n"]
    return "".join(lines).rstrip("\r\n")


def add_cards(t: str) -> str:
    old_label = ("                <run bold='true' fontalignment='0' fontsize='16'>Academic Health</run>\r\n"
                 "                <run fontalignment='0' fontsize='16'> | Home</run>")
    for key, c in CARD_COPY.items():
        name = f"LP - Card {key}"
        t = clone_worksheet(t, "Y1 Landing - Title", name, [
            (old_label, card_label(c)),
            # the Title sheet's caption is not wanted on a card
            ("        <caption>", "        <caption>"),  # placeholder anchor check only; caption removed below
        ])
        w = worksheet_block(t, name)
        w2, n = re.subn(r"      <layout-options>.*?</layout-options>\r\n", "", w, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"{name}: layout-options")
        # left-align the card text
        w2 = sub_once(w2, "<format attr='mark-labels-show' value='true' />",
                      "<format attr='mark-labels-show' value='true' />")
        t = sub_once(t, w, w2)
        t = add_window(t, name)
    return t


def add_guides(t: str) -> str:
    old_label = ("                <run fontcolor='#57c0e9' underline='true'>&lt;</run>\r\n"
                 "                <run fontcolor='#57c0e9' underline='true'>[federated.1ikycy21f3ow4k1eazzbx1iah2yl].[none:Calculation_7500000000000000001:nk]</run>\r\n"
                 "                <run fontcolor='#57c0e9' underline='true'>&gt;</run>")
    for key in CARD_COPY:
        name = f"LP - Guide {key}"
        t = clone_worksheet(t, "Links - GPA Roster - Newark", name, [
            (old_label, "                <run fontcolor='#b9c7e6' fontsize='8' italic='true'>Help guide: coming soon</run>"),
        ])
        w = worksheet_block(t, name)
        # drop the cross-source school filter and its slice, and the goals source it needs
        w2, n = re.subn(r"          <filter class='categorical' column='\[federated\.0n798br073i5kb170j6l90uiv50a\]\.\[none:school:nk\]'.*?</filter>\r\n", "", w, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"{name}: school filter")
        w2 = sub_once(w2, "            <column>[federated.0n798br073i5kb170j6l90uiv50a].[none:school:nk]</column>\r\n", "")
        w2, n = re.subn(r"          <datasource-dependencies datasource='federated\.0n798br073i5kb170j6l90uiv50a'>.*?</datasource-dependencies>\r\n", "", w2, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"{name}: goals dependencies")
        w2 = sub_once(w2, "            <datasource caption='rpt_tableau__gpa_goal_progress (kipptaf_tableau)' name='federated.0n798br073i5kb170j6l90uiv50a' />\r\n", "")
        # drop the roster tooltip; the placeholder has nothing to say on hover
        w2, n = re.subn(r"            <customized-tooltip>.*?</customized-tooltip>\r\n", "", w2, count=1, flags=re.S)
        if n != 1:
            raise RuntimeError(f"{name}: tooltip")
        t = sub_once(t, w, w2)
        t = add_window(t, name)
    return t
```

Remove the placeholder `("        <caption>", "        <caption>")` edit from
`add_cards` before running: it is there only to show where a no-op would sit,
and a no-op edit is exactly what the one-match assertion should not be spent on.
Keep the `re.subn` that removes the whole `<layout-options>` block.

Add `add_cards` and `add_guides` to `STEPS`.

- [ ] **Step 4: Run build, assert, checkers**

Expected: `PASS task6`, `worksheets: 19`, `sheet-windows: 19`, `check_twb`
`rc=0`. `check_twb`'s `check_unknown` will list nothing new: every element in
the clones exists in the base.

---

### Task 7: The `Landing Page` dashboard, its window, and the actions

**Files:**

- Modify: `$lp/build_lp.py` (dashboard, window, actions)
- Modify: `$lp/assert_lp.py` (add `task7`)

**Interfaces:**

- Produces: one `<dashboard name='Landing Page'>` with a `<size>` of 1366 by
  1500 and a tiled zone tree; one
  `<window class='dashboard' name='Landing Page'>` inserted as the FIRST window
  so it is the first tab; nine `nav-action` elements named `[LP_Nav_<n>_<hex>]`;
  three URL actions named `[LP_Link_<Region>]`.
- Target window uuids for the header buttons, read from `base.twb` at build time
  (the plan quotes the 2026-09-10 values):

| Dashboard               | window simple-id                         |
| ----------------------- | ---------------------------------------- |
| Academic Health Home    | `{0AC26311-199E-49CE-9660-25C6B2FCF0C8}` |
| Academic Health Schools | `{73F774A6-1C5F-4D0D-A201-1444AD0D3D59}` |
| Cumulative GPA Monitor  | `{ADAF5834-6C69-47A2-8FED-EBF0C9A782FC}` |
| Gradebook School Rollup | `{3F237DC3-54DD-4F2D-8E5C-EB1C7DE8FC10}` |
| Gradebook Teacher View  | `{8248DE6A-1111-444E-8496-6E843188D9A6}` |

- [ ] **Step 1: Add the assertion**

```python
def task7(t: str) -> None:
    d = re.search(r"<dashboard [^>]*name='Landing Page'>.*?</dashboard>", t, re.S)
    assert d, "dashboard"
    d = d.group(0)
    assert "<size maxheight='1500' maxwidth='1366' minheight='1500' minwidth='1366' sizing-mode='fixed' />" in d
    assert "<devicelayouts" not in d
    for name in [f"LP - {k} {c}" for k in ("Card", "Guide") for c in CARDS] + [
        "LP - Title", "LP - Tile Y1 GPA", "LP - Tile Course Failures", "LP - Tile Cumulative GPA",
        "LP - Tile Gradebook Health", "LP - Strip Y1 GPA", "LP - Strip Course Failures",
        "LP - Strip Cumulative GPA", "LP - Strip Gradebook Health",
        "Links - GPA Roster - Newark", "Links - GPA Roster - Camden", "Links - GPA Roster - Paterson"]:
        assert count(d, rf"<zone [^>]*name='{re.escape(name)}'") == 1, name
    for tile in ("LP - Tile Y1 GPA", "LP - Tile Course Failures", "LP - Tile Cumulative GPA", "LP - Tile Gradebook Health"):
        z = re.search(rf"<zone [^>]*name='{re.escape(tile)}'[^>]*>", d).group(0)
        assert "show-title='true'" in z and "show-caption='true'" in z, tile
    assert count(d, r"tabdoc:goto-sheet window-id=") == 5
    for wid in ("{0AC26311-199E-49CE-9660-25C6B2FCF0C8}", "{73F774A6-1C5F-4D0D-A201-1444AD0D3D59}",
                "{ADAF5834-6C69-47A2-8FED-EBF0C9A782FC}", "{3F237DC3-54DD-4F2D-8E5C-EB1C7DE8FC10}",
                "{8248DE6A-1111-444E-8496-6E843188D9A6}"):
        assert wid in d, wid
    ids = re.findall(r"<zone [^>]*\bid='(\d+)'", d)
    assert len(ids) == len(set(ids)), "duplicate zone id"
    # window: first, and lists every LP sheet as a viewpoint
    win = re.search(r"<windows[^>]*>\r\n(.*?)</window>", t, re.S).group(1)
    assert "class='dashboard' maximized='true' name='Landing Page'" in win, "Landing Page window is not first or not the default view"
    assert count(t, r" maximized='true'") == 1, "exactly one maximized window"
    assert "maximized='true' name='Gradebook Teacher View'" not in t
    # actions
    assert count(t, r"<nav-action caption='LP [^']*' name='\[LP_Nav_") == 9
    assert count(t, r"<action caption='GPA Roster [A-Za-z]+ \(Landing Page\)' name='\[LP_Link_") == 3
    for tab in ("Academic Health Home", "Academic Health Schools", "Cumulative GPA Monitor",
                "Gradebook School Rollup", "Gradebook Teacher View"):
        assert count(t, rf"<param name='sheet' value='{re.escape(tab)}' />") >= 1, tab
    # text zones carry no tokens
    for tz in re.findall(r"<zone [^>]*type-v2='text'.*?</zone>", d, re.S):
        assert "[Parameters]" not in tz and "federated." not in tz
```

Add to `CHECKS`; run; expected `FAIL task7`.

- [ ] **Step 2: The zone builder**

Geometry follows the Rollup: a root vertical flow at 8 px inset on every side.
At 1366 by 1500 that is `x=586 w=98828 y=533 h=98934`. Children of a vertical
flow stack in `y`; children of a horizontal flow stack in `x`. Each fixed child
carries `fixed-size=<px>` and `is-fixed='true'`; every flow container has at
least one non-fixed child.

```python
W_UNIT = 100000 / 1366
H_UNIT = 100000 / 1500
_zone_id = [0]


def zid() -> int:
    _zone_id[0] += 1
    return _zone_id[0]


def px_w(px: float) -> int:
    return round(px * W_UNIT)


def px_h(px: float) -> int:
    return round(px * H_UNIT)


STYLE_NONE = ("<zone-style>\r\n"
              "  <format attr='border-color' value='#000000' />\r\n"
              "  <format attr='border-style' value='none' />\r\n"
              "  <format attr='border-width' value='0' />\r\n"
              "  <format attr='margin' value='4' />\r\n"
              "</zone-style>\r\n")


def indent(block: str, n: int) -> str:
    pad = " " * n
    return "".join(pad + line if line.strip() else line for line in block.splitlines(keepends=True))


def zone(attrs: str, inner: str, depth: int, style: str = STYLE_NONE) -> str:
    pad = " " * depth
    return f"{pad}<zone {attrs}>\r\n{inner}{indent(style, depth + 2)}{pad}</zone>\r\n"


def sheet_zone(name: str, x: int, y: int, w: int, h: int, depth: int, *, title: bool = False, caption: bool = False, fixed_px: int | None = None, axis: str = "horz") -> str:
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    attrs = (f"h='{h}' id='{zid()}'{fixed} name='{name}' show-caption='{str(caption).lower()}' "
             f"show-title='{str(title).lower()}' w='{w}' x='{x}' y='{y}'")
    cache = " " * (depth + 2) + "<layout-cache cell-count-h='1' cell-count-w='1' type-h='cell' type-w='cell' />\r\n"
    return zone(attrs, cache, depth)


def text_zone(runs: str, x: int, y: int, w: int, h: int, depth: int, fixed_px: int | None = None, bg: str | None = None) -> str:
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    attrs = f"forceUpdate='true' h='{h}' id='{zid()}'{fixed} type-v2='text' w='{w}' x='{x}' y='{y}'"
    inner = " " * (depth + 2) + "<formatted-text>\r\n" + indent(runs, depth + 4) + " " * (depth + 2) + "</formatted-text>\r\n"
    style = STYLE_NONE if not bg else STYLE_NONE.replace("</zone-style>", f"  <format attr='background-color' value='{bg}' />\r\n</zone-style>")
    return zone(attrs, inner, depth, style)


def button_zone(caption: str, tooltip: str, target_window_uuid: str, x: int, y: int, w: int, h: int, depth: int, fixed_px: int) -> str:
    attrs = f"fixed-size='{fixed_px}' h='{h}' id='{zid()}' is-fixed='true' type-v2='dashboard-object' w='{w}' x='{x}' y='{y}'"
    inner = indent(crlf(f"""
<button action='tabdoc:goto-sheet window-id=&quot;{target_window_uuid}&quot;' button-type='text'>
  <button-visual-state>
    <caption>{esc(caption)}</caption>
    <tooltip-text>{esc(tooltip)}</tooltip-text>
    <button-caption-font-style fontcolor='#ffffff' fontname='Tableau Bold' fontsize='10' />
    <format attr='background-color' value='#333333' />
  </button-visual-state>
</button>
"""), depth + 2)
    return zone(attrs, inner, depth)


def flow(param: str, x: int, y: int, w: int, h: int, depth: int, children: str, fixed_px: int | None = None, bg: str | None = None, name: str | None = None) -> str:
    fixed = f" fixed-size='{fixed_px}' is-fixed='true'" if fixed_px else ""
    fn = f" friendly-name='{name}'" if name else ""
    attrs = f"{fixed}{fn} h='{h}' id='{zid()}' param='{param}' type-v2='layout-flow' w='{w}' x='{x}' y='{y}'".lstrip()
    style = ("<zone-style>\r\n  <format attr='border-color' value='#000000' />\r\n  <format attr='border-style' value='none' />\r\n"
             "  <format attr='border-width' value='0' />\r\n" + (f"  <format attr='background-color' value='{bg}' />\r\n" if bg else "") + "</zone-style>\r\n")
    return zone(attrs, children, depth, style)
```

- [ ] **Step 3: The page, zone by zone**

Pixel budget per the spec, summing to the root's 1484 px of usable height (1500
minus 8 px inset top and bottom): header 80, tiles 220, strip 150, Miami
footnote 20, cards 220, definitions 400, coverage 220, links 60, and a flexible
spacer of 114 px at the bottom so one child is not fixed. Widths: the root is
1350 px usable (1366 minus 16). Four tiles at 337.5 px each; five cards at 270
px each; header split 167 px logo, flexible title, 130 px year control, five
buttons at 120 px each.

```python
ROOT_X, ROOT_W = 586, 98828
ROOT_Y, ROOT_H = px_h(8), 100000 - 2 * px_h(8)
USABLE_W_PX = 1350

WIN = {  # target window uuids; re-read from base.twb at build time, see step 4
    "Academic Health Home": "{0AC26311-199E-49CE-9660-25C6B2FCF0C8}",
    "Academic Health Schools": "{73F774A6-1C5F-4D0D-A201-1444AD0D3D59}",
    "Cumulative GPA Monitor": "{ADAF5834-6C69-47A2-8FED-EBF0C9A782FC}",
    "Gradebook School Rollup": "{3F237DC3-54DD-4F2D-8E5C-EB1C7DE8FC10}",
    "Gradebook Teacher View": "{8248DE6A-1111-444E-8496-6E843188D9A6}",
}
CARD_TARGET = {"Home": "Academic Health Home", "Schools": "Academic Health Schools", "Monitor": "Cumulative GPA Monitor",
               "Rollup": "Gradebook School Rollup", "Teacher": "Gradebook Teacher View"}
TILE_TARGET = {"LP - Tile Y1 GPA": "Academic Health Home", "LP - Tile Course Failures": "Academic Health Schools",
               "LP - Tile Cumulative GPA": "Cumulative GPA Monitor", "LP - Tile Gradebook Health": "Gradebook School Rollup"}


def header(y: int, depth: int) -> str:
    h = px_h(80)
    x = ROOT_X
    parts = []
    parts.append(zone(f"fixed-size='167' h='{h}' id='{zid()}' is-fixed='true' is-scaled='1' param='Image/CMO_logo_whiteOrange.png' type-v2='bitmap' w='{px_w(167)}' x='{x}' y='{y}'", "", depth + 2))
    x += px_w(167)
    title_w = ROOT_W - px_w(167) - px_w(130) - 5 * px_w(120)
    parts.append(sheet_zone("LP - Title", x, y, title_w, h, depth + 2, caption=True))
    x += title_w
    parts.append(zone(f"custom-title='true' fixed-size='130' h='{h}' id='{zid()}' is-fixed='true' mode='compact' param='[Parameters].[Parameter 2]' type-v2='paramctrl' w='{px_w(130)}' x='{x}' y='{y}'",
                      " " * (depth + 4) + "<formatted-text>\r\n" + " " * (depth + 6) + "<run>Academic Year</run>\r\n" + " " * (depth + 4) + "</formatted-text>\r\n", depth + 2))
    x += px_w(130)
    for tab, short in (("Academic Health Home", "Home"), ("Academic Health Schools", "School View"),
                       ("Cumulative GPA Monitor", "GPA Monitor"), ("Gradebook School Rollup", "Gradebook Rollup"),
                       ("Gradebook Teacher View", "Teacher View")):
        parts.append(button_zone(short, f"Open {tab}", WIN[tab], x, y, px_w(120), h, depth + 2, 120))
        x += px_w(120)
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, "".join(parts), fixed_px=80, bg="#001e62", name="Header")


def tiles(y: int, depth: int) -> str:
    h = px_h(220)
    w = ROOT_W // 4
    parts = []
    x = ROOT_X
    for i, name in enumerate(TILE_TARGET):
        ww = w if i < 3 else ROOT_W - 3 * w
        parts.append(sheet_zone(name, x, y, ww, h, depth + 2, title=True, caption=True))
        x += ww
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, "".join(parts), fixed_px=220, name="Tiles")


def strip(y: int, depth: int) -> str:
    h = px_h(150)
    w = ROOT_W // 4
    parts = []
    x = ROOT_X
    for i, name in enumerate(("LP - Strip Y1 GPA", "LP - Strip Course Failures", "LP - Strip Cumulative GPA", "LP - Strip Gradebook Health")):
        ww = w if i < 3 else ROOT_W - 3 * w
        parts.append(sheet_zone(name, x, y, ww, h, depth + 2, title=True))
        x += ww
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, "".join(parts), fixed_px=150, name="Regions")


def footnote(y: int, depth: int) -> str:
    runs = "<run fontcolor='#8c8c8c' fontsize='8' italic='true'>Miami is not yet in any measure on this page. It joins when Focus gradebook data is onboarded. Paterson has no high school, so its cumulative GPA cell is blank.</run>\r\n"
    return text_zone(runs, ROOT_X, y, ROOT_W, px_h(20), depth, fixed_px=20)


def cards(y: int, depth: int) -> str:
    h = px_h(220)
    w = ROOT_W // 5
    parts = []
    x = ROOT_X
    for i, key in enumerate(CARDS):
        ww = w if i < 4 else ROOT_W - 4 * w
        body = sheet_zone(f"LP - Card {key}", x, y, ww, px_h(196), depth + 4)
        guide = sheet_zone(f"LP - Guide {key}", x, y + px_h(196), ww, px_h(24), depth + 4, fixed_px=24, axis="vert")
        parts.append(flow("vert", x, y, ww, h, depth + 2, body + guide, bg="#001e62"))
        x += ww
    return flow("horz", ROOT_X, y, ROOT_W, h, depth, "".join(parts), fixed_px=220, name="Directory")
```

Definitions, coverage and links follow the same pattern. The definitions zone is
one `text_zone` whose runs are, per term, a bold run with the term, a regular
run with the sentence from the spec's definitions table, and a break; the copy
is the spec's table verbatim, and the "Weighted versus unweighted" entry is the
4.33 wording. The coverage grid is one `text_zone` in `fontname='Courier New'`
with a header line and seven rows, `●` where the spec table says yes and `—`
where it says no, plus the two row notes. The links zone is a horizontal flow
holding a `text_zone` reading `GPA Roster` and the three
`Links - GPA Roster - <Region>` sheet zones at 60 px each, exactly as the Home
header lays them out (`fixed-size='20'`-style layout-cache is not required; the
plain cell layout-cache is used).

```python
def build_dashboard() -> tuple[str, str]:
    """Return (dashboard element, dashboard window element)."""
    _zone_id[0] = 0
    depth = 8
    y = ROOT_Y
    body = []
    for fn, px in ((header, 80), (tiles, 220), (strip, 150), (footnote, 20), (cards, 220),
                   (definitions, 400), (coverage, 220), (links, 60)):
        body.append(fn(y, depth + 2))
        y += px_h(px)
    spacer_h = ROOT_Y + ROOT_H - y
    body.append(zone(f"h='{spacer_h}' id='{zid()}' type-v2='empty' w='{ROOT_W}' x='{ROOT_X}' y='{y}'", "", depth + 2))
    root = flow("vert", ROOT_X, ROOT_Y, ROOT_W, ROOT_H, depth, "".join(body))
    dash_uuid = new_uuid()
    dashboard = crlf(f"""
    <dashboard enable-sort-zone-taborder='true' name='Landing Page'>
      <style />
      <size maxheight='1500' maxwidth='1366' minheight='1500' minwidth='1366' sizing-mode='fixed' />
      <datasources>
        <datasource name='Parameters' />
        <datasource caption='rpt_tableau__student_course_grades+ (kipptaf_tableau)' name='{GRADES_DS}' />
        <datasource caption='rpt_tableau__gpa_goal_progress (kipptaf_tableau)' name='{GOAL_DS}' />
        <datasource caption='rpt_tableau__gradebook_audit (kipptaf_tableau)' name='{GB_DS}' />
      </datasources>
      <zones>
""") + root + crlf(f"""
      </zones>
      <simple-id uuid='{dash_uuid}' />
    </dashboard>
""")
    viewpoints = "".join(f"        <viewpoint name='{esc(n)}'>\r\n          <zoom type='entire-view' />\r\n        </viewpoint>\r\n"
                         for n in sorted(LP_SHEETS + ["Links - GPA Roster - Camden", "Links - GPA Roster - Newark", "Links - GPA Roster - Paterson"]))
    window = crlf(f"""
    <window class='dashboard' maximized='true' name='Landing Page'>
      <viewpoints>
""") + viewpoints + crlf(f"""
      </viewpoints>
      <active id='-1' />
      <simple-id uuid='{new_uuid()}' />
    </window>
""")
    return dashboard, window
```

The `<dashboard>` element's `<datasource-dependencies>` blocks, which the
existing dashboards carry for their parameter controls, are added for
`[Parameter 2]` only, copied verbatim from the Rollup's block for
`[Parameter 1 1]` with the column swapped to the `p_Academic_Year` column
definition from `Y1 Landing - BAN Network ≥3.0`'s dependencies. Insert it
between `</datasources>` and `<zones>`.

- [ ] **Step 4: Insert dashboard, window, actions**

```python
LP_SHEETS = ["LP - Title", "LP - Tile Y1 GPA", "LP - Tile Course Failures", "LP - Tile Cumulative GPA",
             "LP - Tile Gradebook Health", "LP - Strip Y1 GPA", "LP - Strip Course Failures",
             "LP - Strip Cumulative GPA", "LP - Strip Gradebook Health"] + \
            [f"LP - {k} {c}" for k in ("Card", "Guide") for c in CARDS]


def read_window_uuids(t: str) -> None:
    for tab in WIN:
        m = re.search(rf"<window class='dashboard'[^>]*name='{re.escape(tab)}'.*?<simple-id uuid='([^']*)' />\r\n    </window>", t, re.S)
        if not m:
            raise RuntimeError(f"window uuid for {tab}")
        WIN[tab] = m.group(1)


def add_dashboard(t: str) -> str:
    read_window_uuids(t)
    dashboard, window = build_dashboard()
    t = insert_before(t, "  </dashboards>\r\n", dashboard)
    # the base's <windows> tag carries source-height='114'; anchor on the tag as found
    windows_tag = re.search(r"  <windows[^>]*>\r\n", t).group(0)
    t = insert_after(t, windows_tag, window)
    # move the default-view marker off the Teacher View window (the one sanctioned edit)
    t = sub_once(t, "<window class='dashboard' maximized='true' name='Gradebook Teacher View'",
                 "<window class='dashboard' name='Gradebook Teacher View'")
    return t


def nav_action(n: int, source_sheet: str, target: str) -> str:
    return crlf(f"""
    <nav-action caption='LP {n:02d} {esc(source_sheet)} to {esc(target)}' name='[LP_Nav_{n:02d}_{uuid.uuid4().hex.upper()}]'>
      <activation type='on-select' />
      <source dashboard='Landing Page' type='sheet' worksheet='{esc(source_sheet)}' />
      <params>
        <param name='sheet' value='{esc(target)}' />
      </params>
    </nav-action>
""")


ROSTER = {"Newark": "https://docs.google.com/spreadsheets/d/12RHEUde41uR91Fp1aNrpImxhg72kOjPAQu7xLJ90evc/edit?gid=0#gid=0",
          "Camden": "https://docs.google.com/spreadsheets/d/1qM6DQk_mqh4x_rI5YVQyZdYbfDxzOaLGyrqjySlVv2Y/edit?gid=0#gid=0",
          "Paterson": "https://docs.google.com/spreadsheets/d/13j1khv49eSxTFUJGxbgQKnjvmUhYTgH-SshZr5NWCbU/edit?gid=0#gid=0"}


def add_actions(t: str) -> str:
    blocks = []
    n = 0
    for key, target in CARD_TARGET.items():
        n += 1
        blocks.append(nav_action(n, f"LP - Card {key}", target))
    for sheet, target in TILE_TARGET.items():
        n += 1
        blocks.append(nav_action(n, sheet, target))
    for region, url in ROSTER.items():
        blocks.append(crlf(f"""
    <action caption='GPA Roster {region} (Landing Page)' name='[LP_Link_{region}]'>
      <activation type='on-select' />
      <source dashboard='Landing Page' type='sheet' worksheet='Links - GPA Roster - {region}' />
      <link caption='' expression='{url}' />
    </action>
"""))
    return insert_before(t, "  </actions>\r\n", "".join(blocks))


STEPS = [add_goal_calcs, add_title, add_tile_y1, add_tile_failures, add_tile_cumulative,
         add_tile_gradebook, add_strips, add_cards, add_guides, add_dashboard, add_actions]
```

The exact opening tag of `<windows>` must be read from the base (grep
`"<windows"`); the plan's conditional handles the two forms seen in this corpus.
The roster URLs are the ones the three existing actions carry; read them from
the base with a regex rather than trusting the plan's copy, and raise if they
differ.

- [ ] **Step 5: Run build, assert, all checkers, and geometry on the new
      dashboard**

```bash
lp=/workspaces/teamster/.claude/scratch/tableau/lp; cd /workspaces/teamster
~/.local/bin/uv run python $lp/build_lp.py >$lp/o-build.txt 2>&1; echo "build rc=$?"
~/.local/bin/uv run python $lp/assert_lp.py >$lp/o-assert.txt 2>&1; echo "assert rc=$?"; grep -c PASS $lp/o-assert.txt
~/.local/bin/uv run python docs/tableau-xml/scripts/check_additive.py $lp/out.twb $lp/base.twb --sheet-prefix "LP - " --dashboard "Landing Page" --calc-prefix Calculation_76 --action-prefix LP_ >$lp/o-add.txt 2>&1; echo "additive rc=$?"
~/.local/bin/uv run python docs/tableau-xml/scripts/check_twb.py $lp/out.twb --ref $lp/base.twb >$lp/o-twb.txt 2>&1; echo "check_twb rc=$?"
~/.local/bin/uv run python docs/tableau-xml/scripts/check_geometry.py $lp/out.twb "Landing Page" --baseline $lp/base.twb >$lp/o-geo.txt 2>&1; echo "geometry rc=$?"; tail -5 $lp/o-geo.txt
for d in "Academic Health Home" "Academic Health Schools" "Cumulative GPA Monitor" "Gradebook School Rollup" "Gradebook Teacher View"; do
  ~/.local/bin/uv run python docs/tableau-xml/scripts/check_geometry.py $lp/out.twb "$d" --baseline $lp/base.twb >/dev/null 2>&1; echo "geometry [$d] rc=$?"
done
```

Expected: every `rc=0`; `5` PASS lines; `check_additive` reports
`worksheets: 19, dashboard: 1, dashboard-window: 1, sheet-windows: 19, nav-actions: 9, url-actions: 3, calcs: 2`.
`check_geometry` on `Landing Page` reports no overlaps, with new zones checked
against the absolute bound (it prints which mode). If the root zone check
complains that no `layout-basic` spans the canvas, confirm the Rollup baseline
produced the same message in Task 1 Step 3 and discount it.

- [ ] **Step 6: Prove the geometry assertion has teeth on the new dashboard**

```bash
lp=/workspaces/teamster/.claude/scratch/tableau/lp; cd /workspaces/teamster
~/.local/bin/uv run python docs/tableau-xml/scripts/mutate.py $lp/out.twb $lp/ctrl2.twb "Landing Page" control; cmp $lp/out.twb $lp/ctrl2.twb && echo CONTROL_OK
tile_id=$(grep -o "id='[0-9]*'[^>]*name='LP - Tile Y1 GPA'" $lp/out.twb | grep -o "id='[0-9]*'" | tr -dc 0-9)
~/.local/bin/uv run python docs/tableau-xml/scripts/mutate.py $lp/out.twb $lp/mut-2.twb "Landing Page" reparent $tile_id 1
~/.local/bin/uv run python docs/tableau-xml/scripts/check_geometry.py $lp/mut-2.twb "Landing Page" --baseline $lp/base.twb >$lp/o-geo-mut.txt 2>&1; echo "mutant geometry rc=$?"
```

Expected: `CONTROL_OK`, then `rc=1` on the mutant.

---

### Task 8: Repack and publish the review copy

**Files:**

- Create: `tests/test_zz_lp_publish.py` (throwaway)
- Produces: `$lp/final.twbx`, `$lp/review-meta.txt` (review luid, URL, the
  production revision number from Task 1)

- [ ] **Step 1: Repack**

```bash
lp=/workspaces/teamster/.claude/scratch/tableau/lp; cd /workspaces/teamster
~/.local/bin/uv run python docs/tableau-xml/scripts/repack.py $lp/out.twb $lp/base.twbx $lp/final.twbx >$lp/o-repack.txt 2>&1; echo "repack rc=$?"; tail -3 $lp/o-repack.txt
```

Expected: `rc=0`, packaged bytes equal to `out.twb`, zero bare LF. The donor is
the same `base.twbx` the base came from, so the extract matches.

- [ ] **Step 2: Confirm the target project with the user**

The spec default is `GPA-monitor-temp`, `c74d8e08-b856-4430-a759-ebacb061e376`.
Ask once, in plain text, before writing the publish test. Record the answer in
the test's `TEMP_PROJECT` and its allowlist.

- [ ] **Step 3: Write the publish test from the template**

Copy `docs/tableau-xml/scripts/tsc_session.py` to `tests/test_zz_lp_publish.py`,
delete `test_download`, and set:

```python
WORKBOOK_LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"
TEMP_PROJECT = "c74d8e08-b856-4430-a759-ebacb061e376"   # or the id the user named
OUT = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
```

In `test_publish_and_render`, before `publish`:

```python
        base_twb = (OUT / "base.twb").read_text(encoding="utf-8", newline="")
        out_twb = (OUT / "out.twb").read_text(encoding="utf-8", newline="")
        meta = dict(line.split("=", 1) for line in (OUT / "base-meta.txt").read_text().splitlines())
        live = set(meta["live_views"].split("|"))
        publishable = set(re.findall(r"<window class='(?:worksheet|dashboard)'(?![^>]*hidden='true')[^>]*name='([^']*)'", out_twb))
        publishable = {n.replace("&lt;", "<").replace("&amp;", "&") for n in publishable}
        added = {"Landing Page"}
        item.hidden_views = sorted(publishable - live - added)
        item.show_tabs = meta["show_tabs"] == "True"
        item.name = f"ZZ-REVIEW {date.today():%Y-%m-%d} AGHS landing page"
        print("HIDING", len(item.hidden_views), "sheets; LIVE will be", sorted((publishable - set(item.hidden_views))))
```

Replace the template's render loop with a render of every live view at high
resolution, saved as `$lp/render-<slug>.png`, with the parameter left at its
default, plus a second render of `Landing Page` with `p_Marking_Period` set to
`Q1` (`opts.parameter("p_Marking_Period", "Q1")`) saved as
`render-landing-q1.png`. After the loop, write `review-meta.txt` with the review
item's `id`, `webpage_url`, and `production_revision=<from base-meta>`.

- [ ] **Step 4: Publish**

```bash
cd /workspaces/teamster && ~/.local/bin/uv run pytest tests/test_zz_lp_publish.py -s -q 2>&1 | tail -25
```

Expected: `HIDING` line listing every pre-existing hidden sheet and every
`LP - ` sheet, `LIVE will be` exactly the five existing dashboards plus
`Landing Page`, `PUBLISHED: <luid> into GPA-monitor-temp`, six or more
`RENDERED` lines, `1 passed`. A `401002` is a session race: rerun once.

After the publish, in the same test, re-fetch the review item with
`server.workbooks.get_by_id(item.id)`, populate its views, and print
`DEFAULT_VIEW <name>` for the view whose id equals `default_view_id`. Expected:
`Landing Page`. This is the check that Server honors the `maximized` marker on a
REST publish; it is inferred from four workbooks' correlation until this line
prints. Record the outcome in the lessons log either way.

- [ ] **Step 5: Delete the throwaway test**

```bash
rm -f /workspaces/teamster/tests/test_zz_lp_publish.py
```

---

### Task 9: Verify the numbers and the render

**Files:**

- Create: `tests/test_zz_lp_numbers.py` (throwaway)
- Create: `$lp/crop_lp.py` (scratch)

**Interfaces:**

- Consumes: the review copy's luid from `$lp/review-meta.txt`.

- [ ] **Step 1: Pull the numbers through the data API, not the pixels**

Each tile reads the same calculation as its source BAN, so the check is numeric.
`populate_csv` on a dashboard view returns the data of every sheet on it; on
this server version it returns one CSV per sheet in the response body (REST 3.30
and later). Write the test to fetch `Landing Page` and the three source
dashboards from the review copy, then compare.

```python
"""Throwaway: numeric equality between the landing tiles and their source BANs."""

import csv
import io
import os
from pathlib import Path

import tableauserverclient as tsc

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")


def _csv(server: tsc.Server, view: tsc.ViewItem, **params: str) -> list[dict]:
    opts = tsc.CSVRequestOptions()
    for k, v in params.items():
        opts.parameter(k, v)
    server.views.populate_csv(view, opts)
    text = b"".join(view.csv).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_numbers() -> None:
    meta = dict(line.split("=", 1) for line in (LP / "review-meta.txt").read_text().splitlines())
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(meta["review_luid"])
        server.workbooks.populate_views(wb)
        views = {v.name: v for v in wb.views}
        for name in ("Landing Page", "Academic Health Home", "Cumulative GPA Monitor", "Gradebook School Rollup"):
            rows = _csv(server, views[name], p_Region="All")
            (LP / f"csv-{name.replace(' ', '_')}.txt").write_text("\n".join(",".join(f"{k}={v}" for k, v in r.items()) for r in rows[:40]))
            print(f"CSV {name}: {len(rows)} rows; columns={list(rows[0].keys()) if rows else []}")
```

Run it, read the four CSV dumps, and record in `$lp/numbers.md` a table with one
row per tile: tile value, source BAN value, equal yes/no. The columns to compare
are the ones named `% Y1 GPA at or above 3.0`, `% Y1 Failing 2 or more`,
`% at 3.0+` and `% healthy`; if the CSV form returns only the first sheet of
each dashboard, fall back to rendering and reading crops (Step 2) and say so in
the hand-over. Any inequality is a defect: stop and diagnose before Task 10.

- [ ] **Step 2: Crop the renders and look**

```python
"""crop_lp.py: crop the landing render into the regions to read."""

from pathlib import Path

from PIL import Image

LP = Path("/workspaces/teamster/.claude/scratch/tableau/lp")
img = Image.open(LP / "render-landing-page.png")
W, H = img.size
sx, sy = W / 1366, H / 1500
BOXES = {
    "header": (0, 0, 1366, 96),
    "tiles": (0, 88, 1366, 316),
    "strip": (0, 308, 1366, 486),
    "cards": (0, 478, 1366, 716),
    "definitions": (0, 708, 1366, 1116),
    "coverage": (0, 1108, 1366, 1336),
    "links": (0, 1328, 1366, 1500),
}
for name, (x0, y0, x1, y1) in BOXES.items():
    img.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))).save(LP / f"crop-{name}.png")
    print("wrote", name)
```

Run `~/.local/bin/uv run --with pillow python $lp/crop_lp.py`, then `Read` each
crop. If the output hook redacts a crop, halve it and read the halves. Look for,
and record in `$lp/render-notes.md`: `####` in any tile; an ellipsis in any card
or the title; a blank line where a title or caption should be (a zone without
`show-title='true'`); a literal `[federated` or `[Parameters]` token; two zones
overlapping; the region strip rows misaligned across the four columns; the Q1
render showing the marking period `Q1` in the two Y1 tile titles.

- [ ] **Step 3: Region strip alignment decision**

If the four strip columns do not align row for row (Paterson missing from the
cumulative column shifts the rows), apply the spec's fallback: replace the four
strip sheets in `strip()` with a 3 by 4 grid of per-region sheets, each a clone
of the matching strip sheet with a fixed `region` filter member. That is twelve
clones named `LP - Strip <measure> <Region>`; the assertion in `task5` changes
to check the twelve names; the checker suite and Task 8 rerun. Record which
construction shipped.

- [ ] **Step 4: Delete the throwaway test**

```bash
rm -f /workspaces/teamster/tests/test_zz_lp_numbers.py
```

---

### Task 10: Repo changes: links entry, exposure, spec touch-ups, hand-off note

**Files:**

- Modify: `docs/launch/links.yml` (the `academic_gradebook_health_suite` entry's
  `url`)
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml` (the
  `academic_gradebook_health_suite` exposure's `depends_on`)
- Modify:
  `docs/superpowers/specs/2026-09-10-academic-health-launch-page-design.md` (two
  lines)
- Create:
  `docs/superpowers/plans/2026-09-10-academic-health-launch-page-handoff.md`

- [ ] **Step 1: Read the launch page guide, then edit the links entry**

Read `docs/guides/launch-page-guide.md` for the `url` rules, then change the
entry's `url` from
`https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/AcademicHealthHome?:embed=y`
to
`https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/LandingPage?:embed=y`.
The view URL name Tableau assigns to a sheet named `Landing Page` is
`LandingPage`, the same form the other three landing pages use. Set `status` per
the guide's rule for a URL that is not yet live in Production (the guide names
the value; do not guess it).

- [ ] **Step 2: Run the launch build's tests**

```bash
wt=/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-academic-health-launch-page
cd $wt && ~/.local/bin/uv run pytest tests/launch -q 2>&1 | tail -5
```

Expected: pass. A validation failure names the field; fix it per the guide.

- [ ] **Step 3: Complete the exposure**

In `src/dbt/kipptaf/models/exposures/tableau.yml`, the exposure named
`academic_gradebook_health_suite` lists three refs. Add two:

```yaml
depends_on:
  - ref("rpt_tableau__gpa_goals")
  - ref("rpt_tableau__gpa_cumulative_year")
  - ref("rpt_tableau__student_course_grades")
  - ref("rpt_tableau__gpa_goal_progress")
  - ref("rpt_tableau__gradebook_audit")
```

Then `cd $wt && ~/.local/bin/uv run dbt parse --project-dir $wt/src/dbt/kipptaf`
and confirm it exits 0.

- [ ] **Step 4: Two spec touch-ups**

In the spec's tab-directory section, change "cloned from
`Sheet Card - expectations`" to "cloned from `Y1 Landing - Title`" with the
reason from Task 6. In the links section, change "the three existing URL actions
each gain the new dashboard as a source" to "three new URL actions, one per
region, named `GPA Roster <Region> (Landing Page)`, with the same expressions as
the existing nine; the existing actions are not edited". The default-view
carve-out is already in the spec's Verification section.

- [ ] **Step 5: Write the hand-off note**

The note carries, in this order: the review copy URL and luid; the `.twbx` path;
Production's revision number before any of this; the numbers table from
`$lp/numbers.md`; the render notes; the strip construction that shipped; what
was verified by data, what by render, what is inferred; what only the user can
check (Desktop open, every navigation click, the three roster links, the
Academic Year parameter carrying across tabs); that a `<devicelayouts>` block
exists on four existing dashboards and was untouched and none was added; that
embedded connection credentials are not carried by a publish; and that
publishing to Production and the default-view change are the user's actions.

- [ ] **Step 6: Lint, commit, push, open the PR**

```bash
wt=/workspaces/teamster/.worktrees/anthonygwalters/feat/claude-academic-health-launch-page
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/launch/links.yml src/dbt/kipptaf/models/exposures/tableau.yml docs/superpowers/specs/2026-09-10-academic-health-launch-page-design.md docs/superpowers/plans/2026-09-10-academic-health-launch-page-handoff.md </dev/null
git -C $wt add -u && git -C $wt add docs/superpowers/plans/2026-09-10-academic-health-launch-page-handoff.md
git -C $wt commit -m "feat(tableau): landing page for the Academic & Gradebook Health Suite

Refs #5235

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git -C $wt push -u origin anthonygwalters/feat/claude-academic-health-launch-page
```

Open the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md`, body ending `Closes #5235`, then invoke
`pr-ci-review`. The PR carries the repo changes and the hand-off note; the
`.twbx` is handed to the user out of band, and the PR description says the
Production publish is theirs.

---

## Self-review

- Spec coverage: header (Task 7 `header`), tiles (Task 4), region strip and
  Miami footnote (Tasks 5, 7), directory cards and guide slots (Task 6),
  definitions, coverage grid and links (Task 7 step 3), navigation (Task 7 step
  4, verified element forms), default view and links entry (Task 10), exposure
  fix (Task 10), byte identity (Task 2), render and numeric verification (Task
  9), hand-off contents (Task 10). The spec's "each tile carries its data update
  time" is the `<caption>` in Task 4.
- Placeholders: none. The two places the plan defers to the base file (window
  uuids, roster URLs) read and assert at build time rather than trust the copy.
- Names: `Calculation_7600000000000000001` and `...002`, `LP - ` prefix,
  `LP_Nav_` and `LP_Link_` action prefixes, and `Landing Page` are used
  identically in the build script, the assertions and the `check_additive`
  arguments.
