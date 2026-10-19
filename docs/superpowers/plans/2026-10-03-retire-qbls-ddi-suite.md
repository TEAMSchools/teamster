# Retire QBLs and Power Standards from the DDI Suite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every QBL and Power Standards dependency from dbt, Dagster and
the DDI Suite Tableau workbook without breaking any live DDI Suite view.

**Architecture:** Three gated steps:

1. dbt PR 1 swaps `qbl` and `is_qbl` for typed constant placeholders, so the
   output schema does not change.
2. A text-surgery edit of the workbook XML removes every QBL and Power Standards
   field, option and object. It is verified by assertions, mutants, the skill's
   checkers and renders. The owner then opens it in Tableau Desktop and
   publishes to production from there.
3. dbt PR 2 drops the four columns and disables the staging model and its Sheets
   source.

**Tech Stack:** dbt (BigQuery), Dagster, Tableau Server REST via
`tableauserverclient`, Python text surgery over `.twb` XML.

**Spec:** `docs/superpowers/specs/2026-10-03-retire-qbls-ddi-suite-design.md`
(read the 2026-10-03 revision at its end: production publish and the
extract-refresh check moved to the owner's Desktop session).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite`,
  branch `anthonygwalters/chore/claude-retire-qbls-ddi-suite`. Use
  `git -C <worktree>` and absolute paths on every call.
- dbt runs as `uv run dbt <cmd> --project-dir <worktree>/src/dbt/kipptaf`, never
  bare `dbt`. Before the first build, invoke the `dbt-local-dev` skill.
- Workbook: production DDI Suite, LUID `6d82b643-59a8-4106-b2f9-97ddf7f638e7`.
  The inventory and every expected count below come from the revision updated
  2026-10-02 22:33 UTC.
- Workbook edits are text surgery only. Read and write with
  `encoding="utf-8", newline=""`. The file is CRLF throughout and must stay
  CRLF.
- Never publish to the production project from this plan. The owner publishes
  production from Tableau Desktop (Task 5).
- Review copies go to the non-production project the user names. Default:
  `GPA-monitor-temp`, `c74d8e08-b856-4430-a759-ebacb061e376`. The name is
  `ZZ-REVIEW <YYYY-MM-DD> DDI Suite`.
- Do not touch the `Assessments` spreadsheet. Do not drop any BigQuery relation.
- Credentialed Tableau calls run in a throwaway `tests/test_zz_*.py` in the MAIN
  checkout under `uv run pytest -s`. Delete the file at the end of its task.
- No student-level values in commits, PR bodies or issue comments. Aggregates by
  academic year only.

## Review Focus

1. **A saved custom view or bookmark with "Standard or QBL" or a Mastery Type
   set to QBLs.** It should open on the default value and not error. Covered in
   Task 4, which lists custom views and renders each one that touches an edited
   dashboard.
2. **The Mastery Type dropdown's remaining values (Overall, Standards,
   Walkthroughs; Classroom: Overall, Percent Correct, Standards).** Each should
   render the same as production. Covered in Task 4, which renders every value,
   base and edit.
3. **Mastery Over Time [Classroom] actions (Bars to Roster, Lines to bars, Lines
   to Roster) after their exclude lists change.** Clicking a bar or line should
   still filter Mastery Roster. A render cannot click, so the owner checks this
   in Task 5.
4. **Phone layouts of O3 View, DKI View and the three Mastery Over Time
   dashboards.** Rendering uses the default layout. Task 3's assertions pin the
   phone-layout zone lists, and the owner checks Device Preview in Task 5.
5. **The extract after the field list shrinks.** A full extract refresh should
   succeed, and the four retired fields should not reappear. The owner runs a
   full refresh in Desktop in Task 5, and Task 7 checks the first production
   refresh after PR 2.

---

### Task 1: dbt PR 1 — placeholder columns

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`
  (ES/MS branch lines 263, 277, 284-292; HS branch lines 371, 381, 388-394;
  walkthrough branch lines 502, 509)
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ddi_dashboard.yml`
  (columns `qbl`, `is_qbl`)

**Interfaces:**

- Produces: prod `kipptaf_tableau.rpt_tableau__ddi_dashboard` with the same
  column names, order and types. `qbl` is always NULL STRING and `is_qbl` is
  always FALSE. Tasks 2-5 rely on the schema being unchanged.

- [ ] **Step 1: Record the prod baseline**

Run with the BigQuery MCP `execute_sql_readonly` (project `teamster-332318`):

```sql
select
    academic_year,
    count(*) as n_rows,
    countif(is_qbl) as n_qbl_true,
    count(qbl) as n_qbl_nonnull,
from `teamster-332318.kipptaf_tableau.rpt_tableau__ddi_dashboard`
group by academic_year
```

Expected: one row per academic year, and `n_qbl_true = 0` and
`n_qbl_nonnull = 0` on every row (2026-10-03: 2025 had 2,142,859 rows and 2026
had 281,379). Save the result. Step 6 compares against it.

```sql
select column_name, data_type, ordinal_position
from `teamster-332318.kipptaf_tableau.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'rpt_tableau__ddi_dashboard'
order by ordinal_position
```

Save the list.

- [ ] **Step 2: Edit the ES/MS branch**

Replace this in the select list (the union matches columns by position, so the
placeholder takes the same slot):

```sql
    co.is_low_25_fl,

    qbls.qbl,

    g.grade_goal,
```

with:

```sql
    co.is_low_25_fl,

    cast(null as string) as qbl,

    g.grade_goal,
```

Replace:

```sql
    if(qbls.qbl is not null, true, false) as is_qbl,

    coalesce(ip.is_pass_2_lessons_int_reading, 0) as is_passed_iready_2plus_reading_int,
```

with:

```sql
    false as is_qbl,

    coalesce(ip.is_pass_2_lessons_int_reading, 0) as is_passed_iready_2plus_reading_int,
```

Delete the join:

```sql
left join
    {{ ref("stg_google_sheets__assessments__qbls_power_standards") }} as qbls
    on co.academic_year = qbls.academic_year
    and co.term = qbls.term_name
    and co.region = qbls.region
    and co.grade_level = qbls.grade_level
    and co.response_type_code = qbls.standard_code
    and co.subject_area = qbls.illuminate_subject_area
    and qbls.qbl is not null
```

- [ ] **Step 3: Edit the HS branch**

Same pattern. Replace `    qbls.qbl,` (after `co.is_low_25_fl,`) with
`    cast(null as string) as qbl,`, and
`    if(qbls.qbl is not null, true, false) as is_qbl,` with
`    false as is_qbl,`. Delete the join:

```sql
left join
    {{ ref("stg_google_sheets__assessments__qbls_power_standards") }} as qbls
    on co.academic_year = qbls.academic_year
    and co.term = qbls.term_name
    and co.region = qbls.region
    and co.response_type_code = qbls.standard_code
    and co.subject_area = qbls.illuminate_subject_area
```

- [ ] **Step 4: Edit the walkthrough branch**

Replace `    null as qbl,` with `    cast(null as string) as qbl,` and
`    null as is_qbl,` with `    false as is_qbl,`.

Check:
`rg -n 'qbl' <worktree>/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`.
Expected exactly 6 lines: 3 × `cast(null as string) as qbl,` and 3 ×
`false as is_qbl,`.

- [ ] **Step 5: Describe the two columns in the properties YAML**

In `properties/rpt_tableau__ddi_dashboard.yml`, replace:

```yaml
- name: qbl
  data_type: string
```

with:

```yaml
- name: qbl
  data_type: string
  description:
    Always null. QBLs are a retired assessment program; the column stays only so
    the DDI Suite workbook's field list does not change.
```

and:

```yaml
- name: is_qbl
  data_type: boolean
```

with:

```yaml
- name: is_qbl
  data_type: boolean
  description:
    Always false. QBLs are a retired assessment program; the column stays only
    so the DDI Suite workbook's field list does not change.
```

Keep the indentation the file already uses for its `columns:` entries.

- [ ] **Step 6: Build in dev and compare with prod**

Invoke the `dbt-local-dev` skill first. Then, in separate Bash calls:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite/src/dbt/kipptaf
```

```bash
uv run dbt build --select rpt_tableau__ddi_dashboard --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --project-dir /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite/src/dbt/kipptaf 2>&1 | tail -n 30
```

Expected: `PASS=` on the model and its tests, `ERROR=0`. Read the dev relation
name off the log line `create or replace ... rpt_tableau__ddi_dashboard` (the
dataset is `zz_<GITHUB_USER>_kipptaf_tableau`). Run the Step 1 queries against
that dataset. Expected:

- Row counts per `academic_year` match Step 1 exactly.
- `n_qbl_true` and `n_qbl_nonnull` are 0.
- The column list (name, type, position) is identical to Step 1's.

A row-count difference can come from prod being rebuilt between the two queries.
Re-run the prod query before concluding anything. If they still differ, stop and
report.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ddi_dashboard.yml </dev/null 2>&1 | tail -n 30
```

Expected: `No issues`. If sqlfluff ST06 flags `cast(null as string) as qbl` or
`false as is_qbl`: the union fixes their positions, so suppress it with
`-- trunk-ignore(sqlfluff/ST06): union branches match by position` on the line
above. Never reorder.

- [ ] **Step 8: Commit, push, open PR 1**

```bash
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite add -u
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite commit -F <scratchpad>/commit-msg-qbl-pr1.txt
git -C /workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-retire-qbls-ddi-suite push origin HEAD
```

Commit message:
`refactor(dbt): replace qbl lookup in rpt_tableau__ddi_dashboard with constant placeholders`.
The body says the output is unchanged and gives the Step 6 evidence. End it with
the Co-Authored-By line. Open the PR with `mcp__github__create_pull_request`:

- Body from `.github/pull_request_template.md`.
- `Refs #5656`, not `Closes`, because Tasks 2-7 remain.
- The summary says no prod output changes and that the spec ships in the same
  PR.
- Verify the returned title and body.
- Offer to watch CI per `pr-ci-review`.

---

### Task 2: Workbook — fresh pull and drift check

**Files (all gitignored scratch in the MAIN checkout):**

- Create: `/workspaces/teamster/tests/test_zz_ddi_suite_pull.py` (deleted at the
  end of this task)
- Output:
  `/workspaces/teamster/.claude/scratch/tableau/ddi_suite/fresh/base.twbx`,
  `.../fresh/base.twb`

**Interfaces:**

- Produces: `fresh/base.twb` and `fresh/base.twbx`, the unedited production
  workbook, plus `UPDATED` (its `updated_at`). Tasks 3-4 use these as base and
  donor.

- [ ] **Step 1: Write the pull test**

```python
import os
import zipfile
from pathlib import Path

import tableauserverclient as tsc

OUT = Path(__file__).resolve().parents[1] / ".claude" / "scratch" / "tableau" / "ddi_suite" / "fresh"
OUT.mkdir(parents=True, exist_ok=True)
LUID = "6d82b643-59a8-4106-b2f9-97ddf7f638e7"


def test_pull() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        wb = server.workbooks.get_by_id(LUID)
        print(f"PROJECT: {wb.project_name}")
        print(f"UPDATED: {wb.updated_at}")
        print(f"SHOW_TABS: {wb.show_tabs}")
        server.workbooks.populate_views(wb)
        for v in wb.views:
            print(f"VIEW: {v.name}")
        got = Path(server.workbooks.download(LUID, filepath=str(OUT / "base"), include_extract=True))
    twbx = OUT / "base.twbx"
    if got != twbx:
        got.replace(twbx)
    if twbx.stat().st_size < 20_000_000:
        raise RuntimeError(f"extract missing: only {twbx.stat().st_size} bytes")
    with zipfile.ZipFile(twbx) as z:
        name = next(n for n in z.namelist() if n.endswith(".twb"))
        (OUT / "base.twb").write_bytes(z.read(name))
```

- [ ] **Step 2: Run it**

```bash
uv run pytest /workspaces/teamster/tests/test_zz_ddi_suite_pull.py -s -q -p no:cacheprovider 2>&1 | tail -n 20
```

Expected: `1 passed`, `PROJECT: Production`, and these 8 VIEW lines:
`Landing Page`, `Mastery Over Time [Region]`, `Mastery Over Time [School]`,
`Mastery Over Time [Classroom]`, `O3 View`, `DKI View`, `Module Dashboard`,
`Assessment Dashboard`. Record `UPDATED` and `SHOW_TABS`.

- [ ] **Step 3: Check for drift**

If `UPDATED` is `2026-10-02 22:33:40+00:00`, the base matches the inventory and
every count in Task 3 applies. If it is later, run Task 3 Step 3 with `--survey`
first. Any `MISMATCH` line means the owner changed something this plan's counts
depend on. Show the user the mismatches and stop. Never edit a count to make a
new base pass without understanding what changed.

- [ ] **Step 4: Run the skill checkers on the untouched base**

```bash
cd /workspaces/teamster && b=.claude/scratch/tableau/ddi_suite/fresh/base.twb; uv run python docs/tableau-xml/scripts/check_twb.py $b --ref $b >/tmp/claude-1000/ddi_c0.txt 2>&1; echo "rc=$?"; tail -n 5 /tmp/claude-1000/ddi_c0.txt
```

Expected `rc=0`. Then, for each of the five dashboards in Task 3 Step 6, run
`check_geometry.py` with `--baseline` set to the same file. Expected: rc 0 for
four of them. `O3 View` has rc 1 with exactly one failure,
`FAIL overlap at top-level: zone 156 and zone 3`, which exists in production
today. Record it.

- [ ] **Step 5: Delete the pull test**

```bash
rm /workspaces/teamster/tests/test_zz_ddi_suite_pull.py
```

---

### Task 3: Workbook — edit, assert, check, mutate

**Files (scratch, main checkout):**

- Create:
  `/workspaces/teamster/.claude/scratch/tableau/ddi_suite/edit_ddi_qbl.py`
- Create:
  `/workspaces/teamster/.claude/scratch/tableau/ddi_suite/check_ddi_qbl.py`
- Output: `.../ddi_suite/fresh/final.twb`, `.../ddi_suite/fresh/final.twbx`

**Interfaces:**

- Consumes: `fresh/base.twb`, `fresh/base.twbx` (Task 2).
- Produces: `fresh/final.twbx`, the edited workbook with the base's extract.
  Task 4 publishes it and Task 5 hands it to the owner.

- [ ] **Step 1: Write the assertion script**

Save as `check_ddi_qbl.py`:

```python
"""Assert the DDI Suite QBL/Power Standards retirement is complete and contained.

Usage: uv run python check_ddi_qbl.py <candidate.twb> <base.twb>
Exit 0 only when every check passes. Must FAIL when candidate == base.
"""

import re
import sys
import xml.etree.ElementTree as ET

QBL_SHEETS = {
    "Region - QBL Mastery",
    "School - QBL Mastery",
    "Classroom - QBL Mastery",
    "Classroom - QBL",
}
EDITED_DASHBOARDS = {
    "Mastery Over Time [Region]",
    "Mastery Over Time [School]",
    "Mastery Over Time [Classroom]",
    "O3 View",
    "DKI View",
}
DELETED_ZONES = {  # dashboard -> zone ids removed (main and device layouts)
    "Mastery Over Time [Region]": {"306", "373", "375", "456", "359", "312"},
    "Mastery Over Time [School]": {"306", "309", "311", "310", "307", "312"},
    "Mastery Over Time [Classroom]": {"380", "360", "379", "387"},
    "O3 View": {"29"},
    "DKI View": {"16"},
}
NEW_WIDTHS = {  # dashboard -> (zone id, base w, new w): main layout only
    "Mastery Over Time [Region]": ("106", "64788", "75659"),
    "Mastery Over Time [School]": ("106", "64788", "75184"),
    "Mastery Over Time [Classroom]": ("377", "64568", "75549"),
    "O3 View": ("76", "31406", "49268"),
    "DKI View": ("59", "75988", "98535"),
}
FORBIDDEN = re.compile(
    r"qbl|power.?standard|\[Parameter 9\]|Calculation_1835568692093849600|Calculation_1835568692096798721",
    re.I,
)
FORMULAS = {
    "[Calculation_5386727405806911490]": "IF [Parameters].[Parameter 3 1] = 'Overall' THEN \n    IF [response_type] = 'overall' then [is_mastery_int] END\nELSEIF [Parameters].[Parameter 3 1] = 'Standards' THEN\n    IF [response_type] = 'standard' then [is_mastery_int] END\nELSEIF [Parameters].[Parameter 3 1] = 'Walkthroughs' THEN\n    [Calculation_2059270969708253185]\nEND",
    "[Is Mastery Int - Custom (copy)_3457427549108834305]": "IF [Parameters].[Mastery Type - Parameter (copy)_3457427549106843648] = 'Overall' THEN \n    IF [response_type] = 'overall' then [is_mastery_int] END\nELSEIF [Parameters].[Mastery Type - Parameter (copy)_3457427549106843648] = 'Standards' THEN\n    IF [response_type] = 'standard' then [is_mastery_int] END\nELSEIF [Parameters].[Mastery Type - Parameter (copy)_3457427549106843648] = 'Percent Correct' THEN\n    [Percent Correct - Float (copy)_3419569134667223040]\nEND",
    "[Calculation_5298273899702345730]": "[Calculation_5298273899702894595]",
}
MEMBERS = {
    "[Parameter 3 1]": ['"Overall"', '"Standards"', '"Walkthroughs"'],
    "[Mastery Type - Parameter (copy)_3457427549106843648]": ['"Overall"', '"Percent Correct"', '"Standards"'],
}

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    if not ok:
        failures.append(msg)


def dashboards(root: ET.Element) -> dict[str, ET.Element]:
    return {d.get("name"): d for d in root.find("dashboards")}


def zone_ids(d: ET.Element, part: str) -> list[str]:
    block = d.find(part)
    return [] if block is None else [z.get("id") for z in block.iter("zone")]


def runs(d: ET.Element, zid: str) -> list[str]:
    z = next(z for z in d.find("zones").iter("zone") if z.get("id") == zid)
    return [r.text or "" for r in z.iter("run")]


def main(cand_path: str, base_path: str) -> None:
    raw = open(cand_path, encoding="utf-8", newline="").read()
    base_raw = open(base_path, encoding="utf-8", newline="").read()
    cand, base = ET.fromstring(raw), ET.fromstring(base_raw)

    hits = sorted(set(m.group(0) for m in FORBIDDEN.finditer(raw)))
    check(not hits, f"retired tokens remain: {hits}")
    check(raw.count("\n") == raw.count("\r\n"), "bare LF present")

    ws = {w.get("name") for w in cand.find("worksheets")}
    base_ws = {w.get("name") for w in base.find("worksheets")}
    check(ws == base_ws - QBL_SHEETS, f"worksheet set wrong: missing {sorted(base_ws - QBL_SHEETS - ws)}, extra {sorted(ws - (base_ws - QBL_SHEETS))}")

    dc, db = dashboards(cand), dashboards(base)
    check(set(dc) == set(db), "dashboard set changed")
    for name in set(db) - EDITED_DASHBOARDS:
        a = ET.tostring(dc[name], encoding="unicode") if name in dc else None
        check(a == ET.tostring(db[name], encoding="unicode"), f"untouched dashboard changed: {name}")
    for name, gone in DELETED_ZONES.items():
        for part in ("zones", "devicelayouts"):
            want = [z for z in zone_ids(db[name], part) if z not in gone]
            check(zone_ids(dc[name], part) == want, f"{name} {part}: zone list != base minus {sorted(gone)}")
    for name, (zid, old_w, new_w) in NEW_WIDTHS.items():
        z = next(z for z in dc[name].find("zones").iter("zone") if z.get("id") == zid)
        check(z.get("w") == new_w, f"{name} zone {zid} w={z.get('w')}, want {new_w}")

    check(runs(dc["O3 View"], "76") == ["Standards Mastery"], f"O3 zone 76 runs: {runs(dc['O3 View'], '76')}")
    check(runs(dc["O3 View"], "82") == ["Assessment Mastery by <[Parameters].[Parameter 8]>"], f"O3 zone 82 runs: {runs(dc['O3 View'], '82')}")
    check(runs(dc["DKI View"], "59") == ["Standards Mastery"], f"DKI zone 59 runs: {runs(dc['DKI View'], '59')}")
    check(raw.count("assessment and standard mastery") == 3, "Landing Page overview copy not updated 3 times")

    params = {c.get("name"): c for c in cand.find("datasources").find("datasource[@name='Parameters']").findall("column")}
    base_params = {c.get("name") for c in base.find("datasources").find("datasource[@name='Parameters']").findall("column")}
    check(set(params) == base_params - {"[Parameter 9]"}, "parameter set != base minus Standard or QBL")
    for pname, want in MEMBERS.items():
        got = [m.get("value") for m in params[pname].iter("member")]
        check(got == want, f"{pname} members {got}, want {want}")
        check(params[pname].get("value") in want, f"{pname} current value {params[pname].get('value')} not a member")

    for col in cand.iter("column"):
        f = col.find("calculation")
        if col.get("name") in FORMULAS and f is not None:
            check(f.get("formula") == FORMULAS[col.get("name")], f"formula of {col.get('name')} unexpected: {f.get('formula')!r}")

    base_actions = [a.get("name") for a in base.iter("action")]
    check([a.get("name") for a in cand.iter("action")] == base_actions, "action list changed")

    if failures:
        print("FAIL")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 2: Confirm the assertions fail on the base**

```bash
cd /workspaces/teamster/.claude/scratch/tableau/ddi_suite && uv run --project /workspaces/teamster python check_ddi_qbl.py fresh/base.twb fresh/base.twb >fresh/r_base.txt 2>&1; echo "rc=$?"; head -n 4 fresh/r_base.txt | cut -c1-200
```

Expected `rc=1`, with `retired tokens remain`, `worksheet set wrong` and zone
list failures.

- [ ] **Step 3: Write the edit script and run it**

Save as `edit_ddi_qbl.py`:

```python
"""Retire QBLs and Power Standards from the DDI Suite workbook by text surgery.

Usage: uv run python edit_ddi_qbl.py <base.twb> <out.twb> [--survey]

Text surgery, never an ElementTree round trip (that rewrites quoting and line
endings; see docs/tableau-xml/scripts/README.md). Every operation asserts the
exact number of matches it expects against the 2026-10-02 22:33 UTC base. A
count mismatch means the workbook drifted: stop and reconcile, never loosen.
--survey prints mismatches instead of stopping, for reconciling a new base.
"""

import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable

SURVEY = "--survey" in sys.argv
DS = "federated.16c370f0brwmib116zs5m0y0vz0e (copy)"
QBL_SHEETS = [
    "Region - QBL Mastery",
    "School - QBL Mastery",
    "Classroom - QBL Mastery",
    "Classroom - QBL",
]


class Drift(Exception):
    pass


def expect(label: str, got: int, want: int) -> None:
    if got != want and SURVEY:
        print(f"MISMATCH {label}: want {want}, got {got}")
        return
    if got != want:
        raise Drift(f"{label}: expected {want} matches, found {got}")
    print(f"ok  {label}: {got}")


def element_end(text: str, open_start: int, tag: str) -> int:
    """End offset of the element whose opening tag starts at open_start."""
    open_end = text.index(">", open_start) + 1
    if text[open_end - 2 : open_end] == "/>":
        return open_end
    tok = re.compile(rf"<{re.escape(tag)}(?=[\s>/])[^>]*>|</{re.escape(tag)}>")
    depth, pos = 1, open_end
    while depth:
        m = tok.search(text, pos)
        if not m:
            raise Drift(f"unbalanced <{tag}> at {open_start}")
        t = m.group(0)
        depth += -1 if t.startswith("</") else (0 if t.endswith("/>") else 1)
        pos = m.end()
    return pos


def delete_elements(text: str, tag: str, open_re: str, want: int, label: str) -> str:
    """Delete every <tag> element whose opening tag matches open_re.

    Removes whole lines: leading indentation through the trailing CRLF. A match
    nested inside an earlier match's span is skipped (it goes with its parent).
    """
    pat = re.compile(rf"[ \t]*(?=<{re.escape(tag)}(?=[\s>/])[^>]*?{open_re})")
    spans: list[tuple[int, int]] = []
    for m in pat.finditer(text):
        if spans and m.start() < spans[-1][1]:
            continue
        end = element_end(text, m.end(), tag)
        if text.startswith("\r\n", end):
            end += 2
        spans.append((m.start(), end))
    expect(label, len(spans), want)
    for a, b in reversed(spans):
        text = text[:a] + text[b:]
    return text


def delete_lines(text: str, line_re: str, want: int, label: str) -> str:
    """Delete whole single lines matching line_re (anchored to one line)."""
    pat = re.compile(rf"^[ \t]*(?:{line_re})[ \t]*\r\n", re.M)
    expect(label, len(pat.findall(text)), want)
    return pat.sub("", text)


def sub_exact(text: str, pattern: str, repl: str, want: int, label: str) -> str:
    new, n = re.subn(pattern, repl, text)
    expect(label, n, want)
    return new


def replace_exact(text: str, old: str, new: str, want: int, label: str) -> str:
    expect(label, text.count(old), want)
    return text.replace(old, new)


def in_dashboard(text: str, name: str, fn: Callable[[str], str]) -> str:
    m = re.search(rf"<dashboard [^>]*name='{re.escape(name)}'>", text)
    if not m:
        raise Drift(f"dashboard {name!r} not found")
    b = text.index("</dashboard>", m.start())
    return text[: m.start()] + fn(text[m.start() : b]) + text[b:]


def main_layout(segment: str, fn: Callable[[str], str]) -> str:
    """Apply fn to the dashboard's main <zones> block only, not <devicelayouts>."""
    a = segment.index("<zones>")
    b = segment.index("</zones>", a)
    return segment[:a] + fn(segment[a:b]) + segment[b:]


def zones(ids: list[str], want: int, label: str) -> Callable[[str], str]:
    alt = "|".join(ids)
    return lambda s: delete_elements(s, "zone", rf"\bid='(?:{alt})'", want, label)


def widen(zid: str, old_w: str, new_w: str, label: str) -> Callable[[str], str]:
    def fn(seg: str) -> str:
        return main_layout(
            seg,
            lambda z: sub_exact(
                z,
                rf"(<zone [^>]*\bid='{zid}'[^>]*\bw=')({old_w})(')",
                rf"\g<1>{new_w}\g<3>",
                1,
                label,
            ),
        )

    return fn


def main(src: str, out: str) -> None:
    t = open(src, encoding="utf-8", newline="").read()

    # 1. QBL worksheets and their windows.
    sheets = "|".join(re.escape(s) for s in QBL_SHEETS)
    t = delete_elements(t, "worksheet", rf"name='(?:{sheets})'>", 4, "QBL worksheets")
    t = delete_elements(t, "window", rf"name='(?:{sheets})'>", 4, "QBL worksheet windows")
    t = delete_elements(t, "viewpoint", rf"name='(?:{sheets})'>", 4, "dashboard viewpoints of QBL worksheets")

    # 2. Dashboard zones, main layout and device layouts.
    t = in_dashboard(t, "Mastery Over Time [Region]", zones(["306", "456", "359", "312"], 4, "MOT Region zones"))
    t = in_dashboard(t, "Mastery Over Time [School]", zones(["306", "310", "307", "312"], 4, "MOT School zones"))
    t = in_dashboard(t, "Mastery Over Time [Classroom]", zones(["380", "360", "379", "387"], 7, "MOT Classroom zones"))
    t = in_dashboard(t, "O3 View", zones(["29"], 2, "O3 Standard-or-QBL dropdown"))
    t = in_dashboard(t, "DKI View", zones(["16"], 2, "DKI Standard-or-QBL dropdown"))

    # 3. The neighbour in each horizontal flow takes the freed width.
    t = in_dashboard(t, "Mastery Over Time [Region]", widen("106", "64788", "75659", "MOT Region title width"))
    t = in_dashboard(t, "Mastery Over Time [School]", widen("106", "64788", "75184", "MOT School title width"))
    t = in_dashboard(t, "Mastery Over Time [Classroom]", widen("377", "64568", "75549", "MOT Classroom title width"))
    t = in_dashboard(t, "O3 View", widen("76", "31406", "49268", "O3 Standards header width"))
    t = in_dashboard(t, "DKI View", widen("59", "75988", "98535", "DKI Standards header width"))

    # 4. Action exclude lists.
    t = delete_elements(t, "exclude-sheet", rf"name='(?:{sheets})'", 5, "action exclude-sheet entries")
    t = replace_exact(t, ",Classroom - QBL Mastery,", ",", 3, "comma lists: Classroom - QBL Mastery")
    t = replace_exact(t, "'Classroom - QBL,", "'", 2, "comma lists: leading Classroom - QBL")

    # 5. Text.
    t = sub_exact(
        t,
        r"\r\n[ \t]*<run>Æ&#10;</run>\r\n[ \t]*<run [^>]*>Use the dropdown to change between Standard and QBL mastery</run>",
        "",
        4,
        "instruction line under O3 headers",
    )
    t = replace_exact(
        t,
        "<![CDATA[<[Parameters].[Parameter 9]> Mastery]]>",
        "<![CDATA[Standards Mastery]]>",
        2,
        "O3 Standards header token",
    )
    t = sub_exact(
        t,
        r"<run (fontcolor='#f5f5f5'(?: fontsize='15')?)>&lt;</run>\r\n[ \t]*<run \1>\[Parameters\]\.\[Parameter 9\]</run>\r\n[ \t]*<run \1>&gt; Mastery</run>",
        r"<run \1>Standards Mastery</run>",
        6,
        "DKI/O3 sheet titles and DKI header token",
    )
    t = replace_exact(
        t,
        "assessment, standard, and QBL mastery",
        "assessment and standard mastery",
        3,
        "Landing Page overview copy",
    )

    # 6. Calculations.
    t = replace_exact(
        t,
        "ELSEIF [Parameters].[Parameter 3 1] = &apos;QBLs&apos; THEN &#10;    IF [response_type] = &apos;standard&apos;&#10;    AND [is_qbl] then [is_mastery_int] END&#10;",
        "",
        12,
        "Is Mastery Int - Custom: QBLs branch",
    )
    t = replace_exact(
        t,
        "ELSEIF [Parameters].[Mastery Type - Parameter (copy)_3457427549106843648] = &apos;QBLs&apos; THEN &#10;    IF [response_type] = &apos;standard&apos;&#10;    AND [is_qbl] then [is_mastery_int] END&#10;",
        "",
        2,
        "Is Mastery Int - Custom - Classroom: QBLs branch",
    )
    t = replace_exact(
        t,
        "formula='IF [Parameters].[Parameter 9] = &apos;Standards&apos; THEN [Calculation_5298273899702894595]&#10;ELSEIF [Parameters].[Parameter 9] = &apos;QBLs&apos; THEN [Qbl (copy)_2059270969995493381]&#10;END'",
        "formula='[Calculation_5298273899702894595]'",
        4,
        "View by - O3 Standards formula",
    )
    t = sub_exact(
        t,
        r"\r\n[ \t]*<aliases>\r\n[ \t]*<alias key='%null%' value='No QBL' />\r\n[ \t]*</aliases>",
        "",
        4,
        "View by - O3 Standards 'No QBL' alias",
    )

    # 7. Parameters.
    t = delete_lines(t, r"<member value='&quot;QBLs&quot;' />", 8, "QBLs parameter members")
    t = delete_elements(t, "column", r"name='\[Parameter 9\]'", 8, "Standard or QBL parameter (definition + dependency copies)")
    t = delete_lines(t, r"<card [^>]*param='\[Parameters\]\.\[Parameter 9\]'[^>]*/>", 4, "Standard or QBL parameter cards")

    # 8. Calculated fields to drop, and every reference to them.
    calcs = r"Qbl \(copy\)_2059270969995493381|Calculation_1835568692093849600|Calculation_1835568692096798721"
    t = delete_elements(t, "column", rf"name='\[(?:{calcs})\]'", 6, "QBL and Power Standards calculations")
    t = delete_lines(t, r"<field-sort-custom-order field='Qbl \(copy\)_2059270969995493381' />", 1, "QBL calculation sort order")
    t = delete_elements(t, "drill-path", r"name='QBL, Response Type Code'", 1, "QBL drill path")

    # 9. qbl / is_qbl fields: filters, slices, highlights, styles, groups.
    fld = r"(?:qbl|is_qbl)"
    action_grp = r"Action \(Performance Bands - 3 Level,Qbl\)"
    t = delete_elements(t, "filter", rf"column='\[{re.escape(DS)}\]\.\[none:{fld}:nk\]'", 7, "filters on qbl / is_qbl")
    t = delete_elements(t, "filter", rf"column='\[{re.escape(DS)}\]\.\[{action_grp}\]'", 1, "orphan action filter on Mastery Roster")
    t = delete_lines(t, rf"<column>\[{re.escape(DS)}\]\.\[(?:none:{fld}:nk|{action_grp})\]</column>", 8, "slices on qbl / is_qbl / orphan group")
    t = delete_lines(t, rf"<field>\[{re.escape(DS)}\]\.\[none:{fld}:nk\]</field>", 2, "highlight fields on qbl / is_qbl")
    t = delete_lines(t, rf"<format attr='title' field='\[{re.escape(DS)}\]\.\[none:qbl:nk\]' value='QBL' />", 1, "Mastery Roster QBL filter title")
    t = delete_elements(t, "group", r"name='\[Action \((?:Performance Bands - 3 Level,)?Qbl\)\]'", 2, "orphan QBL action groups")
    t = delete_elements(t, "column-instance", rf"column='\[{fld}\]'", 8, "column-instances of qbl / is_qbl")

    # 10. Datasource fields: qbl, is_qbl, power_standard_goal, is_power_standard.
    cols = r"qbl|is_qbl|power_standard_goal|is_power_standard"
    t = delete_elements(t, "column", rf"name='\[(?:{cols})\]'", 27, "retired column definitions and dependency copies")
    t = delete_elements(t, "metadata-record", rf"class='column'>\r\n[ \t]*<remote-name>(?:{cols})</remote-name>", 8, "metadata records")
    t = delete_lines(t, rf"<field-sort-custom-order field='(?:{cols})' />", 2, "field sort orders")

    ET.fromstring(t)
    if t.count("\n") != t.count("\r\n"):
        raise Drift("a bare LF appeared")
    open(out, "w", encoding="utf-8", newline="").write(t)
    print(f"wrote {out}")


if __name__ == "__main__":
    try:
        main(sys.argv[1], sys.argv[2])
    except Drift as e:
        sys.exit(f"DRIFT: {e}")
```

```bash
cd /workspaces/teamster/.claude/scratch/tableau/ddi_suite && uv run --project /workspaces/teamster python edit_ddi_qbl.py fresh/base.twb fresh/final.twb >fresh/edit.txt 2>&1; echo "rc=$?"; grep -v '^ok' fresh/edit.txt
```

Expected `rc=0`, with no output other than `wrote fresh/final.twb`. Each `ok`
line prints a count that matched. A `DRIFT:` line stops the run: go back to Task
2 Step 3.

- [ ] **Step 4: Assertions pass on the output**

```bash
cd /workspaces/teamster/.claude/scratch/tableau/ddi_suite && uv run --project /workspaces/teamster python check_ddi_qbl.py fresh/final.twb fresh/base.twb >fresh/r_final.txt 2>&1; echo "rc=$?"; cat fresh/r_final.txt
```

Expected `rc=0` and `PASS`.

- [ ] **Step 5: Mutants: prove the assertions have teeth**

```bash
cd /workspaces/teamster/.claude/scratch/tableau/ddi_suite/fresh && b=base.twb; m=/workspaces/teamster/docs/tableau-xml/scripts/mutate.py; py="uv run --project /workspaces/teamster python"
$py $m final.twb m_control.twb "Mastery Over Time [Region]" control >/dev/null 2>&1; cmp -s final.twb m_control.twb && echo "control: byte-identical"
$py $m final.twb m1.twb "Mastery Over Time [Region]" delete 372 >/dev/null 2>&1
$py $m final.twb m2.twb "Mastery Over Time [Classroom]" set-attr 377 w 75548 >/dev/null 2>&1
$py - <<'EOF'
o = open("final.twb", encoding="utf-8", newline="").read()
def mk(name, old, new):
    assert o.count(old) >= 1, name
    open(name, "w", encoding="utf-8", newline="").write(o.replace(old, new, 1))
mk("m3.twb", "<member value='&quot;Walkthroughs&quot;' />", "<member value='&quot;QBLs&quot;' />\r\n          <member value='&quot;Walkthroughs&quot;' />")
mk("m4.twb", "ELSEIF [Parameters].[Parameter 3 1] = &apos;Walkthroughs&apos; THEN&#10;    [Calculation_2059270969708253185]&#10;", "")
mk("m5.twb", "<worksheet name='MOT - School - Title'>", "<worksheet name='MOT - School - Title X'>")
mk("m6.twb", "assessment and standard mastery", "assessment, standard mastery")
EOF
for i in 1 2 3 4 5 6; do $py ../check_ddi_qbl.py m$i.twb $b > m$i.txt 2>&1; echo "m$i rc=$? :: $(sed -n 2p m$i.txt | cut -c1-120)"; done
```

Expected: `control: byte-identical`, then `rc=1` for every mutant, with these
messages:

| Mutant | Expected message                               |
| ------ | ---------------------------------------------- |
| m1     | Region zone list                               |
| m2     | zone 377 `w=75548`                             |
| m3     | `retired tokens remain: ['QBL']`               |
| m4     | formula of `[Calculation_5386727405806911490]` |
| m5     | worksheet set                                  |
| m6     | Landing Page copy                              |

A mutant that passes means the assertion has a hole. Fix the assertion, not the
mutant.

- [ ] **Step 6: Skill checkers on the output**

```bash
cd /workspaces/teamster && b=.claude/scratch/tableau/ddi_suite/fresh/base.twb; o=.claude/scratch/tableau/ddi_suite/fresh/final.twb
uv run python docs/tableau-xml/scripts/check_twb.py $o --ref $b >/tmp/claude-1000/ddi_c1.txt 2>&1; echo "check_twb rc=$?"; tail -n 3 /tmp/claude-1000/ddi_c1.txt
for d in "Mastery Over Time [Region]" "Mastery Over Time [School]" "Mastery Over Time [Classroom]" "O3 View" "DKI View"; do uv run python docs/tableau-xml/scripts/check_geometry.py $o "$d" --baseline $b >/tmp/claude-1000/ddi_g.txt 2>&1; echo "$d rc=$?"; grep FAIL /tmp/claude-1000/ddi_g.txt; done
```

Expected: `check_twb rc=0` with `CLEAN`. Geometry: rc 0 on four dashboards.
`O3 View` has rc 1 with only the zone 156 / zone 3 overlap recorded in Task 2
Step 4. Any other failure is new and blocks the task.

- [ ] **Step 7: Repack**

```bash
cd /workspaces/teamster && uv run python docs/tableau-xml/scripts/repack.py .claude/scratch/tableau/ddi_suite/fresh/final.twb .claude/scratch/tableau/ddi_suite/fresh/base.twbx .claude/scratch/tableau/ddi_suite/fresh/final.twbx >/tmp/claude-1000/ddi_r.txt 2>&1; echo "rc=$?"; tail -n 3 /tmp/claude-1000/ddi_r.txt
```

Expected `rc=0`. The donor is the `base.twbx` from this same pull.

---

### Task 4: Workbook — review copy and renders

**Files:**

- Create: `/workspaces/teamster/tests/test_zz_ddi_suite_review.py` (deleted at
  the end of this task)
- Output: `.../ddi_suite/fresh/render/{base,edit}-<view>-<value>.png` and their
  crops

**Interfaces:**

- Consumes: `fresh/final.twbx`, `fresh/final.twb` (Task 3), `SHOW_TABS` (Task
  2).
- Produces: the review workbook in the named project, the production revision
  number, and rendered crops. Task 5 hands these to the owner.

- [ ] **Step 1: Ask which non-production project**

Ask the user which non-production project or subproject the review copy goes in.
If they have no preference, use `GPA-monitor-temp`
(`c74d8e08-b856-4430-a759-ebacb061e376`). Put the id into `TEMP_PROJECT` and
into `NON_PRODUCTION` below.

- [ ] **Step 2: Write the review test**

```python
import os
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import tableauserverclient as tsc

ROOT = Path(__file__).resolve().parents[1] / ".claude" / "scratch" / "tableau" / "ddi_suite" / "fresh"
RENDER = ROOT / "render"
RENDER.mkdir(parents=True, exist_ok=True)
PROD_LUID = "6d82b643-59a8-4106-b2f9-97ddf7f638e7"
TEMP_PROJECT = "c74d8e08-b856-4430-a759-ebacb061e376"  # replace with the id the user named
NON_PRODUCTION = {"c74d8e08-b856-4430-a759-ebacb061e376"}  # plus the id the user named
SHOW_TABS = True  # replace with SHOW_TABS from Task 2
RENDERS = {
    "Landing Page": None,
    "Mastery Over Time [Region]": ("Mastery Type - Parameter", ["Overall", "Standards", "Walkthroughs"]),
    "Mastery Over Time [School]": ("Mastery Type - Parameter", ["Overall", "Standards", "Walkthroughs"]),
    "Mastery Over Time [Classroom]": ("Mastery Type - Parameter - Classroom", ["Overall", "Percent Correct", "Standards"]),
    "O3 View": None,
    "DKI View": None,
    "Module Dashboard": None,
    "Assessment Dashboard": None,
}


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in s).strip("_")


def _render(server: tsc.Server, view: tsc.ViewItem, prefix: str) -> None:
    spec = RENDERS[view.name]
    values = [None] if spec is None else spec[1]
    for value in values:
        opts = tsc.ImageRequestOptions(imageresolution=tsc.ImageRequestOptions.Resolution.High)
        if value is not None:
            opts.parameter(spec[0], value)
        server.views.populate_image(view, opts)
        out = RENDER / f"{prefix}-{_slug(view.name)}-{_slug(value or 'default')}.png"
        out.write_bytes(view.image)
        print(f"RENDERED {out.name} {out.stat().st_size}")


def test_review() -> None:
    auth = tsc.PersonalAccessTokenAuth(
        token_name=os.environ["TABLEAU_TOKEN_NAME"],
        personal_access_token=os.environ["TABLEAU_PERSONAL_ACCESS_TOKEN"],
        site_id=os.environ["TABLEAU_SITE_ID"],
    )
    server = tsc.Server(os.environ["TABLEAU_SERVER_ADDRESS"], use_server_version=True)
    with server.auth.sign_in(auth):
        prod = server.workbooks.get_by_id(PROD_LUID)
        server.workbooks.populate_views(prod)
        live = {v.name for v in prod.views}
        server.workbooks.populate_revisions(prod)
        print(f"PROD REVISION: {max(int(r.revision_number) for r in prod.revisions)}")

        for cv in tsc.Pager(server.custom_views):
            if cv.workbook and cv.workbook.id == PROD_LUID:
                print(f"CUSTOM VIEW: {cv.id} {cv.name!r} on {cv.view.name if cv.view else '?'}")

        root = ET.parse(ROOT / "final.twb").getroot()
        publishable = {
            w.get("name") for w in root.find("windows")
            if w.get("class") in ("worksheet", "dashboard") and w.get("hidden") != "true"
        }
        hidden = sorted(publishable - live)
        print(f"HIDDEN VIEWS: {len(hidden)}")

        item = tsc.WorkbookItem(
            project_id=TEMP_PROJECT,
            name=f"ZZ-REVIEW {date.today():%Y-%m-%d} DDI Suite",
            show_tabs=SHOW_TABS,
        )
        item.hidden_views = hidden
        if TEMP_PROJECT not in NON_PRODUCTION:
            raise RuntimeError("target is not an agreed non-production project")
        if not item.name.startswith("ZZ-REVIEW "):
            raise RuntimeError("review copies carry the ZZ-REVIEW prefix")
        # trunk-ignore(pyright/reportCallIssue): mode is a str at runtime; see tsc_session.py
        item = server.workbooks.publish(item, str(ROOT / "final.twbx"), mode=tsc.Server.PublishMode.Overwrite)
        if item.project_id != TEMP_PROJECT:
            raise RuntimeError(f"published to {item.project_name}, not the temp project")
        print(f"PUBLISHED: {item.id} into {item.project_name}")

        server.workbooks.populate_views(item)
        review = {v.name: v for v in item.views}
        print(f"REVIEW VIEWS: {sorted(review)}")
        if set(review) != live:
            raise RuntimeError(f"review view set {sorted(review)} != production {sorted(live)}")
        for v in prod.views:
            _render(server, v, "base")
            _render(server, review[v.name], "edit")
```

`custom_views.get`, `populate_revisions`, `RevisionItem.revision_number`,
`CustomViewItem.workbook` and `.view`, and `WorkbookItem.hidden_views` were
checked against the installed `tableauserverclient` source on 2026-10-03.

- [ ] **Step 3: Run it**

```bash
uv run pytest /workspaces/teamster/tests/test_zz_ddi_suite_review.py -s -q -p no:cacheprovider 2>&1 | tail -n 60
```

Expected:

- `1 passed`.
- A `PROD REVISION` number (record it).
- `REVIEW VIEWS` equal to the 8 production view names.
- 2 × 14 `RENDERED` lines: 5 views without a parameter, plus 3 × 3 parameter
  values.
- Zero or more `CUSTOM VIEW` lines (record them).

- [ ] **Step 4: Crop and look**

Crop each render pair to the regions that changed. Full renders trip output
scanning.

```bash
cd /workspaces/teamster/.claude/scratch/tableau/ddi_suite/fresh/render && uv run --with pillow python - <<'EOF'
from pathlib import Path
from PIL import Image
for p in sorted(Path(".").glob("*.png")):
    if "_crop" in p.stem:
        continue
    im = Image.open(p)
    w, h = im.size
    im.crop((0, 0, w, int(h * 0.12))).save(p.with_name(p.stem + "_crop_header.png"))
    if "O3_View" in p.stem or "DKI_View" in p.stem:
        im.crop((0, int(h * 0.12), w, int(h * 0.65))).save(p.with_name(p.stem + "_crop_body.png"))
    print(p.name, w, h)
EOF
```

Read each `base`/`edit` crop pair with the Read tool:

- **Mastery Over Time (each value):** the header row shows the logo, the title
  and one button. There is no Show/Hide QBLs button, and nothing is clipped or
  overlapping. The Mastery Type dropdown has no QBLs choice.
- **O3 View:** the Standards section header reads `Standards Mastery`, with no
  dropdown beside it and no "Use the dropdown…" line. The Assessment Mastery
  header keeps its View By dropdown.
- **DKI View:** the header reads `Standards Mastery`, with no dropdown.
- **Landing Page:** the overview copy reads `assessment and standard mastery`.
- **Every view:** no `####`, no blank marks where the base has marks, and no
  literal `[Parameters]` token. Chart content matches the base apart from data
  refreshed in between.

If a `CUSTOM VIEW` sits on O3 View, DKI View or a Mastery Over Time dashboard,
render it on production through `server.custom_views.populate_image`. Note that
it cannot be rendered against the review copy, because custom views belong to
the production workbook. List it for the owner to open after the production
publish.

- [ ] **Step 5: Delete the review test**

```bash
rm /workspaces/teamster/tests/test_zz_ddi_suite_review.py
```

---

### Task 5: Owner — Desktop check and production publish (the user does this)

This task is the user's. Claude hands over, waits, and then verifies.

- [ ] **Step 1: Hand over**

Give the user:

- `fresh/final.twbx`.
- The review copy's URL.
- `PROD REVISION` (their restore point).
- The custom view list.
- The crops looked at, and what was verified vs. inferred.
- The click-through checklist:

  1. Open `final.twbx` in Tableau Desktop. It must open without a validation
     error.
  2. On each data source, run Data → Extract → Refresh (a full refresh). Both
     must succeed. In the `rpt_tableau__ddi_dashboard` source, `Qbl` and
     `Is Qbl` must not appear in the Data pane after the refresh. Neither may
     `Power Standard Goal` nor `Is Power Standard` in the
     `rpt_tableau__assessment_dashboard` source.
  3. On Mastery Over Time [Region], [School] and [Classroom], step through every
     Mastery Type value. Then click a bar and a line on [Classroom] and confirm
     Mastery Roster filters.
  4. On O3 View and DKI View, check the Standards sections and their filters.
  5. Dashboard → Device Preview → Phone for those five dashboards.
  6. If all of that is fine, publish to production from Desktop (Server →
     Publish Workbook, same name and project, embed credentials as today).

- [ ] **Step 2: After the user says they published, verify**

Pull the production workbook again with a copy of Task 2's test and run
`check_ddi_qbl.py <new prod twb> fresh/base.twb`. Expected `PASS`; Desktop's
save may reorder XML, so a failure needs reading, not a re-edit. Confirm the 8
view names are unchanged and `updated_at` moved. Delete the test file. Post a
short comment on #5656 saying the workbook step is live.

---

### Task 6: dbt PR 2 — drop the columns, disable the lookup (data engineer)

Gate: PR 1 is merged and Task 5 Step 2 passed. Start on a new branch, linked to
#5656, cut from `origin/main` after PR 1 merges. Follow the root CLAUDE.md
_Branches_ flow and ask worktree or branch switch. Example name:
`<gh-user>/chore/claude-drop-qbl-columns`.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__ddi_dashboard.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__ddi_dashboard.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__assessment_dashboard.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__assessment_dashboard.yml`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__assessments__qbls_power_standards.yml`
- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`
- Modify: `docs/launch/links.yml`

- [ ] **Step 1: Record baselines**

Run Task 1 Step 1's two queries against prod for both
`rpt_tableau__ddi_dashboard` and `rpt_tableau__assessment_dashboard`, with row
counts by `academic_year`.

- [ ] **Step 2: Drop the placeholders from `rpt_tableau__ddi_dashboard`**

Delete all six lines that Task 1 left: 3 × `cast(null as string) as qbl,` and 3
× `false as is_qbl,`, plus any blank line that leaves doubled. In the properties
YAML, delete the `qbl` and `is_qbl` column entries, descriptions included.

- [ ] **Step 3: Drop the Power Standards placeholders from
      `rpt_tableau__assessment_dashboard`**

Delete:

```sql
    null as power_standard_goal,
    null as is_power_standard,
```

Keep the comment `/* retired fields kept for tableau compatibility */` and
`null as standard_domain,`. They are out of scope. In its properties YAML,
delete:

```yaml
- name: power_standard_goal
  data_type: int64
- name: is_power_standard
  data_type: int64
```

- [ ] **Step 4: Disable the staging model**

In `stg_google_sheets__assessments__qbls_power_standards.yml`, add a model-level
config under the `name:` line:

```yaml
models:
  - name: stg_google_sheets__assessments__qbls_power_standards
    config:
      enabled: false
    columns:
```

The model has no tests, so no test needs disabling. Confirm with
`rg -n 'data_tests' <that file>`, which should return nothing.

- [ ] **Step 5: Disable the Sheets source**

In `sources-external.yml`, under
`- name: src_google_sheets__assessments__qbls_power_standards`, add
`enabled: false` as the first key of its `config:` block. Same form as
`src_google_sheets__gradebook_flags`:

```yaml
config:
  enabled: false
  meta:
    dagster:
      asset_key:
```

- [ ] **Step 6: Update the launch catalog**

In `docs/launch/links.yml`, the `ddi_suite` entry becomes:

```yaml
description:
  Data-Driven Instruction metrics. Week-over-week assessment and standard
  mastery.
```

- [ ] **Step 7: Verify**

Sweep:

```bash
rg -n -i 'qbl|power_standard' --glob '*.{sql,yml,md}' /workspaces/teamster/<new worktree>/src /workspaces/teamster/<new worktree>/docs/launch
```

Expected: hits only in the disabled models (`rpt_tableau__ddi_audit`,
`rpt_tableau__qbl`, `rpt_tableau__power_standards` and their YAML), the disabled
staging model and its YAML, and the disabled source entry.

Parse, in its own Bash call:

```bash
uv run dbt parse --no-partial-parse --project-dir <new worktree>/src/dbt/kipptaf 2>&1 | tail -n 15
```

Expected: success. Confirm in `target/manifest.json` that
`source.kipptaf.google_sheets.src_google_sheets__assessments__qbls_power_standards`
is under `disabled`, not `sources`, and that no node in `nodes` lists it or the
staging model in `depends_on`.

Build both `rpt_` models in dev with `--defer` (Task 1 Step 6 form). Expected:

- Row counts by year match Step 1.
- `INFORMATION_SCHEMA.COLUMNS` equals prod minus exactly `qbl` and `is_qbl`, and
  minus exactly `power_standard_goal` and `is_power_standard`.

Run the launch tests the `docs/launch` change gates on:

```bash
uv run --group docs pytest tests/launch -q 2>&1 | tail -n 5
```

Run `trunk check --force --no-fix` on every changed file.

- [ ] **Step 8: Commit, push, open PR 2**

`refactor(dbt): drop retired QBL and Power Standards columns and disable their sheet source`.

- Body: `Closes #5656`.
- Say that `docs/launch/links.yml` needs `analytics-engineers` review.
- Say how to roll back: revert the PR.
- Verify the returned title and body.

---

### Task 7: After PR 2 merges — confirm prod

- [ ] **Step 1: The Dagster asset is gone**

After the kipptaf code location reloads, use `mcp__dagster-plus__get_asset` (or
`get_assets` filtered by prefix) on
`kipptaf/google/sheets/assessments/qbls_power_standards`. Expected: not found.

- [ ] **Step 2: The Tableau refresh succeeded**

After the first prod build of `rpt_tableau__ddi_dashboard` that follows the
merge, pull the workbook's metadata with a throwaway test. Get
`server.workbooks.get_by_id(...)` and its `updated_at`, plus
`server.jobs.filter(...)` for the latest RefreshExtract job on this workbook.
Expected: the job finished with `finish_code == 0`, and `updated_at` is after
the merge.

If it failed, revert PR 2 and report the job's error notes.

- [ ] **Step 3: Close out**

Post the result on #5656.
