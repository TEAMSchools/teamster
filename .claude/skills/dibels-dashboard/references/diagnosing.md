# Diagnosing and verifying

What to do before reporting a gap, and the checks a field change runs before
anyone trusts it.

## What's in here

- Explain a gap before reporting it
- A whole region missing: read Amplify's file before tracing any join
- SY2026-2027 header rename: null ids are a column move, not missing data
- Verifying a year that is not in prod yet -- go to the source
- "It should match prod" means diff every column, not the row count
- Check the paste before anyone trusts it
- Every field change runs this check sequence before you report it
- The PM branches cannot match prod's row count, and should not
- A student's two grade columns can disagree -- known, and not fixable
- A stale dev relation will hide a filter you removed

## Explain a gap before reporting it

Missing DIBELS data usually has a boring, checkable cause, and this model has
the calendar that explains most of them. **Before presenting an absence as a
finding, a limitation, or a constraint on someone's plan, spend the one query it
takes to find out why.** Both of these were stated to the user as facts to work
around, and both dissolved on a single lookup:

- "Miami has no AY2026 BOY scores yet, so its calculations cannot be verified."
  `reporting__terms` says Miami's BOY window is 9/8 to 9/25 and the date was
  9/6. It had not opened. The other three regions opened in mid-August, which is
  why only they had scores. Nothing to plan around -- it resolved that week.
- "`grade_band` also holds `ES` and `MS`, so how should the CTE treat them?"
  Those rows are AY2010-2022 and expected assessments starts at AY2023, so they
  can never reach the model on the year join. The question was moot.

The checks worth reaching for first, in order: is the window open yet
(`reporting__terms` dates against `current_date`), is the year switched off
(`assessment_include`), does the region run that measure at that grade at all
(the T&L doc), and does the year even overlap the other side of the join.

`rpt_gsheets__dibels_pm_goal_setting` returning zero rows is the same class of
thing -- it filters `academic_year = current_academic_year`, so it is empty
whenever the new year's PM calendar has not been entered. Empty is the expected
state mid-rollover, not a defect.

## A whole region missing: read Amplify's file before tracing any join

When the calendar checks above pass and an entire region still has no scores,
**the export itself is the first suspect, not the pipeline.** On 2026-09-15 I
gave the user three wrong causes for Miami's empty AY2026 dashboard -- a missing
union member, a crosswalk gap, then the `is_self_contained` exclusion -- before
checking the top of the hierarchy, where the answer was sitting: Amplify's
SY2026-2027 export contained no Miami schools at all on that date. By 2026-09-22
Amplify had added 4 Miami schools back under a new `district_name`,
`Kipp Florida` (the NJ schools moved to `Kipp New Jersey`). The export moves
under you; re-run the query, do not trust the last answer.

Run this before anything else:

```sql
select
    school_year,
    district_name,
    school_name,
    count(*) as n_rows,
    count(distinct student_primary_id) as n_students,
    cast(max(sync_date) as string) as last_sync,
from `teamster-332318`.kippnewark_amplify.benchmark_student_summary
where school_year = '2026-2027'
group by school_year, district_name, school_name
order by school_name
```

That is the external over the landed file -- the top of the hierarchy, no
dependencies. Swap the year to see the contrast with SY2025-2026.

Four rules for this class of question:

- **`kippmiami_amplify` is deliberately absent from the union.** Amplify exports
  one network account and it lands in `kippnewark`'s bucket; region comes from
  `int_people__location_crosswalk`. Do not "fix" the union.
- **Amplify renames schools between years, and the rename is not the bug until
  you prove it.** `Kipp Hatch Middle` became `Kipp Hatch Academy` and
  `Kipp Sumner Elementary` became `Kipp Sumner Academy` for SY2026-2027; the
  crosswalk absorbed both. A rename it misses produces a **null region**, not
  missing rows -- so compare row counts layer by layer and check for null
  regions before concluding anything. Identical counts across layers means
  nothing is being dropped at the join. Example: `Kipp Legacy Elementary` and
  `Kipp Legacy Middle` (Miami, ~205 students) arrived in the SY2026-2027 file
  with no crosswalk row and read as null region until Ops added them to the
  sheet on 2026-09-22. The fix is a sheet row, not dbt; verify it by reading the
  sheet external through ADC (the MCP cannot), then wait for the staging
  rebuild.
- **Confirm by student number, not by school name.** Matching the file's student
  id against enrollment rules out a rename entirely, because it never touches a
  name. That is the check that actually closes the question. Which column holds
  the id depends on the year -- see the header rename below.
- **Reading the raw SFTP file is available and cheap.** Credentials come from
  the pytest session fixture, so a throwaway `tests/**/test_zz_*.py` using
  `SSH_RESOURCE_AMPLIFY.process_config_and_initialize()` plus
  `setup_for_execution(build_init_resource_context())` can list the tree and
  download a file. Do not report an export as empty without it when the question
  is whether the vendor sent the data. Print aggregates only, never student
  rows, and delete the test file afterwards.

Two facts about the remote layout, current as of 2026-09-15: SY2025-2026 files
live under `/25-26/BM` and `/25-26/PM` while SY2026-2027 files are at `/BM` and
`/PM`, and every file is a daily cumulative snapshot (704 of them), so the asset
takes the newest match by mtime. Since 2026-09-22 the kippnewark assets list the
`/YY-YY/<BM|PM>` archive directory when the current directory has no match for
the partition (`archive_remote_dir` in the kippnewark assets module), so a
closed-year re-pull works and a just-closed year still resolves while Amplify
has not moved it yet. The sensor still matches only `/BM` and `/PM`; it never
triggers on the archive folders. Amplify keeps refreshing the archived year
daily (2026-09-22: the newest `/25-26/PM` file was dated 2026-09-21), so a
re-pull lands a newer snapshot of the same export.

## SY2026-2027 header rename: null ids are a column move, not missing data

Amplify dropped the parenthetical qualifiers from the id headers in the
SY2026-2027 BM and PM files, so `slugify` produced new column names:
`student_primary_id_studentnumber` -> `student_primary_id`,
`enrollment_teacher_staff_id_teachernumber` -> `enrollment_teacher_staff_id`,
`assessing_teacher_staff_id_teachernumber` -> `assessing_teacher_staff_id`,
`secondary_student_id_stateid` -> `secondary_student_id`,
`additional_student_id_primarysisid` / `_sisid` -> `additional_student_id`. Each
year populates only its own column.

Two failure shapes follow from it, and they look different:

- **BM**: the Avro schema already carried both names, so the new column landed
  in the warehouse with values and the old one went null. Symptom: the staging
  `unique_combination_of_columns` test fails with exactly one duplicate key per
  grade (all-null id). Fix shipped 2026-09-22: the staging model coalesces the
  two columns.
- **PM**: the Avro schema (`PMStudentSummary` in
  `src/teamster/libraries/amplify/mclass/sftp/schema.py`) lacked the new names,
  so `fastavro` dropped the columns and SY2026-2027 PM rows had NO id column at
  all. The 5 fields were added to the schema on 2026-09-22 and both PM
  partitions were re-pulled that day. The PM staging model keeps the OLD names
  in its contract and folds each new column into its old one; the new
  `additional_student_id` maps to `additional_student_id_sisid`, because that is
  the column SY2025-2026 PM rows fill (61,387 of 61,387; `_primarysisid` is
  empty). The re-pull alone broke prod: `select *` passed the 5 new columns
  through and the contract failed with "missing in contract". Any future Avro
  field add on a contracted `select *` staging model needs the staging change in
  the same deploy as the re-pull.
- **Miami school ids went alphanumeric in SY2026-2027** (`2332A`, `2008A`), so
  the PM `cast(school_primary_id as int)` failed with `Bad int64 value`. Both PM
  staging models now keep it as a string, like BM. The user chose this over
  `safe_cast` on 2026-09-22 so the vendor id is not silently nulled. The kipptaf
  PM intermediate casts both coalesce inputs to string, so it works whether a
  district copy is still int64 or already string. Nothing downstream joins on
  `school_primary_id`; region and school come from the crosswalk on
  `school_name`.

A `dibels8_PM_CUSTOM_2026-2027` aimline file was not on the server as of
2026-09-22; that asset partition is expected to be missing.

## Verifying a year that is not in prod yet -- go to the source

When you need to check something about an academic year whose rows are not in
prod (or not pasted into the sheet yet), **verify against the document the rows
came from, not against rows you generated**. Your own generated output is a
transcription; checking it against itself proves nothing about the source.

The T&L PM rounds document is that source:
<https://docs.google.com/document/d/12ZDlAJY_IgSS4yElBAFWouJ6_M8982j1Fb1B93-INjU>

For **benchmark** goals -- the foundation goals paste, not PM rounds -- the
academics source is a separate sheet:
<https://docs.google.com/spreadsheets/d/1-fLmFQz94yAuotVYkzTxOxv6O129V3I2LDhdPY16HIc>

Academics replace this each year, so re-read it rather than trusting the values
recorded here, and update this link if they move it.

**Reading it needs ADC from Python -- both MCP routes fail.** Do not spend time
rediscovering this:

- The **BigQuery MCP cannot read a Sheets external at all.** Its service account
  carries no Drive scope, so `src_google_sheets__*` returns
  `Permission denied while getting Drive credentials`. Sharing the file with
  anyone changes nothing -- it is a missing OAuth scope, not a file permission.
- The **Drive MCP reads it, then `check-output.sh` redacts the whole response**
  as containing a high-entropy string, which any real spreadsheet has somewhere.
  `read_file_content` and `get_file_metadata` both come back as
  `[redacted: secret material]` with no content.

What works is `scripts/read_sheet_tabs.py`, which requests
`spreadsheets.readonly` and `drive.readonly` through ADC and writes each tab to
a local TSV:

```bash
uv run --with google-api-python-client --with google-auth python \
    .claude/skills/dibels-dashboard/scripts/read_sheet_tabs.py \
    <spreadsheet_id> .claude/scratch dibels
```

The third argument filters tabs by substring, which matters on the academics
workbook -- it carries 15+ tabs and only `DIBELS Goals` is the goal source. Then
Read the TSVs.

Two things that make it work, both easy to undo by accident. It prints only tab
names and row/column counts, never cell values, so the output scanner has no
payload to catch -- if you add a line that echoes sheet contents, the whole run
gets redacted again. And keep the output directory free of UUIDs: passing a path
containing the session id redacts the run, because the scanner reads the UUID
itself as high-entropy.

What the sheet decides:

**Grades 6-8 are goal-set at EOY only.** Verified identical in AY2025 and
AY2026: grades K-5 carry both MOY and EOY foundation goals, grades 6-8 carry EOY
alone. This is academics' intent, not a truncated paste -- confirm the shape
before reporting a gap.

That shape collides with how `benchmark_goal_season` works.
`int_amplify__all_assessments` sets it to the goal season a row is measured
AGAINST, which is the NEXT one: a BOY row carries `MOY`, an MOY row carries
`EOY`, an EOY row carries null. `rpt_gsheets__dibels_bm_goals_calculations`
joins `a.benchmark_goal_season = f.period`, so a **BOY** row needs an **MOY**
foundation goal. Grades 6-8 have none, the LEFT join misses, `grade_goal_type`
comes back null, and `where c.grade_goal_type = 'At/Above'` drops the row. So
grades 6-8 produce no BOY benchmark goals at all; they appear only once MOY
testing lands, where their EOY goal does match.

Consequence for the rollover: the first paste of a year covers **K-5 only**
(measured 2026-09-14: 49 rows, BOY, grades 0-5, 16 schools). Do not read the
missing grades as a broken foundation paste -- the 6-8 EOY values are present
and populated; the model never consults them at BOY.

**Reading the foundation goals columns.** Two columns decide which goal a row
gets, and neither name says so on its own:

- `period` is the administration the goal is FOR -- an `MOY` row is the goal for
  the MOY administration, an `EOY` row the goal for EOY. It is not the date the
  goal was set.
- `grade_goal_type` selects WHICH foundation aggregate applies: `At/Above` or
  `Well Below`. On the assessment side the counterpart is
  `foundation_measure_standard_level`, the student's own composite bucket, and
  `rpt_gsheets__dibels_bm_goals_calculations` joins the two so a student is
  measured against the aggregate matching their level.

`benchmark_goal_season` on the assessment side is the season a row is measured
AGAINST, which is the next one (`BOY -> MOY`, `MOY -> EOY`, `EOY -> null`). The
join is `a.benchmark_goal_season = f.period`, so a BOY row looks for the goal
FOR MOY.

**This is correct behaviour, not a bug.** The academics sheet sets MOY and EOY
goals per grade, and grades 6-8 deliberately get EOY only -- K-2 and 3-5 carry
both. K-2 is also the only band with `grade_range_goal` populated. Verified
against AY2026: grades 0-5 have 6 MOY and 6 EOY rows each, grades 6-8 have 0 MOY
and 6 EOY, and only grades 0-2 have non-null range goals.

Because a BOY row is measured against the MOY goal, grades 6-8 have nothing to
measure against at BOY, and a blank goal is the honest output. They pick up
their goal once MOY testing lands, where `MOY -> EOY` matches their EOY row. So
the first paste of a year covering K-5 only is expected; do not widen the join
to reach the EOY goal early -- an EOY target is not a mid-year one, and
academics chose not to set a mid-year target for these grades.

**Do not use the AY2025 `bm_goals` tab as evidence against this.** It does
contain grades 6-8 at `period = 'BOY'` carrying the foundation EOY goal, which
looks like precedent for an EOY fallback. It is not: no version of
`rpt_gsheets__dibels_bm_goals_calculations` ever produced those rows -- the join
has been `a.benchmark_goal_season = f.period` since `aac3e5a86`, and
`benchmark_goal_season` has always been the plain next-season map (`BOY -> MOY`,
`MOY -> EOY`), never grade-aware. The tab is a manual-freeze snapshot, so those
rows were hand-filled, and they carry errors that prove it: Paterson grade 6
reads `0.53` against a foundation EOY of `0.30`, and grade 7 reads `0.34`
against `0.33`, both of them Newark's value. This cost a full investigation
cycle in September 2026; the tab is not a specification.

Separately, **Miami has benchmark goals in that tab but no foundation goals at
all.** Foundation goals cover Camden, Newark and Paterson only, so Miami's
numbers come from outside this lineage.

It is a Google Doc, not a Sheet, so
`mcp__claude_ai_Google_Drive__read_file_content` returns the whole thing with
its region headings intact (`# Newark & Paterson`, `# Camden`, `# Miami`) --
provenance comes for free, unlike the multi-tab Sheet problem described in
`.claude/context/claude_ai_Google_Drive.md`. It reads as the USER's identity, so
it works even when the doc is not shared with the ADC service account.

Worked example. Asked whether SY26-27 would repeat SY25-26's null
`benchmark_goal` rows (Miami testing Word Reading at grades 4-5, above its 0-3
goal range, and Reading Accuracy at grade 0, below its 1-8 range), checking the
generated rows said no. Confirming against the doc is what made that answer
trustworthy: Miami's SY26-27 set has no Word Reading at any grade, and Kinder
gets PSF and NWF only. The single Word Reading combo in SY26-27 is Newark and
Paterson's Kinder at rounds 7-8, which `dibels_goals_long` does cover.

`stg_google_sheets__dibels_goals_long` carries no `academic_year` -- goals are
year-agnostic, so its coverage table serves every year at once. A year "clears"
by having its measure/grade/season combos land inside that one table.

**That table is University of Oregon's, not ours, and it has not changed
since 2020.** Verified against UO's own PDF, which states
`Goals Updated: July 2020` and `Reformatted: October 2025`:
<https://dibels.uoregon.edu/sites/default/files/2026-06/dibels-benchmark-goals-all-grades.pdf>
Do not read the `2026-06` in that path as a new edition -- it is the CMS upload
folder for the 2025 reformat, and the goal values are still 2020's. The PDF also
confirms the coverage boundaries are the assessment's design rather than a
transcription gap: Word Reading appears only in the Grades K-3 section with no
Grades 4-8 table at all, ORF Accuracy leaves the three Kinder columns blank, and
Maze leaves Kinder and First blank. `stg_google_sheets__dibels_goals_long`
matches that exactly -- WRF 0-3, ORF-Accuracy 1-8, Maze 2-8 -- so treat the
sheet as a faithful copy rather than something to extend. So a missing goal is
never a KTAF data-entry gap to fill -- UO defines no goal where the measure is
not designed to be administered at that grade (Word Reading is a K-3 measure;
Reading Accuracy needs oral reading, so not kindergarten). A null
`benchmark_goal` downstream therefore means **a measure was assigned outside its
valid grade range** on the Expected Assessments sheet. Raise it with academics
as a testing-assignment error; do not propose adding rows to the goals table,
and do not treat the null as noise -- it makes the at-or-above-benchmark
comparison unevaluable, which is exactly the test that separates On Track &
Meeting Aimline from Meeting Aimline, Off Track.

## "It should match prod" means diff every column, not the row count

When the user says a model should match prod, a row-count and key-set comparison
is not enough -- and on a model whose prod copy is fanned out, the counts cannot
match by construction anyway. Compare `distinct` full rows, then join on the key
and `countif(p.col is distinct from d.col)` per column. On the internal
`pm_expectations` port that check passed on `round_number`, `month_round`,
`start_date`, `end_date`, `pm_round_days`, `pm_days`, `pm_goal_include` and
`benchmark_goal`, and isolated the entire delta to two window columns -- which
is what identified the cause in one query instead of a model-by-model hunt.

**Which years and grades are live is a sheet decision, not a SQL one.**
`assessment_include` is the off switch: null means live, non-null means
excluded, and consumers express that as `assessment_include is null`. Do not add
year filters to the model -- flip `assessment_include` instead. Currently off:
all AY2024 PM rows on both tabs, and 99 AY2023 Benchmark rows (upper grades did
not sit Benchmark that year).

## Check the paste before anyone trusts it

Four checks against `stg_google_sheets__dibels_pm_goals` after a rebuild. The
failure modes are paste-shaped -- a fanned-out source, a shifted column, a
partial selection -- and these catch all of them.

1. Rows equal distinct rows on `academic_year`, `region`, `admin_season`,
   `assessment_grade_int`, `measure_standard`, `round_number`.
2. Each season's last round equals `benchmark_goal_padded`. The calculation pins
   it there, so a deviation is a paste problem, not rounding.
3. Every earlier round equals the running sum of `round_growth_words_goal`.
4. `benchmark_goal` equals `goals_long.grade_level_standard`, and
   `benchmark_goal_padded` that plus three -- confirms the row landed against
   the right measure and grade, not just that the arithmetic is self-consistent.

Known state as of this branch: AY2025 passes all four but for one row whose last
round sits 11 words under target; AY2024 has 24 rows off on check 2 and 8 on
check 3, which is hand arithmetic from before the automation rather than a
defect. Show the AY2025 row to academics rather than fixing it -- the sheet
records what the goals were.

## Every field change runs this check sequence before you report it

Standing instruction from the dashboard owner, 2026-09-19, after a week in which
unverified model changes made the Tableau build harder than the data warranted.
Run ALL of it after ANY column add, rename, drop or logic change in the DIBELS
chain. Do not report a change as done on a subset.

1. **Read back what changed.** `git diff --name-only`, then `git diff` on the
   SQL. A scripted edit is not evidence it landed where intended.
2. **Union-branch balance**, whenever `rpt_tableau__dibels_dashboard` is
   touched:
   `uv run python .claude/skills/dibels-dashboard/scripts/diff_union_branches.py <abs path>`.
   All three branches must report the same projection count and **0 mismatched
   ordinals**. BigQuery binds UNION ALL by POSITION, so a column added or
   removed on one branch needs the same on the other two.
3. **Contract column count matches the SQL.**
   `grep -c "^      - name: " <properties yml>` against the projection count
   from step 2. A rename can silently leave a DUPLICATE entry when the new name
   already exists in the yml; grep the new name and confirm it appears once.
4. **Dev build, green.** From the main checkout:

   ```bash
   uv run dbt build --project-dir <worktree>/src/dbt/kipptaf \
     --favor-state --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
     --select <every changed model and its extract>
   ```

   `--favor-state` ALONE is not enough -- it does not shadow a stale personal
   dev copy, and this chain has one (`int_amplify__mclass__pm_student_summary`
   in at least one developer schema predates the `device_date` rename, failing
   with `Name device_date not found inside p`). `--defer --state` is what fixes
   it, and from a worktree the state path must be ABSOLUTE.

5. **Dev values against prod.** Query `zz_<user>_kipptaf_tableau` and
   `kipptaf_tableau` side by side, grouped by `model_type`, counting each
   distinct value of the changed column including nulls. For a rename or a
   refactor every cell must match exactly; for a logic change, the deltas must
   be the ones you intended and no others.
6. **Column presence.** `INFORMATION_SCHEMA.COLUMNS` on the dev relation -- the
   new name present, the old name absent.
7. **Lint.**
   `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <changed files> </dev/null`,
   with `trunk fmt` first if it reports formatting.
8. **Update this skill and the reference document in the same turn**, not later.
   Also flag any Tableau workbook exposure you could not verify -- the
   datasource is embedded and VizQL returns 500 on those, so a dropped or
   renamed column breaks a bound calc SILENTLY on the next extract refresh
   rather than erroring. That check needs a human in Desktop.

`dbt` and `trunk` output both trip the output scanner on high-entropy strings
and come back fully redacted. Redirect to a file and pull specific patterns
(`grep -oE "PASS=[0-9]+|ERROR=[0-9]+"`) rather than re-running to see it.

## The PM branches cannot match prod's row count, and should not

Do not treat a PM row-count difference against prod as a regression to fix. The
branches drop scores from students who were never PM-eligible. Measured on
AY2025, prod carried 8,253 such rows -- 8,170 for 3,024 students whose composite
was At/Above Benchmark, and 83 for 28 students with no benchmark row at all.

Those students were already invisible downstream -- the participation roster and
the dashboard each re-derive eligibility independently, and both return zero
rows for them. Verify that before accepting the drop, then treat the change as
consolidating one gate from three places to one.

## A student's two grade columns can disagree -- known, and not fixable

On a PM row, `assessment_grade` comes from the score side (the grade the probe
was administered at) and `assessment_grade_int` comes from the benchmark side
(the grade the student was benchmarked at). A student who changes grade level
mid-year has both, and they differ. Measured on AY2025: one student, four rows,
`assessment_grade = '4'` against `assessment_grade_int = 3`.

**This is known and accepted. Neither column is wrong** -- the student really
did sit their benchmark at one grade and their progress monitoring at another.
Do not "fix" it by sourcing both from one side. Both from the score side matches
prod, but the row would then claim grade 4 while carrying the round windows and
expected measures that came from grade 3's gate row. Both from the benchmark
side keeps the row coherent with its expectations, but discards the grade the
probe was actually sat at.

**The dashboard is unaffected; the participation roster is not.** An earlier
version of this section said it "settles at the reporting layer" full stop. That
was too broad -- the two consumers join the grade differently.

`rpt_tableau__dibels_dashboard`'s PM branch drives off the student's enrollment
record -- `int_extracts__student_enrollments_subjects` joined to
`int_google_sheets__dibels_pm_expectations` on `s.grade_level = e.grade` -- so
the ENROLLED grade decides which expectations the student is held to, and the
score is attached with a LEFT JOIN on year, season, round, measure and student
number, **with no grade predicate at all**. Whichever grade the PM row carries,
the score lands on the enrolled-grade expectation row.

`int_students__dibels_participation_roster` DOES put grade in its score join
(`s.grade_level = a.assessment_grade_int`), so a PM row keyed to the benchmark
grade misses a student enrolled at the probe grade and `actual_row_count`
reads 0. Measured on AY2025: one row, Newark grade 4, BOY->MOY round 2, prod 2
against 0. `completed_test_round` is false on both sides, so nothing reported
moves -- the count is just understated. Expect it when every measure in a round
landed at the other grade.

The remaining consequence is internal: these rows key to a different grade than
prod does, so a prod-versus-branch comparison always shows them as branch-only.
Confirm the count is still tiny, then move on.

What _must_ match prod is the Benchmark half. That was verified byte-for-byte:
337,073 rows, 38 columns, zero differing values.

## A stale dev relation will hide a filter you removed

After the `assessment_grade_int >= 3` floor was removed from
`int_amplify__mclass__pm_student_summary_aimline`, downstream queries still
returned grades 3-8 only. The SQL was correct; the dev relation was not rebuilt,
and dbt prefers an existing dev relation over the deferred prod one. Rebuild the
edited model before reading anything downstream of it, and reach for
`--favor-state` when deferring. Same trap with the Google Sheets externals: the
external reads the sheet live, but `stg_*` is frozen at its last build, so a
fresh paste is invisible until you rebuild the staging model.

Watch for orphaned relations from renames too -- `__dibels__` (double
underscore) renames left single-underscore copies of both by-levels models in
the dev and PR schemas. They resolve, they hold stale data, and nothing points
at them.
