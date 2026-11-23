# Module Dashboard Completion and Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a review copy of the DDI Suite whose Module Dashboard shows an
accurate completion %, hides cells under 75% complete, and lets a user pivot the
2 main heatmaps by grade level or high school course subject.

**Architecture:** Every change is an edit to the workbook's `.twb` XML, made by
re-runnable Python scripts against a fresh download of the review copy. The
extract already holds the not-taken rows, so no dbt model changes. An
independent SQL oracle over the packaged `.hyper` proves the completion numbers.

**Tech Stack:** Tableau `.twb` XML, Python (`tableauserverclient`,
`tableauhyperapi` through `uv run --with`), the scripts in
`docs/tableau-xml/scripts/`, pytest as the credential runner.

**Spec:**
`docs/superpowers/specs/2026-11-23-module-dashboard-completion-pivot-design.md`.
Read it first. The formulas, the cell grain and the list of sheets live there
and are not repeated here.

## Global Constraints

- Invoke the `tableau-workbook-xml` skill before any workbook work and follow
  its loop. Invoke `ddi-stack` for dashboard terms. Where this plan and the
  skill disagree on mechanics, the skill wins.
- Base workbook: luid `652f1c0a-371a-42ee-807a-61a3915e3af2`
  (`ZZ-REVIEW 2026-11-12 DDI Suite goal columns`). Never publish over it.
- Never publish to the Production project. The production DDI Suite is luid
  `6d82b643-59a8-4106-b2f9-97ddf7f638e7`; no step here touches it.
- Every copy is published to `GPA-monitor-temp`,
  `c74d8e08-b856-4430-a759-ebacb061e376`, the project the user named. No other
  project id appears in a publish call.
- Every published name starts
  `ZZ-REVIEW <YYYY-MM-DD> DDI Suite module completion`. Probe copies append
  ` PROBE <variant>`.
- No dbt, Cube or Dagster file changes. If a step seems to need one, stop and
  ask the user.
- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-module-dashboard-completion-pivot`
  (called `<wt>` below). Reach it by absolute path and `git -C <wt>`.
- Scripts and workbook files live in `<wt>/.claude/scratch/tableau/`, which is
  gitignored. Only the docs change in Task 7 is committed.
- Student-level rows (the `.hyper`, exported CSVs) stay in scratch. Nothing
  student-level goes to git, GitHub or the final report. Report aggregates only.
- Read every `.twb` with `encoding="utf-8", newline=""` and write it the same
  way. The file uses CRLF line endings.
- Every substitution asserts how many times it matched. A calculated field's
  `<column>` element is repeated: once in the datasource and once in the
  `<datasource-dependencies>` of every worksheet that reads it. An edit to a
  formula changes every copy, and the assertion counts them.
- Read exit codes with a redirect, never through a pipe.
- Avoid Tableau MCP calls while a publish or export is running. They share the
  token and can end the session.

## Review Focus

1. A worksheet that reads `% Completion` but lacks a dependency declaration for
   `Heatmap Column` or the new parameter. Server may render it and Desktop may
   refuse it. Pinned by the dependency assertion in Task 4.
2. A mark that mixes a due assessment with one not yet due. Its mastery value
   legitimately changes, because early scores for the not-yet-due assessment are
   now hidden. Pinned by the exclusion list in Task 6, check A.
3. A cell with no counted assignment (possible is 0). Completion must be null
   and the cell hidden, not an error or 100%. Pinned by the oracle comparison in
   Task 6, check B.
4. Grade order on the heatmap columns. A string sort puts 10 before 2. Pinned by
   the column-order check in Task 6, check D.
5. The shared `response_type` filter (group 27) losing its context flag on only
   some of its sheets. Pinned by the count assertion in Task 2.

## File Structure

All under `<wt>/.claude/scratch/tableau/`:

| Path                          | Responsibility                                                 |
| ----------------------------- | -------------------------------------------------------------- |
| `server/base.twbx`            | Fresh download of the base, with its extract                   |
| `server/base.twb`             | The untouched XML. `--ref` and `--baseline` for every check    |
| `module-dashboard/build.py`   | Applies every edit in order. The one entry point               |
| `module-dashboard/asserts.py` | One assertion function per task, runnable by name              |
| `module-dashboard/oracle.py`  | Computes cell completion from the `.hyper`                     |
| `module-dashboard/compare.py` | Compares exported sheet data with the oracle and with the base |
| `module-dashboard/out/`       | Built `.twb` and `.twbx` files                                 |

Credentialed steps run from a throwaway
`<wt>/tests/test_zz_module_dashboard.py`, copied from
`docs/tableau-xml/scripts/tsc_session.py` and run with
`cd <wt> && uv run pytest tests/test_zz_module_dashboard.py -s`. Delete it in
Task 7.

`build.py` interface, used by every later task:

```python
def build(base_text: str, *, completion_min: float = 0.75,
          pooled_format: str = "p0%") -> str:
    """Return the edited .twb text. Each edit_* runs once, in task order."""

# CLI
# uv run python build.py <base.twb> <out.twb> [--completion-min 0.0]
#                                             [--pooled-format p0.00%]
```

`asserts.py` interface:

```python
# uv run python asserts.py <twb> <name>   -> exit 0 pass, 1 fail, prints why
# names: completion, pooled, pivot, param_zone, all
```

---

### Task 1: Fresh base, baseline checks and the oracle

**Files:**

- Create: `server/base.twbx`, `server/base.twb`, `module-dashboard/oracle.py`

**Interfaces:**

- Produces: `base.twb`, `base.twbx`; the recorded `updated_at`, revision number
  and `show_tabs` of the base; `oracle.py` with

  ```python
  def cells(hyper_path: str, *, pivot: str, today: date) -> pandas.DataFrame:
      """One row per completion cell.

      pivot is "Grade Level" or "Course Subject".
      Columns: academic_year, schoolid, subject_area, module_type,
      module_number, is_replacement, heatmap_column, grade_levels (set),
      n_possible, n_complete, n_scored_rows, has_not_yet_due (bool).
      """
  ```

- [ ] **Step 1: Download the base with its extract.** Use the `test_download`
      recipe with `WORKBOOK_LUID` set to the base luid. Record `updated_at`,
      `show_tabs` and the current revision number (`populate_revisions`).

  Expected: `base.twbx` over 20 MB; `base.twb` about 3 MB with CRLF endings.

- [ ] **Step 2: Check the base has not drifted.** Confirm these facts, which the
      spec depends on. If any fails, stop and report: the design was made
      against a different file.

  - `[% Completion (copy)]` formula contains
    `SUM([Calculation_860187586860363778])`.
  - 15 worksheets carry `[none:response_type:nk]` with `context='true'` and
    `filter-group='27'`.
  - `Module - Overall - Network Overview` and
    `Module - Overall - Assessments Over Time` have `[none:grade_level:ok]` in
    `<cols>`.
  - 12 worksheets carry a `[none:% Completion (copy):qk]` filter with
    `<min>0.75</min>` and `filter-group='44'`.

- [ ] **Step 3: Run both checkers on the untouched base.**

  ```bash
  uv run python docs/tableau-xml/scripts/check_twb.py <base.twb> --ref <base.twb> >/tmp/o1 2>&1; rc1=$?
  uv run python docs/tableau-xml/scripts/check_geometry.py <base.twb> "Module Dashboard" --baseline <base.twb> >/tmp/o2 2>&1; rc2=$?
  ```

  Expected: both exit 0. A failure here is a checker problem; report it before
  editing anything.

- [ ] **Step 4: Confirm the extract holds not-taken rows.** Unpack the
      `rpt_tableau__assessment_dashboard` `.hyper` from `base.twbx` (its
      `dbname` is on the datasource's `<extract><connection>`). With
      `uv run --with tableauhyperapi --with pandas`, count rows in
      `"Extract"."Extract"` where `response_type` is null and `academic_year` is
      2026, by `region`.

  Expected: tens of thousands for Newark and Camden, thousands for Paterson,
  none for Miami. If the count is 0, stop: the workbook has a datasource or
  extract filter the spec did not account for.

- [ ] **Step 5: Write `oracle.py`.** It implements the spec's _Definitions_
      section in SQL over the `.hyper`, independently of the workbook's
      formulas. `heatmap_column` follows the spec's `Heatmap Column` formula.
      `n_scored_rows` counts `overall` rows with a non-null `percent_correct`
      (the rows a sheet can show). `has_not_yet_due` is true when the cell holds
      any row with `administered_at` after `today`.

- [ ] **Step 6: Sanity-check the oracle.** Pooled `n_complete / n_possible` by
      region for 2026, `pivot="Grade Level"`.

  Expected: Camden, Newark and Paterson between 60% and 85%; Miami at or near
  100%. (Prod measured 69%, 73%, 75% on 2026-11-23; the extract is older, so
  expect nearby values, not equal ones.)

---

### Task 2: Completion calcs and the context filter

**Files:**

- Create: `module-dashboard/build.py` (with `edit_completion`),
  `module-dashboard/asserts.py` (with `completion`)

**Interfaces:**

- Consumes: `base.twb`.
- Produces: `edit_completion(text: str) -> str`; the 3 completion calcs with the
  spec's formulas, using `[grade_level]` where the spec writes
  `[Heatmap Column]`. Task 4 swaps that one token.

- [ ] **Step 1: Write the `completion` assertion.** It passes only when all of
      these hold:

  - No `<calculation>` formula contains `SUM([Calculation_860187586860363778])`.
  - Every copy of `[Student Baseline Count (copy)]` and
    `[Calculation_860187586860363778]` has a formula containing
    `[administered_at] <= TODAY()` and `STR([student_number])`, and none
    contains `[is_pathways]`.
  - Every copy of `[Student Baseline Count (copy)]` contains
    `ISNULL([response_type])`.
  - The number of copies of each of the 3 calcs equals its count in `base.twb`.
  - The 17 worksheets the spec lists have a `[none:response_type:nk]` filter
    without `context='true'`; its `<groupfilter>` members are unchanged from the
    base; `filter-group='27'` is still on the same 15.
  - Every other `context='true'` in the file is unchanged from the base (compare
    counts per worksheet).

- [ ] **Step 2: Run it on the base.**

  Run: `uv run python asserts.py <base.twb> completion; echo $?` Expected: exit
  1, naming the first failed condition.

- [ ] **Step 3: Implement `edit_completion`.** Formulas come from the spec.
      Inside an XML attribute, a line break is `&#10;`, an apostrophe is
      `&apos;`, `<` is `&lt;`. Keep each calc's `caption`, `datatype`, `role`
      and `default-format`.

- [ ] **Step 4: Build and assert.**

  Run: `uv run python build.py <base.twb> out/out.twb` then
  `uv run python asserts.py out/out.twb completion; echo $?` Expected: exit 0.
  `ET.fromstring` parses the output.

- [ ] **Step 5: Prove the assertion bites.** Hand-write 2 broken variants of
      `out.twb` and confirm each fails: one copy of `% Completion` left with the
      old formula; one of the 17 sheets left with `context='true'`.

- [ ] **Step 6: Run both checkers** against `out.twb` with `--ref` and
      `--baseline` set to `base.twb`.

  Expected: both exit 0.

---

### Task 3: Pooled completion where it is shown

**Files:**

- Modify: `module-dashboard/build.py` (add `edit_pooled`),
  `module-dashboard/asserts.py` (add `pooled`)

**Interfaces:**

- Consumes: the Task 2 calcs.
- Produces: `edit_pooled(text: str, *, fmt: str = "p0%") -> str`; a calc with
  caption `% Completion (Pooled)`, internal name `[% Completion (Pooled)]`,
  `datatype='real'`, `role='measure'`, `default-format=fmt`, and the instance
  `[usr:% Completion (Pooled):qk]`. Its `INCLUDE` grain uses `[grade_level]`
  until Task 4.

- [ ] **Step 1: Write the `pooled` assertion.**

  - The datasource defines `[% Completion (Pooled)]` once, with the spec's
    formula.
  - In `Module - Overall - Summary` and
    `Module - Overall - Assessments Over Time`, the instance
    `[avg:% Completion (copy):qk]` no longer appears and
    `[usr:% Completion (Pooled):qk]` appears the same number of times the old
    one did in the base.
  - Each of those 2 worksheets declares the new `<column>` and its
    `<column-instance>` in `<datasource-dependencies>`.
  - `[none:% Completion (copy):qk]` (the filter) is untouched: 12 worksheets, as
    in the base.
  - No other worksheet's XML differs from the Task 2 output.

- [ ] **Step 2: Run it on the Task 2 output.** Expected: exit 1.

- [ ] **Step 3: Implement `edit_pooled`.** Model the declarations on
      `[usr:Calculation_1835568692099076098:qk]` in
      `Module - Overall - Assessments Over Time`, which is an aggregate calc
      already on that sheet. In the tooltip, change only the instance string
      inside the existing run; keep the run's attributes and separators
      byte-for-byte. On the summary sheet the old instance also appears in the
      Measure Names filter and may appear in aliases and formats; replace each.

- [ ] **Step 4: Build, assert, break, check.** Same four moves as Task 2 steps 4
      to 6. The broken variant: the summary sheet's Measure Names filter still
      naming the old instance.

  Expected: assertion exit 0 on the build, exit 1 on the variant, both checkers
  exit 0.

---

### Task 4: Pivot parameter, fields and heatmap columns

**Files:**

- Modify: `module-dashboard/build.py` (add `edit_pivot`),
  `module-dashboard/asserts.py` (add `pivot`)

**Interfaces:**

- Consumes: Tasks 2 and 3.
- Produces: `edit_pivot(text: str) -> str`; parameter
  `[Parameters].[Heatmap Columns]` (caption `Heatmap Columns`, members
  `"Grade Level"` and `"Course Subject"`, value `"Grade Level"`); calcs
  `[Heatmap Column]` (caption `Heatmap Column`, string dimension) and
  `[Heatmap Column Sort]` (caption `Heatmap Column Sort`, integer dimension);
  instance `[none:Heatmap Column:nk]`.

- [ ] **Step 1: Write the `pivot` assertion.**

  - Fails first if `base.twb` already contains a column named
    `[Heatmap Columns]`, `[Heatmap Column]` or `[Heatmap Column Sort]`.
  - The parameter exists once in the `Parameters` datasource with exactly the 2
    members, and both calcs exist with the spec's formulas.
  - `<cols>` of both heatmap sheets holds `[none:Heatmap Column:nk]` and no
    `grade_level` instance. `<rows>` is unchanged from the base.
  - Both heatmap sheets carry a computed sort on `[none:Heatmap Column:nk]` by
    the minimum of `Heatmap Column Sort`, ascending.
  - No formula of the 3 completion calcs or the pooled calc contains
    `[grade_level]`; each contains `[Heatmap Column]`.
  - Dependency rule: every worksheet whose `<datasource-dependencies>` declares
    `[% Completion (copy)]` also declares `[Heatmap Column]`, and declares
    `[Heatmap Columns]` under a `Parameters` dependency block.
  - `Module - Overall - Teacher` shelves are unchanged from the base.

- [ ] **Step 2: Run it on the Task 3 output.** Expected: exit 1.

- [ ] **Step 3: Implement `edit_pivot`.** Model the parameter on
      `[Group By (copy)]` (caption `Dashboard View`), a 2-member string list.
      Model a parameter-driven dimension and its per-sheet declarations on
      `[Calculation_731272039934623744]` (caption `Dashboard View Filter`) as
      declared in `Module - Overall - Assessments Over Time`: the calc's
      `<column>`, its `<column-instance>`, and the parameter's `<column>` under
      the sheet's `Parameters` dependency block. A sheet with no `Parameters`
      block gains one, plus the `Parameters` entry in its view's
      `<datasources>`; copy both from a sheet that has them. Model the computed
      sort on an existing `<computed-sort>` (25 exist; the simplest sorts
      `assessment_id` by `[max:title:nk]`).

  If the feature manifest lacks an entry an added element needs, `check_twb.py`
  says so; insert the one entry, never rebuild the manifest.

- [ ] **Step 4: Build, assert, break, check.** Broken variants: one completion
      calc copy still on `[grade_level]`; one worksheet missing the
      `Heatmap Column` dependency.

  Expected: assertion exit 0 on the build, exit 1 on each variant, both checkers
  exit 0.

---

### Task 5: The parameter control on the dashboard

**Files:**

- Modify: `module-dashboard/build.py` (add `edit_param_zone`),
  `module-dashboard/asserts.py` (add `param_zone`)

**Interfaces:**

- Consumes: the Task 4 parameter.
- Produces: `edit_param_zone(text: str) -> str`; one new `paramctrl` zone in the
  `Module Dashboard` `<zones>` block with
  `param='[Parameters].[Heatmap Columns]'`.

- [ ] **Step 1: Write the `param_zone` assertion.**

  - `Module Dashboard` has exactly 2 `paramctrl` zones: the existing
    `[Parameters].[Group By (copy)]` and the new one.
  - The new zone has the same parent zone as the existing one and directly
    follows it.
  - Zone ids are unique within the workbook.
  - The existing zone's `mode` and style are copied onto the new one.
  - No other dashboard's `<zones>` differs from the base. If `Module Dashboard`
    has a `<devicelayouts>` block, it is unchanged.

- [ ] **Step 2: Run it on the Task 4 output.** Expected: exit 1.

- [ ] **Step 3: Implement `edit_param_zone`.** Read
      `references/layout-and-zones.md` in the skill first. The parent is a flow
      container: decide from that reference whether the new zone takes space
      from its sibling or from the container, and keep the container's
      parent-minus-children gap equal to the baseline's.

- [ ] **Step 4: Prove the assertion with `mutate.py`.** Run `control` first; it
      must be byte-identical. Then `duplicate` the new zone and `reparent` it,
      and confirm the assertion fails on each mutant.

- [ ] **Step 5: Run both checkers.**

  Expected: `check_geometry.py out.twb "Module Dashboard" --baseline base.twb`
  exits 0 or reports only the one intended gap change; explain any reported
  difference before going on. `asserts.py out.twb all` exits 0.

---

### Task 6: Probe copies and the data checks

**Files:**

- Create: `module-dashboard/compare.py`, `tests/test_zz_module_dashboard.py`

**Interfaces:**

- Consumes: `build()`, `oracle.cells()`, `base.twbx`.
- Produces: 3 probe copies, 4 passing checks, and the luids of the probes for
  deletion in Task 7.

Probe copies. Each is repacked with `repack.py` using `base.twbx` as the donor,
and published with `hidden_views` computed as the skill describes, except that
the 2 heatmap worksheets stay visible so their data can be exported:
`Module - Overall - Network Overview` and
`Module - Overall - Assessments Over Time`.

| Probe   | Built from                                           |
| ------- | ---------------------------------------------------- |
| `base`  | `base.twb`, unedited                                 |
| `min0`  | `build(completion_min=0.0, pooled_format="p0.00%")`  |
| `min75` | `build(completion_min=0.75, pooled_format="p0.00%")` |

- [ ] **Step 1: Set the publish gate in the test file** before any publish call:
      the literal `GPA-monitor-temp` project id, the `ZZ-REVIEW ` name prefix,
      and a raise after the call if `item.project_id` differs.

- [ ] **Step 2: Publish the 3 probes and export.** For each probe and each of
      the 2 heatmap worksheets, export CSV with `CSVRequestOptions`, setting the
      `Dashboard View` parameter to the value that shows that sheet
      (`Network Comparison` or `Assessments Over Time`). For `min0` and `min75`,
      export once per `Heatmap Columns` value. Confirm from the installed
      `tableauserverclient` source that `CSVRequestOptions` takes `parameter()`
      before relying on it.

  Expected: each export has rows. An empty export means the parameter did not
  apply; fix that before reading any result.

- [ ] **Step 3: Check A, mastery is unchanged.** `base` against `min0`,
      `Grade Level`, both heatmaps. Join on every dimension column.

  Expected: the mastery column is equal on every key present in both. Keys only
  in `base`, and keys whose mastery differs, all belong to marks that the oracle
  flags `has_not_yet_due`. No key is only in `min0`.

- [ ] **Step 4: Check B, completion matches the oracle.** `min75`,
      `Module - Overall - Assessments Over Time`, both pivot values. Aggregate
      the oracle's cells to the sheet's marks under the sheet's default filters
      (read them from the XML, including the members of the subject group the
      context filter selects): keep cells with `n_scored_rows > 0`,
      `n_possible > 0` and `n_complete / n_possible >= 0.75`, then sum.

  Expected: the same set of marks, and `% Completion (Pooled)` equal to the
  oracle's value at 2 decimal places of a percent, for every mark.

- [ ] **Step 5: Check C, the filter hides cells.**

  Expected: `min75` has strictly fewer marks than `min0` on each heatmap, and no
  `min75` mark has pooled completion under 75%.

- [ ] **Step 6: Check D, the pivot columns.**

  Expected, `Grade Level`: column headers are a subset of K, 1 to 12, in that
  order in the export or render. Expected, `Course Subject`: grades K to 8
  unchanged, no header 9 to 12, and the high school headers equal the distinct
  `subject_area` values the oracle returns for grades 9 to 12 under the same
  filters.

- [ ] **Step 7: If a check fails,** fix `build.py`, rebuild, rerun
      `asserts.py all` and both checkers, republish the affected probes and
      rerun every check. Do not adjust the oracle to match the workbook without
      a reason found in the spec's definitions.

---

### Task 7: Final review copy, hand-over and docs

**Files:**

- Create: `module-dashboard/out/final.twbx`
- Modify: `<wt>/docs/models/ddi-stack-data-model.md` (the
  `rpt_tableau__assessment_dashboard` section)
- Delete: `<wt>/tests/test_zz_module_dashboard.py`

**Interfaces:**

- Consumes: everything above.
- Produces: the review copy `ZZ-REVIEW <date> DDI Suite module completion`, a
  hand-over report, a docs commit and a pull request.

- [ ] **Step 1: Build and publish the final copy.** `build()` with defaults
      (`completion_min=0.75`, `pooled_format="p0%"`), repacked on `base.twbx`.
      `hidden_views` per the skill: publishable sheets from `<windows>`, minus
      the base copy's live view names, minus nothing (this build adds no sheet).
      Pass the base's `show_tabs`.

  Expected: the copy lists the same 8 views as the base.

- [ ] **Step 2: Render and look.** Render the `Module Dashboard` view of the
      base and of the final copy at the same resolution, for each of the 4
      combinations of `Dashboard View` and `Heatmap Columns`. Crop the control
      strip, each heatmap and the summary row.

  Expected in every crop: no `####`, no clipped or ellipsised text, no literal
  `[federated…]` token, no overlapping zones; the new control shows its 2
  values; grade headers in order; the summary shows a completion value under
  100% for a New Jersey region.

- [ ] **Step 3: Delete the 3 probe copies** by the luids Task 6 recorded.
      Confirm each luid's name ends in ` PROBE <variant>` before deleting.

- [ ] **Step 4: Update the model doc.** In
      `docs/models/ddi-stack-data-model.md`, under
      `rpt_tableau__assessment_dashboard`, add to _Worth knowing_: how the
      workbook computes completion (assignment, counted, taken, the cell grain),
      that the Module Dashboard reads the null-`response_type` rows for it, and
      that Miami reads about 100%. Replace the bullet saying Miami holds zero
      rows in prod; Miami rows from SY26-27 are Focus Apex assessments, as the
      model's own description says. State behavior, not measurements.

- [ ] **Step 5: Lint, commit, push.**

  ```bash
  cd <wt> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/models/ddi-stack-data-model.md </dev/null
  git -C <wt> add -u
  git -C <wt> commit -m "docs(ddi): describe Module Dashboard completion and the heatmap pivot"
  git -C <wt> push
  ```

  Expected: no lint findings; the push lands on
  `anthonygwalters/feat/claude-module-dashboard-completion-pivot`.

- [ ] **Step 6: Delete the throwaway test file** and confirm
      `git -C <wt> status --short` shows nothing under `tests/`.

- [ ] **Step 7: Open the pull request and report.** PR body from
      `.github/pull_request_template.md`, with `Closes #6474`. Comment on #6474
      with the review copy's link and the hand-over report:

  - What was verified (checks A to D, with mark counts as aggregates) and what
    was only inferred.
  - Which regions were rendered and looked at.
  - What a human still has to do: open `final.twbx` in Desktop, hover the
    Assessments Over Time tooltip, click a heatmap cell in each pivot mode and
    confirm the other sheets filter, move the completion slider.
  - The extract date (`updated_at` of the base) the copy carries.
  - That embedded connection credentials were not carried by the publish, so the
    copy will not refresh until the owner re-embeds them.
  - The path of `build.py`, for replaying the edits on a newer base.
  - That promotion to production is the user's decision and needs the skill's
    two typed confirmations.
