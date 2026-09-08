# Cumulative GPA Monitor cards, captions and basis reminder — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every chart on the Cumulative GPA Monitor a title and a caption,
state the GPA basis at every panel that depends on it, and repoint the goal
colours to the Gradebook Fidelity met and not-met pair.

**Architecture:** The deliverable is a Tableau workbook, not repository code.
Each task runs a Python script over the workbook XML in
`.claude/scratch/gpa-overnight/`, then proves the result with an assertion
script that fails before the edit and passes after. Content changes land before
geometry changes, so a layout break bisects cleanly. Nothing publishes to
`Production`.

**Tech Stack:** Python 3 standard library (`re`, `xml.etree.ElementTree`,
`zipfile`), `tableauserverclient` for download, publish and render, `pytest` for
anything needing credentials.

**Spec:**
`docs/superpowers/specs/2026-09-08-cumulative-monitor-cards-captions-design.md`

## Global Constraints

Never publish to the Tableau `Production` project, for any reason, at any step.

Publish only to `GPA-monitor-temp`, project id
`c74d8e08-b856-4430-a759-ebacb061e376`.

Publish with `show_tabs=True` and the extract included. A publish call that
omits the extract produces a 187 KB file instead of a 30 MB one.

Insert into `<document-format-change-manifest>`, never rebuild it.

The paragraph break inside `<formatted-text>` is the literal run
`<run>Æ&#10;</run>`. It must be byte-exact.

The workbook file uses CRLF line endings. Read and write with `encoding="utf-8"`
and never normalise newlines.

Working directory for all scripts and artifacts:
`/workspaces/teamster/.claude/scratch/gpa-overnight/`, workbooks under its
`server/` subdirectory. This path is gitignored.

Credentialed work runs under pytest. A throwaway `tests/**/test_zz_*.py` gets
1Password secrets from the autouse fixture in `tests/conftest.py`; a plain
`uv run python` does not. Write those files with the Write tool, never a Bash
heredoc — a heredoc containing `os.environ` trips the sensitive-path hook.
Delete the throwaway file when the task ends.

Repository commits carry this plan's checkboxes and result notes only. The
workbook artifacts live in gitignored scratch.

Assertion scripts are given here in full, and they are the contract. Edit
scripts are specified — exact anchors, exact XML, exact invariants — but not
pre-written, because the anchors have to be located against the real file and
pre-writing untested code would assert it works without having run it. Write the
assertion first, watch it fail, then write whatever edit makes it pass.

Tableau environment variable names, for the pytest helper:
`TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`, `TABLEAU_TOKEN_NAME`,
`TABLEAU_PERSONAL_ACCESS_TOKEN`.

Constants used across tasks:

| Name             | Value                                     |
| ---------------- | ----------------------------------------- |
| Workbook LUID    | `b3c14d67-3130-46ac-82a0-0637a5cc2da5`    |
| Dashboard        | `Cumulative GPA Monitor`                  |
| View LUID        | `6b9d6b16-d63c-4976-ac22-358f3c0759c5`    |
| Datasource id    | `federated.0n798br073i5kb170j6l90uiv50a`  |
| Basis parameter  | `[Parameter 11]`, caption `GPA basis`     |
| Basis members    | `"Projected EOY"`, `"On the books today"` |
| Goal colour calc | `Calculation_7236501339153214575`         |

---

### Task 0: Re-pull production and establish the base

The copy on disk is from 15:52 on 2026-09-08. Production may have moved. Every
later task builds on this task's output.

**Files:**

- Create: `tests/tableau/test_zz_pull.py` (throwaway, deleted in step 5)
- Create: `.claude/scratch/gpa-overnight/server/prod-base3.twbx`
- Create: `.claude/scratch/gpa-overnight/server/prod-base3.twb`

**Interfaces:**

- Produces: `server/prod-base3.twb`, the unmodified production XML that Tasks 2,
  3 and 5 edit in sequence. `server/prod-base3.twbx`, the donor archive whose
  extract Task 6 repacks around the final XML.

- [ ] **Step 1: Write the download helper**

Write this with the Write tool to `tests/tableau/test_zz_pull.py`:

```python
import os
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path("/workspaces/teamster/.claude/scratch/gpa-overnight/server")
WORKBOOK_LUID = "b3c14d67-3130-46ac-82a0-0637a5cc2da5"


def _server():
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    return server, auth


def test_pull():
    server, auth = _server()
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(WORKBOOK_LUID)
        print(f"PROJECT: {wb.project_name}")
        print(f"UPDATED: {wb.updated_at}")
        path = server.workbooks.download(
            WORKBOOK_LUID, filepath=str(OUT / "prod-base3.twbx"), include_extract=True
        )
        print(f"DOWNLOADED: {path}")

    twbx = OUT / "prod-base3.twbx"
    assert twbx.stat().st_size > 20_000_000, twbx.stat().st_size
    with zipfile.ZipFile(twbx) as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (OUT / "prod-base3.twb").write_bytes(z.read(name))
    print(f"EXTRACTED: {(OUT / 'prod-base3.twb').stat().st_size} bytes")
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/tableau/test_zz_pull.py -s`

Expected: PASS. Record the printed `PROJECT`, `UPDATED` and byte sizes — they go
in the commit note. `PROJECT` must read `Production`.

- [ ] **Step 3: Diff the base against the previous pull**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight/server && python3 - <<'PY'
import re
a = open('prod-base2.twb', encoding='utf-8').read()
b = open('prod-base3.twb', encoding='utf-8').read()
for label, pat in (("worksheets", r"<worksheet name='([^']*)'"),
                   ("parameters", r"<column caption='([^']*)'[^>]*name='\[Parameter \d+\]'")):
    sa, sb = set(re.findall(pat, a)), set(re.findall(pat, b))
    print(f"{label}: {len(sa)} -> {len(sb)}")
    for x in sorted(sa - sb): print(f"   GONE: {x}")
    for x in sorted(sb - sa): print(f"   NEW:  {x}")
print("school filter zones:", len(re.findall(r"filter-group='17'", b)))
PY
```

Expected: no `GONE` lines, and `school filter zones` at least 17. A `GONE` line
means production changed in a way this plan did not anticipate — stop and report
rather than proceeding.

- [ ] **Step 4: Baseline the structural checker**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && uv run python check_twb.py server/prod-base3.twb --ref server/prod-base2.twb
```

Expected: clean. This is the reference result every later task must still
produce.

- [ ] **Step 5: Delete the throwaway and commit**

```bash
rm -f /workspaces/teamster/tests/tableau/test_zz_pull.py
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cum-monitor-cards-captions add docs/superpowers/plans/2026-09-08-cumulative-monitor-cards-captions.md
git -C /workspaces/teamster/.worktrees/anthonygwalters/feat/claude-cum-monitor-cards-captions commit -m "docs(tableau): record the production base for the Cumulative GPA Monitor rebuild"
```

Tick this task's boxes and append the recorded `UPDATED` timestamp and byte
sizes under the task heading before committing.

---

### Task 1: Probe the parameter placeholder — GATE

The whole reminder design rests on `<[Parameters].[Parameter 11]>` resolving
inside a worksheet title. That syntax is inferred from the field placeholders
already in the workbook. No parameter placeholder exists in this file yet.

**Do not start Task 3 until this task passes.** If it fails, stop and report.

**Files:**

- Create: `.claude/scratch/gpa-overnight/probe_placeholder.py`
- Create: `.claude/scratch/gpa-overnight/server/probe.twb`, `server/probe.twbx`
- Create: `tests/tableau/test_zz_probe.py` (throwaway, deleted in step 5)

**Interfaces:**

- Consumes: `server/prod-base3.twb` from Task 0.
- Produces: a yes or no answer, recorded in the plan. Produces no artifact any
  later task depends on.

- [ ] **Step 1: Write the probe edit**

Write `.claude/scratch/gpa-overnight/probe_placeholder.py`:

```python
"""Add one parameter-placeholder title to one sheet, to prove the syntax."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

D = Path("/workspaces/teamster/.claude/scratch/gpa-overnight/server")
SHEET = "GPA - Goal by grade"
TITLE = (
    "      <layout-options>\n"
    "        <title>\n"
    "          <formatted-text>\n"
    "            <run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'>"
    "<![CDATA[PROBE <[Parameters].[Parameter 11]>]]></run>\n"
    "          </formatted-text>\n"
    "        </title>\n"
    "      </layout-options>\n"
)


def main(src, dst):
    t = (D / src).read_text(encoding="utf-8")
    anchor = f"<worksheet name='{SHEET}'>"
    if anchor not in t:
        sys.exit(f"FAIL: {SHEET} not found")
    if t.count(anchor) != 1:
        sys.exit(f"FAIL: {SHEET} anchor matched {t.count(anchor)} times")
    i = t.index(anchor) + len(anchor)
    nl = "\r\n" if "\r\n" in t[:2000] else "\n"
    t = t[:i] + nl + TITLE.replace("\n", nl).rstrip(nl) + t[i:]
    ET.fromstring(t)
    (D / dst).write_text(t, encoding="utf-8", newline="")
    print(f"wrote {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Run it and repack**

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python probe_placeholder.py prod-base3.twb probe.twb && \
  uv run python check_twb.py server/probe.twb --ref server/prod-base3.twb && \
  uv run python repack_task.py server/probe.twb prod-base3.twbx probe.twbx
```

Expected: checker clean, `probe.twbx` over 20 MB.

- [ ] **Step 3: Write the publish-and-render probe**

Write with the Write tool to `tests/tableau/test_zz_probe.py`:

```python
import os
from pathlib import Path

import tableauserverclient as tsc

D = Path("/workspaces/teamster/.claude/scratch/gpa-overnight/server")
TEMP_PROJECT = "c74d8e08-b856-4430-a759-ebacb061e376"


def test_probe():
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        item = tsc.WorkbookItem(project_id=TEMP_PROJECT, name="ZZ-PROBE placeholder", show_tabs=True)
        item = server.workbooks.publish(
            item, str(D / "probe.twbx"), mode=tsc.Server.PublishMode.Overwrite
        )
        assert item.project_id == TEMP_PROJECT, item.project_name
        print(f"PUBLISHED: {item.id} into {item.project_name}")

        server.workbooks.populate_views(item)
        view = next(v for v in item.views if v.name == "Cumulative GPA Monitor")
        for value in ("Projected EOY", "On the books today"):
            opts = tsc.ImageRequestOptions(imageresolution=tsc.ImageRequestOptions.Resolution.High)
            opts.parameter("GPA basis", value)
            server.views.populate_image(view, opts)
            out = D / f"probe-{value.split()[0].lower()}.png"
            out.write_bytes(view.image)
            print(f"RENDERED {value}: {out} {out.stat().st_size} bytes")
```

- [ ] **Step 4: Run it and read the images**

Run: `uv run pytest tests/tableau/test_zz_probe.py -s`

Then open both PNGs with the Read tool and look at the `% at 3.0+ by grade`
panel.

PASS means one image reads `PROBE Projected EOY` and the other reads
`PROBE On the books today`.

FAIL means the literal text `PROBE <[Parameters].[Parameter 11]>` appears, or
the title is empty. On FAIL, stop. Record which of these it was, then report to
the user. Fallbacks in the spec, in order: caption-style syntax, native axis
titles plus a badge worksheet, fixed text.

- [ ] **Step 5: Delete the throwaway and commit the answer**

```bash
rm -f /workspaces/teamster/tests/tableau/test_zz_probe.py
```

Append a `**Result:**` line under this task's heading recording PASS or FAIL and
the exact rendered string, then commit the plan.

---

### Task 2: Repoint the goal colours

Smallest change, and independently visible in a render. Goes first among the
edits so a colour regression cannot hide behind a text or layout change.

**Files:**

- Create: `.claude/scratch/gpa-overnight/task_cum_colour.py`
- Create: `.claude/scratch/gpa-overnight/assert_cum_colour.py`
- Create: `.claude/scratch/gpa-overnight/server/cum-1-colour.twb`

**Interfaces:**

- Consumes: `server/prod-base3.twb` from Task 0.
- Produces: `server/cum-1-colour.twb`, consumed by Task 3.

- [ ] **Step 1: Write the failing assertion**

Write `.claude/scratch/gpa-overnight/assert_cum_colour.py`:

```python
"""Assert the Cumulative goal encoding uses the fidelity met / not-met pair."""

import re
import sys
from pathlib import Path

CALC = "Calculation_7236501339153214575"
WANT = {"At or above goal": "#12a47c", "Below goal": "#b3161c",
        "Not yet measured": "#b6c0cf"}
BANNED = {"#2f5fc4", "#d8342f"}


def main(path):
    t = Path(path).read_text(encoding="utf-8")
    m = re.search(rf"<encoding attr='color'[^>]*{CALC}[^>]*>(.*?)</encoding>", t, re.S)
    if not m:
        sys.exit(f"FAIL: no colour encoding for {CALC}")
    got = dict(
        (b.replace("&quot;", ""), to)
        for to, b in re.findall(r"<map to='([^']*)'>\s*<bucket>([^<]*)</bucket>", m.group(1))
    )
    bad = 0
    for member, want in WANT.items():
        if got.get(member) != want:
            print(f"  FAIL {member}: {got.get(member)} != {want}")
            bad += 1
    for member, hexv in got.items():
        if hexv in BANNED:
            print(f"  FAIL {member} still on retired colour {hexv}")
            bad += 1
    if bad:
        sys.exit(f"{bad} colour failures")
    print(f"  OK: {CALC} on {WANT['At or above goal']} / {WANT['Below goal']}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`cd /workspaces/teamster/.claude/scratch/gpa-overnight && uv run python assert_cum_colour.py server/prod-base3.twb`

Expected: FAIL, reporting `At or above goal: #2f5fc4 != #12a47c` and
`Below goal: #d8342f != #b3161c`.

- [ ] **Step 3: Write the edit**

Write `.claude/scratch/gpa-overnight/task_cum_colour.py`:

```python
"""Repoint the Cumulative GPA Monitor goal colours to the fidelity pair.

Scoped to Calculation_7236501339153214575, which colours GPA - Goal by grade,
GPA - Goal by school and GPA - BAN Gap to goal. The Academic Health Home twin,
Calculation_4005670422418128910, keeps blue and red and is not touched here.
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

D = Path("/workspaces/teamster/.claude/scratch/gpa-overnight/server")
CALC = "Calculation_7236501339153214575"
SWAP = {"At or above goal": ("#2f5fc4", "#12a47c"), "Below goal": ("#d8342f", "#b3161c")}


def main(src, dst):
    t = (D / src).read_text(encoding="utf-8")
    m = re.search(rf"<encoding attr='color'[^>]*{CALC}[^>]*>.*?</encoding>", t, re.S)
    if not m:
        sys.exit(f"FAIL: no colour encoding for {CALC}")
    block = m.group(0)
    new = block
    for member, (old, want) in SWAP.items():
        pat = rf"(<map to=')({re.escape(old)})('>\s*<bucket>&quot;{re.escape(member)}&quot;</bucket>)"
        new, n = re.subn(pat, rf"\g<1>{want}\g<3>", new)
        if n != 1:
            sys.exit(f"FAIL: {member} matched {n} times, expected 1")
        print(f"  {member}: {old} -> {want}")
    t = t[: m.start()] + new + t[m.end() :]
    ET.fromstring(t)
    (D / dst).write_text(t, encoding="utf-8", newline="")
    print(f"  wrote {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 4: Run the edit, then the assertion and the checker**

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python task_cum_colour.py prod-base3.twb cum-1-colour.twb && \
  uv run python assert_cum_colour.py server/cum-1-colour.twb && \
  uv run python check_twb.py server/cum-1-colour.twb --ref server/prod-base3.twb
```

Expected: the edit prints both swaps, the assertion prints `OK`, the checker is
clean.

- [ ] **Step 5: Confirm the Academic Health twin is untouched**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight/server && python3 - <<'PY'
import re
t = open('cum-1-colour.twb', encoding='utf-8').read()
m = re.search(r"<encoding attr='color'[^>]*Calculation_4005670422418128910[^>]*>.*?</encoding>", t, re.S)
print(dict((b.replace('&quot;',''), to) for to, b in
           re.findall(r"<map to='([^']*)'>\s*<bucket>([^<]*)</bucket>", m.group(0))))
PY
```

Expected: `At or above goal` still `#2f5fc4`, `Below goal` still `#d8342f`.

- [ ] **Step 6: Commit**

Tick the boxes, then commit the plan with message
`docs(tableau): record the Cumulative goal colour repoint`.

---

### Task 3: Add the basis reminders

Nine text edits, no zone moves. The whole content layer becomes readable in a
render before any geometry changes.

Two flavours. Live means the parameter placeholder. Fixed means literal text.
Both use the same run formatting, copied from `GPA - BAN Below 3.0`:

```xml
<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'>Always projected</run>
```

**Files:**

- Create: `.claude/scratch/gpa-overnight/task_cum_reminders.py`
- Create: `.claude/scratch/gpa-overnight/assert_cum_reminders.py`
- Create: `.claude/scratch/gpa-overnight/server/cum-2-reminders.twb`

**Interfaces:**

- Consumes: `server/cum-1-colour.twb` from Task 2.
- Produces: `server/cum-2-reminders.twb`, consumed by Task 5.

The edits, exhaustively:

| Sheet                       | Where              | Content                                |
| --------------------------- | ------------------ | -------------------------------------- |
| `GPA - BAN % 3.5+`          | `customized-label` | live placeholder, new middle line      |
| `GPA - BAN % 3.0+`          | `customized-label` | live placeholder, new middle line      |
| `GPA - BAN Gap to goal`     | `customized-label` | split `Always projected` onto own line |
| `GPA - BAN Students needed` | `customized-label` | split `Always projected` onto own line |
| `GPA - Dist by grade`       | worksheet `title`  | live placeholder                       |
| `GPA - Goal by grade`       | worksheet `title`  | live placeholder                       |
| `GPA - Goal by school`      | worksheet `title`  | live placeholder                       |

`GPA - BAN Below 3.0` and `GPA - BAN Can reach` already carry the fixed line in
the right place and are not edited.

- [ ] **Step 1: Write the failing assertion**

Write `.claude/scratch/gpa-overnight/assert_cum_reminders.py`:

```python
"""Assert every basis-dependent panel states its basis."""

import re
import sys
from pathlib import Path

PLACEHOLDER = "<[Parameters].[Parameter 11]>"
FIXED = "Always projected"
STYLE = "fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'"

LIVE_LABEL = ["GPA - BAN % 3.5+", "GPA - BAN % 3.0+"]
LIVE_TITLE = ["GPA - Dist by grade", "GPA - Goal by grade", "GPA - Goal by school"]
FIXED_LABEL = ["GPA - BAN Below 3.0", "GPA - BAN Can reach",
               "GPA - BAN Gap to goal", "GPA - BAN Students needed"]


def sheet(t, name):
    i = t.index(f"<worksheet name='{name}'")
    return t[i : t.index("</worksheet>", i)]


def main(path):
    t = Path(path).read_text(encoding="utf-8")
    bad = 0
    for name in LIVE_LABEL:
        seg = sheet(t, name)
        lab = re.search(r"<customized-label>.*?</customized-label>", seg, re.S)
        if not lab or PLACEHOLDER not in lab.group(0):
            print(f"  FAIL {name}: no basis placeholder in customized-label")
            bad += 1
    for name in LIVE_TITLE:
        seg = sheet(t, name)
        ttl = re.search(r"<layout-options>.*?<title>.*?</title>.*?</layout-options>", seg, re.S)
        if not ttl or PLACEHOLDER not in ttl.group(0):
            print(f"  FAIL {name}: no basis placeholder in worksheet title")
            bad += 1
        elif not seg.lstrip().startswith("<worksheet") or seg.index("<layout-options>") > seg.index("<table>"):
            print(f"  FAIL {name}: layout-options must precede table")
            bad += 1
    for name in FIXED_LABEL:
        seg = sheet(t, name)
        lab = re.search(r"<customized-label>.*?</customized-label>", seg, re.S)
        runs = re.findall(r"<run ([^>]*)>([^<]*)</run>", lab.group(0)) if lab else []
        if not any(FIXED.lower() in text.lower() and STYLE in attrs for attrs, text in runs):
            print(f"  FAIL {name}: no standalone '{FIXED}' run in the standard style")
            bad += 1
    if bad:
        sys.exit(f"{bad} reminder failures")
    print(f"  OK: {len(LIVE_LABEL) + len(LIVE_TITLE)} live, {len(FIXED_LABEL)} fixed")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`cd /workspaces/teamster/.claude/scratch/gpa-overnight && uv run python assert_cum_reminders.py server/cum-1-colour.twb`

Expected: FAIL with 7 lines — 5 missing placeholders, and
`GPA - BAN Gap to goal` and `GPA - BAN Students needed` reported for having no
standalone fixed run.

- [ ] **Step 3: Write the edit**

Write `.claude/scratch/gpa-overnight/task_cum_reminders.py`. It performs three
distinct transforms. Every anchor must match exactly once; abort otherwise.

The break run, byte-exact, is `<run>Æ&#10;</run>`.

The live run to insert:

```xml
<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[Parameters].[Parameter 11]>]]></run>
```

The worksheet title block, inserted immediately after `<worksheet name='...'>`
and therefore before `<table>`, because the content model is
`((layout-options?|repository-location?), table, simple-id)`:

```xml
      <layout-options>
        <title>
          <formatted-text>
            <run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'><![CDATA[<[Parameters].[Parameter 11]>]]></run>
          </formatted-text>
        </title>
      </layout-options>
```

Transform A, for `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+`. Inside the sheet's
`<customized-label>`, find the first `<run>Æ&#10;</run>` — the break between the
13 point label and the 30 point number — and insert the live run plus a second
break run immediately after it. Result order: label, break, basis, break,
number.

Transform B, for `GPA - BAN Gap to goal` and `GPA - BAN Students needed`. Their
first run reads `Gap to goal, pts — always projected` and
`Students still needed — always projected`. Split each: truncate the first run's
text at the em dash, strip trailing whitespace, then insert a break run and a
fixed run reading `Always projected` in the standard style. Match the em dash as
the literal character `—`, not a hyphen.

Transform C, for the three body sheets. Insert the title block after
`<worksheet name='...'>`. All three currently have no `<layout-options>`; assert
that before inserting, and abort if one appears.

Preserve CRLF: detect the newline from the source text and use it in every
inserted line. Parse with `ET.fromstring` before writing. Write with
`newline=""`.

- [ ] **Step 4: Run the edit, the assertion and the checker**

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python task_cum_reminders.py cum-1-colour.twb cum-2-reminders.twb && \
  uv run python assert_cum_reminders.py server/cum-2-reminders.twb && \
  uv run python check_twb.py server/cum-2-reminders.twb --ref server/prod-base3.twb
```

Expected: assertion prints `OK: 5 live, 4 fixed`, checker clean.

- [ ] **Step 5: Confirm the break run survived byte-exact**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight/server && \
  grep -c '<run>Æ&#10;</run>' prod-base3.twb cum-2-reminders.twb
```

Expected: the second count is higher than the first by exactly the number of
break runs the edit added, and no other value. Record both numbers.

- [ ] **Step 6: Commit**

Tick the boxes, then commit the plan with message
`docs(tableau): record the Cumulative basis reminders`.

---

### Task 4: Build the geometry checker

The card restructure re-parents nine zones. No existing checker catches a zone
at the wrong nesting level, which is valid XML that renders as an overlap. Write
the checker before the change it guards.

**Files:**

- Create: `.claude/scratch/gpa-overnight/check_geometry.py`

**Interfaces:**

- Consumes: any `.twb` path plus a dashboard name.
- Produces: `check_geometry.py`, run by Task 5 and Task 6. Exits non-zero on any
  violation.

- [ ] **Step 1: Write the checker**

Write `.claude/scratch/gpa-overnight/check_geometry.py`:

```python
"""Assert dashboard zone geometry is internally consistent.

Three invariants, none of which any schema check covers:

1. Siblings in a layout-flow do not overlap.
2. A flow container's children sum to the container along the flow axis.
3. The top-level zone spans the full 100000-unit canvas.

Usage: uv run python check_geometry.py <twb> "<dashboard name>"
"""

import sys
import xml.etree.ElementTree as ET

TOL = 40  # units; 100000 units is 900px, so 40 units is under half a pixel


def rect(z):
    return tuple(int(z.get(k, 0)) for k in ("x", "y", "w", "h"))


def overlaps(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def walk(z, path, bad):
    kids = [c for c in z.findall("zone") if not c.get("hidden-by-user")]
    for i, a in enumerate(kids):
        for b in kids[i + 1 :]:
            if overlaps(rect(a), rect(b)):
                bad.append(f"overlap at {path}: zone {a.get('id')} and zone {b.get('id')}")
    flow = z.get("param")
    if kids and z.get("type-v2") == "layout-flow" and flow in ("vert", "horz"):
        idx = 3 if flow == "vert" else 2
        total = sum(rect(c)[idx] for c in kids)
        want = rect(z)[idx]
        if abs(total - want) > TOL * len(kids):
            bad.append(
                f"children of zone {z.get('id')} ({flow}) sum to {total}, parent is {want}"
            )
    for c in kids:
        walk(c, f"{path}/{z.get('id')}", bad)


def main(path, dashboard):
    root = ET.parse(path).getroot()
    dash = next(d for d in root.find("dashboards") if d.get("name") == dashboard)
    bad = []
    tops = dash.find("zones").findall("zone")
    for z in tops:
        if z.get("hidden-by-user"):
            continue
        x, y, w, h = rect(z)
        if (x, y, w, h) != (0, 0, 100000, 100000) and z.get("type-v2") == "layout-basic":
            bad.append(f"top-level layout-basic zone {z.get('id')} is {x},{y},{w},{h}")
        walk(z, "", bad)
    for line in bad:
        print(f"  FAIL {line}")
    if bad:
        sys.exit(f"{len(bad)} geometry failures in '{dashboard}'")
    print(f"  OK: geometry consistent in '{dashboard}'")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Prove it passes on known-good input**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python check_geometry.py server/prod-base3.twb "Cumulative GPA Monitor" && \
  uv run python check_geometry.py server/prod-base3.twb "Academic Health Home"
```

Expected: both print `OK`. A checker that fails on production is a broken
checker, not a finding — fix the checker.

- [ ] **Step 3: Prove it catches a real fault**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && python3 - <<'PY'
import re, pathlib
p = pathlib.Path('server/prod-base3.twb')
t = p.read_text(encoding='utf-8')
i = t.index("<dashboard enable-sort-zone-taborder='true' name='Cumulative GPA Monitor'>")
j = t.index("<zone h='15333'", i)
broken = t[:j] + t[j:].replace("<zone h='15333'", "<zone h='45333'", 1)
pathlib.Path('server/zz-broken.twb').write_text(broken, encoding='utf-8', newline='')
print('wrote server/zz-broken.twb')
PY
uv run python check_geometry.py server/zz-broken.twb "Cumulative GPA Monitor"; echo "exit=$?"
rm -f server/zz-broken.twb
```

Expected: non-zero exit with at least one `FAIL` line. A checker that passes the
broken file is useless — fix it and repeat.

- [ ] **Step 4: Commit**

Tick the boxes, then commit the plan with message
`docs(tableau): record the dashboard geometry checker`.

---

### Task 5: Restructure into cards with header strips

The riskiest task, deliberately last among the edits.

**Files:**

- Create: `.claude/scratch/gpa-overnight/task_cum_cards.py`
- Create: `.claude/scratch/gpa-overnight/assert_cum_cards.py`
- Create: `.claude/scratch/gpa-overnight/server/cum-3-cards.twb`

**Interfaces:**

- Consumes: `server/cum-2-reminders.twb` from Task 3, `check_geometry.py` from
  Task 4.
- Produces: `server/cum-3-cards.twb`, consumed by Task 6.

Target structure. Existing zone ids in the Cumulative GPA Monitor: title strip
5, controls 10, headline 20 holding BANs 124, 120, 121, 122; goal strip 30
holding text 130 and BANs 131, 132; body 35 holding body-left 40 (sheets 141,
142, legend 143, 144) and body-right 50 (sheets 151, 152). New zones take ids
from 800 up, which are unused.

```text
zone 4  layout-basic        margin 8                       (edit: add margin)
  zone 3  layout-flow vert
    zone 5   Title                                          (unchanged)
    zone 10  Controls        background-color #f5f5f5       (edit)
    zone 20  Headline        border #001e62 1pt, margin 5   (edit: card)
    zone 30  Goal strip      border #001e62 1pt, margin 5   (edit: card)
    zone 35  Body
      zone 40  Body left     border #001e62 1pt, margin 5   (edit: card)
        zone 800 header strip  bg #e6e6e6                   (new)
          zone 801 text                                     (new)
        zone 141                                            (unchanged)
        zone 142                                            (unchanged)
        zone 810 header strip  bg #e6e6e6                   (new)
          zone 811 text                                     (new)
          zone 143 legend                                   (moved in)
        zone 144                                            (unchanged)
      zone 50  Body right    border #001e62 1pt, margin 5   (edit: card)
        zone 820 header strip  bg #e6e6e6                   (new)
          zone 821 text                                     (new)
        zone 151                                            (unchanged)
        zone 830 header strip  bg #e6e6e6                   (new)
          zone 831 text                                     (new)
        zone 152                                            (unchanged)
```

Header strip template. Substitute the id, geometry, title and caption:

```xml
              <zone fixed-size='40' h='{H}' id='{SID}' is-fixed='true' param='horz' type-v2='layout-flow' w='{W}' x='{X}' y='{Y}'>
                <zone fixed-size='40' forceUpdate='true' h='{H}' id='{TID}' is-fixed='true' type-v2='text' w='{W}' x='{X}' y='{Y}'>
                  <formatted-text>
                    <run bold='true' fontcolor='#000000' fontname='Arial'>{TITLE}</run>
                    <run>Æ&#10;</run>
                    <run fontcolor='#000000' fontname='Arial' fontsize='8' italic='true'>{CAPTION}</run>
                  </formatted-text>
                  <zone-style>
                    <format attr='border-color' value='#000000' />
                    <format attr='border-style' value='none' />
                    <format attr='border-width' value='0' />
                    <format attr='margin' value='4' />
                  </zone-style>
                </zone>
                <zone-style>
                  <format attr='border-color' value='#000000' />
                  <format attr='border-style' value='none' />
                  <format attr='border-width' value='0' />
                  <format attr='background-color' value='#e6e6e6' />
                </zone-style>
              </zone>
```

Card style, appended to zones 20, 30, 40 and 50, replacing their existing
`zone-style` if present:

```xml
                <zone-style>
                  <format attr='border-color' value='#001e62' />
                  <format attr='border-style' value='solid' />
                  <format attr='border-width' value='1' />
                  <format attr='margin' value='5' />
                </zone-style>
```

Content model reminder:
`zone = (formatted-text, layout-cache?, zone, flipboard, zone-style?)`. Child
zones come before the container's own `zone-style`. The container's style
indents 14 spaces and its children's 16.

Title and caption strings, verbatim:

| Strip | Title                          | Caption                                                                                                        |
| ----- | ------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| 800   | `Band mix, network`            | `On the books today above, projected to year end below. This panel shows both, whatever the switch is set to.` |
| 810   | `Band mix by grade`            | `The same bands, split by grade.`                                                                              |
| 820   | `% at 3.0+ by grade`           | `Share of students at a 3.0 cumulative or better. The grey tick is the network goal for that grade.`           |
| 830   | `Gap to goal, school by grade` | `Bar length is % at 3.0+; the label is the gap in points; the grey tick is that school's own goal.`            |

Zone 130's existing text run gets a caption line appended in the same style, so
the goal strip reads `Progress against the goal` over
`Always projected, against the network goal — or the selected region's goal.`

One more edit, outside the zone tree. The `GPA - Title` worksheet's `<caption>`
currently ends with the hedge
`Projected end-of-year unless the basis switch is set to on the books today.`
Every panel now states its own basis, so delete that sentence and leave the rest
of the caption intact. Assert the remaining caption still starts
`Cumulative unweighted GPA against each grade's goal`.

Height budget, in the 100000-unit space where 1 pixel is 111.11 units. Set these
`h` values and recompute every `y` beneath them:

| Zone                      | Old h   | New h   | Pixels    |
| ------------------------- | ------- | ------- | --------- |
| 30 goal strip             | `8667`  | `7333`  | 78 → 66   |
| 35 body                   | `61777` | `63111` | 556 → 568 |
| 40 body left, 50 right    | `60889` | `62222` | 548 → 560 |
| 800, 810, 820, 830 strips | —       | `4444`  | 0 → 40    |
| 141, 142                  | `9556`  | `6889`  | 86 → 62   |
| 143 legend                | `4222`  | `4222`  | 38, moved |
| 144                       | `36667` | `35111` | 330 → 316 |
| 151                       | `15668` | `13333` | 141 → 120 |
| 152                       | `44333` | `36000` | 399 → 324 |

Body left children then sum to `4444 + 6889 + 6889 + 4444 + 35111 = 57777`, plus
the legend `4222` nested inside strip 810, giving `62222` less margins. Body
right sums to `4444 + 13333 + 4444 + 36000 = 58221`. Reconcile both against the
parent before writing, and let `check_geometry.py` be the judge.

- [ ] **Step 1: Write the failing assertion**

Write `.claude/scratch/gpa-overnight/assert_cum_cards.py`. It asserts, against
the `Cumulative GPA Monitor` dashboard:

- Zones 20, 30, 40 and 50 each carry `border-style` `solid`, `border-color`
  `#001e62`, `border-width` `1`.
- Zones 800, 810, 820 and 830 exist, are `layout-flow` with `param='horz'`, and
  carry `background-color` `#e6e6e6`.
- Zones 801, 811, 821 and 831 exist, are `type-v2='text'`, and each contains
  exactly 3 runs whose second is the byte-exact break run.
- The four title strings and four caption strings appear exactly once each.
- Zone 143 is a descendant of zone 810, not of zone 40 directly.
- Zone 4 carries `margin` `8`; zone 10 carries `background-color` `#f5f5f5`.
- In every `zone-style`, no child `zone` element follows it within the same
  parent.

- [ ] **Step 2: Run it to verify it fails**

Run:
`cd /workspaces/teamster/.claude/scratch/gpa-overnight && uv run python assert_cum_cards.py server/cum-2-reminders.twb`

Expected: FAIL on every assertion above.

- [ ] **Step 3: Write the edit**

Write `.claude/scratch/gpa-overnight/task_cum_cards.py`, operating only within
the `Cumulative GPA Monitor` dashboard element and only on its `<zones>` block,
not the `<devicelayouts>` copy.

Guard against the variable-shadowing bug that truncated a workbook from 1.45M to
143k characters on 2026-09-08: never reuse the name of an outer regex match
object inside a loop. Assert the output length is within 20 percent of the input
length before writing.

Assert every anchor matches exactly once. Parse with `ET.fromstring` before
writing. Write with `newline=""`.

- [ ] **Step 4: Run the edit and all three checkers**

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python task_cum_cards.py cum-2-reminders.twb cum-3-cards.twb && \
  uv run python assert_cum_cards.py server/cum-3-cards.twb && \
  uv run python assert_cum_reminders.py server/cum-3-cards.twb && \
  uv run python assert_cum_colour.py server/cum-3-cards.twb && \
  uv run python check_geometry.py server/cum-3-cards.twb "Cumulative GPA Monitor" && \
  uv run python check_geometry.py server/cum-3-cards.twb "Academic Health Home" && \
  uv run python check_twb.py server/cum-3-cards.twb --ref server/prod-base3.twb
```

Expected: all seven clean. The two earlier assertions re-run here to prove the
restructure did not undo them.

- [ ] **Step 5: Confirm nothing else moved**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight/server && python3 - <<'PY'
import re
a = open('prod-base3.twb', encoding='utf-8').read()
b = open('cum-3-cards.twb', encoding='utf-8').read()
print(f"length: {len(a)} -> {len(b)}")
for label, pat in (("worksheets", r"<worksheet name='([^']*)'"),
                   ("parameters", r"name='(\[Parameter \d+\])'")):
    sa, sb = set(re.findall(pat, a)), set(re.findall(pat, b))
    print(f"{label}: {len(sa)} -> {len(sb)}  gone={sorted(sa-sb)}  new={sorted(sb-sa)}")
print("school filter zones:", len(re.findall(r"filter-group='17'", a)), "->",
      len(re.findall(r"filter-group='17'", b)))
for name in ("Academic Health Home", "Academic Health Schools", "Gradebook School Rollup"):
    ia = a.index(f"name='{name}'>"); ib = b.index(f"name='{name}'>")
    ja = a.index("</dashboard>", ia); jb = b.index("</dashboard>", ib)
    print(f"{name}: {'UNCHANGED' if a[ia:ja] == b[ib:jb] else 'CHANGED'}")
PY
```

Expected: no worksheets or parameters gone, `filter-group='17'` count unchanged,
and all three other dashboards `UNCHANGED`.

- [ ] **Step 6: Commit**

Tick the boxes, then commit the plan with message
`docs(tableau): record the Cumulative card restructure`.

---

### Task 6: Repack, render and hand over

**Files:**

- Create: `.claude/scratch/gpa-overnight/server/cum-final.twbx`
- Create: `tests/tableau/test_zz_review.py` (throwaway, deleted in step 5)

**Interfaces:**

- Consumes: `server/cum-3-cards.twb` from Task 5, `server/prod-base3.twbx` from
  Task 0.
- Produces: `server/cum-final.twbx`, the handover package, and a review copy in
  `GPA-monitor-temp`.

- [ ] **Step 1: Repack around the production extract**

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && \
  uv run python repack_task.py server/cum-3-cards.twb prod-base3.twbx cum-final.twbx && \
  ls -l server/cum-final.twbx
```

Expected: over 20 MB. A file in the hundreds of kilobytes means the extract was
dropped — stop.

- [ ] **Step 2: Publish the review copy and render both bases**

Write with the Write tool to `tests/tableau/test_zz_review.py`, copying the
structure of the Task 1 probe but publishing `cum-final.twbx` as
`ZZ-REVIEW cum cards 20260908` and rendering `Cumulative GPA Monitor` at both
`GPA basis` values plus `Academic Health Home` once.

Write the renders to exactly these paths, which later steps read by name:
`server/review-projected.png`, `server/review-onthebooks.png`,
`server/review-acadhealth.png`.

Assert `item.project_id` equals `c74d8e08-b856-4430-a759-ebacb061e376` after
publish, before rendering. Print the project name.

Run: `uv run pytest tests/tableau/test_zz_review.py -s`

- [ ] **Step 3: Assert the rendered colours by pixel, not by eye**

Run:

```bash
cd /workspaces/teamster/.claude/scratch/gpa-overnight && uv run --with pillow python - <<'PY'
from collections import Counter
from PIL import Image
img = Image.open('server/review-projected.png').convert('RGB')
w, h = img.size
crop = img.crop((int(w * 0.60), int(h * 0.55), w, h))          # goal-by-school panel
counts = Counter(crop.getdata())
def near(target, tol=12):
    r0, g0, b0 = tuple(int(target[i:i+2], 16) for i in (1, 3, 5))
    return sum(n for (r, g, b), n in counts.items()
               if abs(r-r0) <= tol and abs(g-g0) <= tol and abs(b-b0) <= tol)
for name, hexv in (("green #12a47c", "#12a47c"), ("red #b3161c", "#b3161c"),
                   ("OLD blue #2f5fc4", "#2f5fc4"), ("OLD red #d8342f", "#d8342f")):
    print(f"  {name}: {near(hexv)} px")
PY
```

Expected: the two new colours have thousands of pixels each; the two retired
colours have none, or a negligible count from anti-aliasing against the band
chart. If a retired colour shows thousands, the edit missed a sheet.

- [ ] **Step 4: Read both renders and check the text**

Open `server/review-projected.png` and `server/review-onthebooks.png` with the
Read tool. Confirm, in both:

- Four card borders are visible, and each header strip shows its title and
  caption.
- The four headline numbers each show a basis line.
- The three body charts each show a basis line, and it differs between the two
  images.
- The goal strip shows `Always projected` on both numbers in both images.
- No text is clipped, no panel overlaps another, and the dashboard title is not
  cut off at the top.

Also open the Academic Health Home render and confirm it is unchanged, including
its blue and red goal bars.

- [ ] **Step 5: Delete the throwaway, record and hand over**

```bash
rm -f /workspaces/teamster/tests/tableau/test_zz_review.py
```

Append a `**Result:**` block under this task recording the review workbook URL,
the pixel counts, and anything the renders showed that the checkers did not.

Commit the plan with message
`docs(tableau): record the Cumulative monitor rebuild verification`.

Then report to the user, in the terminal:

- The path to `server/cum-final.twbx` and its size.
- The review copy's URL in `GPA-monitor-temp`.
- An explicit statement that nothing was published to `Production` and that the
  production publish is theirs to run.

- [ ] **Step 6: Open the pull request**

Push the branch and open a PR from `.github/pull_request_template.md`, with
`Closes #5190` in the body. The PR carries the spec and the plan; the workbook
itself is not in the repository, so say so in the body and link the review copy.
