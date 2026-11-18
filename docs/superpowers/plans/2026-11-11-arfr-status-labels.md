# ARFR Status Labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** DeansList report cards print the dashboard's ARFR labels, and
promotion-in-doubt letters match the 2026-27 draft, live before the Friday
11/13/2026 print.

**Architecture:** One dbt extract view (`rpt_deanslist__promo_status`) changes
the values DeansList receives. Three DeansList Report Manager sources change
through the scratch splice workflow: scripts read a pulled live copy, apply
asserted edits, and write paste targets that the user pastes and saves.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Python splice scripts,
Handlebars/JS DeansList reports, Claude in Chrome for read-only pulls.

**Spec:** `docs/superpowers/specs/2026-11-11-arfr-status-labels-design.md`

## Global Constraints

- Everything is live and render-tested by Thursday 11/12 evening; print is
  Friday 11/13 in every region.
- Label strings, exactly: `At-Risk for Retention`,
  `On-Track (Academic Warning)`, `On-Track (Attendance Warning)`, `On-Track`,
  `Off-Track`.
- Camden letter sentence, exactly:
  `Failing 3 or more core classes means automatic retention with no summer school eligibility.`
- K-2 letter note, exactly:
  `NOTE: K-2 data reflects DIBELS, and 3-4 data reflects iReady`
- This repo is public. DeansList source, vendor docs, and student data stay
  under `.claude/scratch/deanslist/` (gitignored). Nothing from there is
  committed or pasted into GitHub.
- The agent never saves in Report Manager. The user pastes and saves; the agent
  produces paste targets, a paste list, and checksums.
- Pull live and compare before every edit. Save a checksummed baseline before
  any paste; the baseline is the rollback.
- Always `uv run` for Python and dbt. Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/fix/claude-arfr-status-labels`.
- DeansList source GUIDs: letter `E0E7E752-2ED1-DAF6-8C2C-5E8950CF55F0` (owner
  KIPP BOLD Academy); MS/HS report card `4D5EFD16-E225-B041-D4D0-B1B86404FA5D`
  (owner KIPP Cooper Norcross HS); ES report card
  `DD312901-BD2A-D9FA-63DA-5134AB473955` (owner KIPP Lanning Square Primary).

## Review Focus

- A student with no PROMOSTAT row for the term must print `-`, never `undefined`
  or a blank page. Owned by Tasks 4 and 5 (gate plus render check).
- Camden detection that silently fails falls back to 90%; a Camden grade 5-8
  letter must print 88%. Owned by Task 4 (render check).
- The Spanish warning labels are longer than the English ones, and the ES report
  card's Overall cell does not wrap. Owned by Task 7 (render check).
- A missing translation prints English; confirm on one Spanish letter and one
  Spanish report card before Friday. Owned by Task 7.
- Each source is shared by every school that installs it, so a paste changes all
  of them at once, including schools that are not printing. Owned by Task 6
  (paste list names this).

---

### Task 1: Label ladder in `rpt_deanslist__promo_status`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__promo_status.sql:55-76`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__promo_status.yml`

**Interfaces:**

- Produces: `promo_status_overall` and `promo_status_grades` with the values
  below; every other column is unchanged. DeansList reads them as the
  `PROMOSTAT` custom data object.

- [ ] **Step 1: Write the failing unit test**

Invoke `dbt-local-dev` before running dbt. Add `unit_tests:` to the properties
file: `test_rpt_deanslist__promo_status_labels`, with
`overrides: vars: {current_academic_year: 2026}`. Mock all five refs with
`format: sql` (`int_extracts__student_enrollments`, `int_powerschool__gpa_term`,
`int_students__promotional_status`, `int_students__athletic_eligibility`,
`int_powerschool__log`); the last three may return zero rows (`where false`) as
long as they carry the columns the model reads. Enrollment rows: region
`Newark`, `rn_year = 1`, `academic_year = 2026`. Promotional status rows exist
for `term_name = 'Q1'` only.

| student_number | grade_level | overall_status | academic_status | attendance_status | expected promo_status_overall | expected promo_status_grades |
| -------------- | ----------- | -------------- | --------------- | ----------------- | ----------------------------- | ---------------------------- |
| 1              | 6           | Off-Track      | Off-Track       | Off-Track         | At-Risk for Retention         | Off-Track                    |
| 2              | 6           | On-Track       | Off-Track       | On-Track          | On-Track (Academic Warning)   | Off-Track                    |
| 3              | 2           | On-Track       | On-Track        | Off-Track         | On-Track (Attendance Warning) | On-Track                     |
| 4              | 1           | On-Track       | Off-Track       | On-Track          | On-Track (Academic Warning)   | Off-Track                    |
| 5              | 10          | On-Track       | Off-Track       | On-Track          | On-Track                      | Off-Track                    |
| 6              | 4           | On-Track       | On-Track        | On-Track          | On-Track                      | On-Track                     |
| 7              | 7           | Off-Track      | On-Track        | On-Track          | At-Risk for Retention         | On-Track                     |

Expect (`format: sql`) columns
`student_number, term, promo_status_overall, promo_status_grades`: the Q1 rows
above, plus Q2-Q4 rows for all seven students with both status columns null (the
model cross-joins four terms).

- [ ] **Step 2: Run it and confirm it fails**

Run from `src/dbt/kipptaf`:
`uv run dbt test --select "rpt_deanslist__promo_status,test_type:unit"` with the
defer flags `dbt-local-dev` prescribes. Expected: FAIL, with students 2, 3 and 4
showing the old `Off-Track: ...` labels.

- [ ] **Step 3: Implement the ladder**

`promo_status_grades` becomes the plain `p.academic_status` column. Move it into
the `p.` plain-column group (S6). `promo_status_overall` is a `case`, first
match wins, all branches inside the existing NJ-region condition:

1. policy `overall_status = 'Off-Track'` -> `At-Risk for Retention`
2. `grade_level < 9`, academic `Off-Track`, attendance `On-Track` ->
   `On-Track (Academic Warning)`
3. `grade_level < 9`, attendance `Off-Track`, academic `On-Track` ->
   `On-Track (Attendance Warning)`
4. else policy `overall_status`

Put a one-line comment on the `< 9` branches: K-8 only; grades 9-12 keep the
policy status (S20).

- [ ] **Step 4: Run the unit test and confirm it passes**

Same command as Step 2. Expected: PASS.

- [ ] **Step 5: Describe the model and every column**

Model description: what the extract is (one row per enrolled NJ student per
quarter of the current year, uploaded nightly to DeansList as the `PROMOSTAT`
custom data object for report cards and promotion-in-doubt letters) and that the
overall labels mirror the Promotional Status dashboard. Column descriptions for
the three status columns must state the value set and the rule above; describe
the rest from the SQL. Keep `student_number` (it has a column test) first in
`columns:`.

- [ ] **Step 6: Build in dev and project the counts**

`uv run dbt build --select rpt_deanslist__promo_status` (contract, grain test,
unit test). Then query the dev relation: count Q1 enrolled K-8 rows by
`promo_status_overall`. Expected, within daily drift of the 11/11 numbers:
`At-Risk for Retention` about 518, `On-Track (Academic Warning)` about 2,413,
`On-Track (Attendance Warning)` about 440, and zero values starting
`Off-Track:`. Grades 9-12 counts unchanged from prod.

- [ ] **Step 7: Lint and commit**

`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <sql> <yml> </dev/null`
from the worktree; fix findings. Then:

```bash
git -C <worktree> add src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__promo_status.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__promo_status.yml
git -C <worktree> commit -m "fix(dbt): match DeansList ARFR labels to the dashboard"
```

### Task 2: Pull request, merge, and prod check

**Files:** none (PR, prod verification).

**Interfaces:**

- Consumes: Task 1's commit.
- Produces: the merged view in prod and one DeansList upload carrying the new
  labels.

- [ ] **Step 1: Push and open the PR**

Body from `.github/pull_request_template.md`; `Closes #5677`. The branch is
linked to #6336, so merging closes it. Offer to watch CI and handle the
`claude-review` findings (`pr-ci-review`).

- [ ] **Step 2: User merges when CI is green**

Merge as soon as CI and review are clean; it does not wait on the template work.
Letters and the ES report card do not read the changed labels.

- [ ] **Step 3: Confirm the prod view rebuilt**

Query `kipptaf_extracts.INFORMATION_SCHEMA.VIEWS` for
`rpt_deanslist__promo_status`; expected: `view_definition` contains
`On-Track (Academic Warning)`. If not after the deploy settles, rematerialize
the asset with `mcp__dagster-plus__launch_asset_run` (one asset).

- [ ] **Step 4: Rerun Task 1 Step 6's count against prod**

Expected: the same distribution.

- [ ] **Step 5: Run the DeansList upload once, with the user's OK**

Launch `kipptaf__extracts__deanslist_annual__asset_job` once. Expected: the run
succeeds. The 1:25 am schedule is the backstop. Post a status comment on #6336
naming what is still open on the template side.

### Task 3: Pull and baseline the three live sources

**Files (all under `.claude/scratch/deanslist/`, gitignored):**

- Create: `report/live-2026-11-11/<Report>/` for `Promotion in Doubt Letter`,
  `ES Report Card`, `MS Report Card` (file names per `platform-access.md`:
  `<report>.css`, `<report>_head.html`, `<report>.html`, `<report>.js`)
- Create: `report/baselines/<Report> @ 20261111-<HHMM>/` with `SHA256SUMS`

**Interfaces:**

- Produces: byte-exact live copies that Tasks 4-5 read and never edit.

- [ ] **Step 1: Seed local candidates**

Start from the 10/06/2026 Drive exports in the "DeansList-Report-Config" folder
(`1iDB2ZHQxygWYdWhZtnrgG8WTKkgWwFaE`), downloaded byte-exact. The letter was
last saved 11/16/2025 and the MS report card 5/29/2026, so both should match
live.

- [ ] **Step 2: Compare against live**

In the user's Chrome, follow `skill-brief/platform-access.md`: snippets block 2
(checksum) per pane. Where a pane differs, block 3 line diff plus
`scripts/tools/rm-apply-hunks.py`, then re-check. Expected: block 2 returns
`MATCHES` for all 12 panes.

- [ ] **Step 3: Snapshot the baselines**

Copy the 12 files to the baseline folders with `SHA256SUMS`. Expected:
`sha256sum -c` passes in each.

### Task 4: Letter splice (`scripts/build-chain/pid-letter-2627.py`)

**Files:**

- Create: `.claude/scratch/deanslist/scripts/build-chain/pid-letter-2627.py`
- Create:
  `.claude/scratch/deanslist/report/paste-2026-11-11/Promotion in Doubt Letter/`
  (all four files; unchanged panes copied as is)

**Interfaces:**

- Consumes: Task 3's live letter.
- Produces: paste targets plus a printed list of changed panes and their line
  counts.

- [ ] **Step 1: Write the script with asserted anchors**

Follow `skill-brief/build-methodology.md`: locate every anchor by exact bytes,
assert all of them before writing, abort on any count other than expected, and
assert post-conditions. Edits:

1. JS query: add `city` to `schools { ... }`; set `data.camdenFlag` from
   `schools[0].city === "Camden"`.
2. JS: `attendancePct` is 88 when `camdenFlag`, else 90 (feeds the grade 5-8
   requirement text only).
3. JS: `statusAttendance` is `Met` when `promo_status_attendance` is `On-Track`,
   `Not Met` when it is any other non-empty value, `-` when the row or value is
   missing. Remove the `>= attendancePct` comparison.
4. JS: `statusMath` and `statusReading` map `promo_status_math` /
   `promo_status_lit` the same way (`On-Track` -> `Met`, `Off-Track` ->
   `Not Met`, missing -> `-`).
5. JS: `showDibels` is true for grade short names `K`, `1st`, `2nd`.
6. Head, chart partial, Reading row: when `showDibels`, the Data cell prints
   `dibels_composite_recent` through `dlrc_translateText`; otherwise the current
   i-Ready cell. In the elementary requirement text, add the K-2 note.
7. Head, chart partial: Math and Reading status cells print `statusMath` /
   `statusReading` through `dlrc_translateText`.
8. Head, chart partial, Core classes requirement cell: when `camdenFlag`, append
   the Camden sentence.

Post-conditions: the K-2 note, the Camden sentence, `camdenFlag`,
`promo_status_attendance` and `dibels_composite_recent` present; the literal
`data.attendancePct = 90;` gone; `registerPartial` ids unchanged.

- [ ] **Step 2: Run the gates**

`node --check` on the JS;
`uv run scripts/tools/validate-report-queries.py schema/introspection.json "<paste js>"`
(expected `N/N documents validate`); cross-file partial check; re-run the script
and `diff -r` (no differences).

### Task 5: ES report card splice (`scripts/build-chain/es-rc-2627.py`)

**Files:**

- Create: `.claude/scratch/deanslist/scripts/build-chain/es-rc-2627.py`
- Create: `.claude/scratch/deanslist/report/paste-2026-11-11/ES Report Card/`

**Interfaces:**

- Consumes: Task 3's live ES report card.

- [ ] **Step 1: Confirm grade short names**

Read-only GraphiQL query of the grade levels at Sumner (no student fields).
Expected: the short names the script will match for grades 5 and 6.

- [ ] **Step 2: Write the script with asserted anchors**

1. `showPromoAcademicsDibels` covers `K`, `1st`, `2nd`;
   `showPromoAcademicsIready` excludes all three.
2. `promoAcademicsLabel` / `showIreadyMath`: drop the 2nd-grade i-Ready branch;
   grades 3-6 get `(i-Ready reading & math)` and the Math line.

Post-conditions assert both lists; JS is the only pane that changes.

- [ ] **Step 3: Run the gates**

Same as Task 4 Step 2.

### Task 6: Paste list and paste

**Files:**

- Create: `.claude/scratch/deanslist/report/paste-2026-11-11/PASTE-LIST.md`

- [ ] **Step 1: Write the paste list**

Per report: which panes changed, paste order (CSS, head, body, JS), each file's
line count and one distinctive string, what a partial paste looks like (for
example, letter JS without head: K-2 rows still show i-Ready), and that every
school with the source installed changes at once.

- [ ] **Step 2: User pastes and saves; agent confirms**

After each save, snippets block 2 against the paste targets. Expected: `MATCHES`
for every pane, and `UpdatedAt` moved.

### Task 7: Render tests, translations, and Paterson check

**Files:** none.

- [ ] **Step 1: Hand the user the translation list**

The two warning labels, the K-2 note, the Camden sentence, and the DIBELS level
strings found in `dibels_composite_recent`. Spanish wording comes from Teaching
& Learning; entry in the DeansList translations grid.

- [ ] **Step 2: User renders; agent reads screenshots**

Letters: a K-2 student (DIBELS in Data, note shown), a Camden grade 5-8 student
(88%, Camden sentence, Met/Not Met consistent with the dashboard), a Newark
grade 5-8 student (90%, no Camden sentence), one Spanish letter, and a student
with no PROMOSTAT row (`-` everywhere, page renders). Report cards: a 2nd grader
(DIBELS row), a Sumner 6th grader (label and Math line), and, after Task 2 Step
5, a middle school student with each warning label in English and Spanish (fits
the Status column).

- [ ] **Step 3: Paterson installation check, with the user's OK**

Switch the DeansList school to a Paterson school, list its report cards and
letters, switch back. Report whether the letter and both report cards are
installed there; installing them is an admin action for the user.

- [ ] **Step 4: Close out**

Comment on #6336 with what shipped and any open item.
