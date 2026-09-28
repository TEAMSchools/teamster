# Goals sheet: reconciliation and gap rows

Reconciles the `Finalsite` goals sheet (the one dbt reads) against SRE's target
workbook. How to read SRE's workbook, its tab maps and its rounding are in
[sre-workbook.md](sre-workbook.md); read it before step 3.

## The reconciliation loop

1. **Ask for the workbook URL — actually ask, in a message, before reading
   anything.** SRE issues a new one each cycle. **A recorded id that still opens
   and still carries a plausible current-cycle title is NOT confirmation** — a
   superseded copy keeps both. This step has been skipped on the reasoning that
   the recorded id "resolved to `26-27 …`, which matches
   `finalsite_recruitment_year`, so it must be current"; that inference is
   invalid and the user ended up supplying the URL unprompted. Ask first, then
   read.
1. **Confirm goal names are unchanged.** The goals sheet joins on `goal_name`,
   so a rename silently stops matching rather than erroring. Compare SRE's goal
   labels against `distinct goal_name` in `stg_google_sheets__finalsite__goals`
   and surface any that don't appear.
1. **Compare all three granularities, not just the cover sheet.** Compare
   against `stg_google_sheets__finalsite__goals` on
   `(region, schoolid, grade_level, goal_type, goal_name)`, and classify each
   difference as missing / extra / value-mismatch. **SRE's cover sheet only
   carries `School` rows (`grade_level = -9`)** — `School/Grade Level` and
   `Region/Grade Level` rows come from the per-region tabs, and grade-level
   goals DO change independently of the school totals. A reconciliation that
   stops at the cover sheet is incomplete; say so explicitly rather than
   implying the sheet is clean.

   **`Region/Grade Level` is the granularity that gets short-changed.** Reading
   only its one sourced goal (`App Target`, from the cover-sheet grid) and
   calling the granularity done skips `New Student Target` and
   `Re-Enroll Projection`, which are derived and therefore cannot drift against
   the workbook — only against prod's own school rows. Check all three.

1. **Also reconcile prod against ITSELF at region grain.** A sheet-vs-prod diff
   cannot see a region row that was never recomputed after its school rows
   changed, because both sides read the same stale value. Compare each
   `Region/Grade Level` row against the `SUM` of prod's own `School/Grade Level`
   rows for that `(region, grade_level, goal_name)`:

   ```sql
   with sg as (
     select region, grade_level, goal_name, sum(goal_value) as sum_rounded
     from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__finalsite__goals`
     where enrollment_academic_year = <year>
       and goal_granularity = 'School/Grade Level'
     group by 1, 2, 3
   ),
   rg as (
     select region, grade_level, goal_name, goal_value as region_value
     from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__finalsite__goals`
     where enrollment_academic_year = <year>
       and goal_granularity = 'Region/Grade Level'
   )
   select * from rg full join sg using (region, grade_level, goal_name)
   where region_value is distinct from sum_rounded
   ```

   Triage the output — most of it is expected, and treating all of it as drift
   manufactures a false alarm:
   - **`abs(delta) = 1` is the documented `round(SUM)` vs `SUM(round)`
     artifact**, not drift. AY2026 threw six such rows (Camden g5, Newark g1,
     Newark g3 — each as a `New Student Target` / `Re-Enroll Projection` pair).
     Ignore them.
   - **Region `0` against NULL school rows** is benign — HS upper grades recruit
     nobody (AY2026: Newark g11/g12, Camden g12 `New Student Target`).
   - **`abs(delta) > 1` is real** and needs attribution to a cell before you
     report it.

1. **When every discrepancy is a contradiction INSIDE SRE's workbook, there is
   no paste-ready block — say that outright.** Prod can be simultaneously
   correct-as-loaded and wrong, and the fix is SRE's answer, not a value push.
   Do not invent a paste block by picking the side you find more convincing, and
   do not report "clean" either; report the contradictions as questions and say
   the block follows their answer.
1. **Only six `goal_name`s are SRE-entered numeric targets** — `Seat Target`,
   `FDOS Target`, `New Student Target`, `Budget Target`, `Re-Enroll Projection`
   (all `goal_type` `Enrollment`) and `App Target` (`Applications`). Those are
   the cover sheet's columns. Everything else is a funnel roll-up; don't hunt
   for it in SRE's workbook.
1. **Cross-check the cover sheet against the per-region tab before reporting a
   diff.** They disagree in real cases. When the two conflict, do NOT pick one:
   flag it as a question for SRE (see _Handing SRE a question_ below).

1. **When they disagree, re-read the cover-sheet cell as a FORMULA** —
   `valueRenderOption="FORMULA"` — because that is what tells you which KIND of
   problem you have. On the cover sheet, cols `D`, `E`, `G`, `H` and `I` are
   formulas pointing into the region tabs for essentially every school, while
   **col `F` (`Budget Target`) is hand-typed for all of them**. So a literal in
   `F` is ordinary authoring and needs no explanation, whereas **a lone literal
   in an otherwise-formula column is the signature of a manual overwrite** — and
   from here it is indistinguishable from an accidental paste over the formula.

   **That is where it stops. Do not escalate a hand-typed override and do not
   push a value from it.** SRE customizes cells by hand and that is theirs to
   do, so a literal in a formula column EXPLAINS a diff rather than being a
   defect to chase — this is the standing call from the data team, not a
   judgement to re-make per cell. Say what you found, leave prod as loaded, and
   move on. It is also the exception to the "flag it as a question for SRE" rule
   in the step above: that rule is for two SOURCED numbers disagreeing, not for
   a cover-sheet cell someone deliberately typed.

   Verified 2026-09-09: cover sheet `H11` (Purpose `New Student Target`) is the
   only literal in col `H`, reading 69 against the `Newark` tab's `P51`
   (`=sum(P47:P50)`) of 73.97 → 74. Prod holds 74, and 74 was KEPT — the
   divergence from the cover sheet's 69 was accepted rather than reconciled, and
   no question went to SRE. Do not re-open it.

   Print only a literal-vs-formula CLASSIFICATION, never the formula strings: a
   grid of formula text trips `check-output.sh`'s high-entropy scan and the
   entire tool result comes back as `[redacted: secret material]`.

1. **Never encode an interpretation from this skill as a transformation in your
   extractor.** Read every column as its header says, diff, and explain the
   diffs afterwards. Remapping a column on the way in ("the skill says `F` is
   really seat here") applies the same edit to both sides of the comparison, so
   the discrepancy becomes unrepresentable and the reconciliation reports clean.
   This exact failure hid three missing Miami `Budget Target` values, and was
   then reported as a confirmation — "the NULLs are exactly the documented
   three" — because the documentation and the extractor were the same claim. A
   NULL that matches a note in this skill is still a finding until you have
   checked the source cell.
1. **Hand back a FULL rebuild of the `goals` tab, not just the changed rows.**
   Emit every row the tab should contain, as many as staging holds, as plain
   tab-delimited lines in a fenced code block, in the sheet's column order
   (`enrollment_academic_year`, `region`, `school_level`, `schoolid`, `school`,
   `grade_level`, `goal_granularity`, `goal_type`, `goal_name`, `goal_value`),
   so the analyst clicks `A2` and pastes once. Not a markdown table, which can't
   be pasted into Sheets.

   **Do not hand back only the rows that changed.** Applying a diff by hand
   means finding each row among thousands and editing a single cell, and every
   step of that is error-prone: the analyst has to trust a row number you
   computed, the tab's row order is not guaranteed stable between reads, and a
   mis-scrolled edit writes a goal onto the wrong school silently — no test
   downstream would catch it, because the value is perfectly valid where it
   landed. A full replace has one failure mode instead, a bad paste, and that
   one is visible immediately in the row count.

   Three constraints on the full-replace path:
   - **Row 1 is the header** (`skip_leading_rows: 1`). The paste starts at `A2`
     and must never overwrite, shift or sort row 1 — capturing it corrupts the
     external table's column mapping.
   - **The rebuild must be a superset of what is already there.** Build it by
     taking the current staging rows and applying only the value changes you
     attributed to a source cell — NEVER by re-deriving the tab from SRE's
     workbook. The workbook carries only the six SRE-entered targets, so a
     workbook-derived rebuild silently drops every funnel roll-up row
     (`Inquiries`, `Deferred`, `Waitlisted`, `Accepted`, and the
     `Pending Offers` / `Conversion` families), most of the tab.
   - **Diff your rebuild against the staging table before handing it over**, on
     row count and on the full key set (`enrollment_academic_year`, `region`,
     `schoolid`, `grade_level`, `goal_granularity`, `goal_type`, `goal_name`).
     Only `goal_value` may differ, and only in the cells you can name. Say in
     your message how many values moved.

   Still name each change in prose next to the block, with the source cell, so
   the analyst and SRE can see what moved without diffing the whole tab.

1. **Rebuild before re-comparing.** Sheet edits are not visible to the frozen
   tables (the entry file's rules). Rebuild into your dev schema, then query the
   `zz_<user>_kipptaf_google_sheets` copy:

   ```bash
   uv run dbt build --select stg_google_sheets__finalsite__goals \
     --project-dir src/dbt/kipptaf --target dev \
     --defer --favor-state --state target/prod
   ```

   Skipping this makes the loop never converge — you keep re-reporting the same
   diff against pre-edit values. Repeat until there are no discrepancies.

Suggest the user drive this with `/loop` (no interval — self-paced) so each
round re-compares automatically after they finish a batch of edits. Stop the
loop when a comparison comes back clean, and say so explicitly rather than going
quiet.

**Mid-year goal updates** can optionally be applied through the Claude Chrome
extension instead of hand-pasting: generate a change-set prompt naming the
workbook, the tab, each target row keyed by
`(enrollment_academic_year, region, schoolid, grade_level, goal_type, goal_name)`,
old value → new value, and an explicit instruction to change nothing else. The
user drops that into the extension, which edits the sheet. **Then re-run the
comparison** — the extension's write is unverified from here, so the
reconciliation query is what confirms it landed.

The change-set prompt MUST carry these three guardrails. Each blocks a specific
silent failure, so don't trim them for brevity:

- **"Change `goal_value` only; do not add or create rows."** A new row needs
  `school_level`, `school` and `goal_granularity` filled correctly, and
  `goal_granularity` is what decides which CTE in
  `rpt_tableau__fresh_dashboard_progress_to_goals` picks the row up — a guessed
  value produces a goal that silently never joins. Adds go back to the user as a
  paste block instead. Tell the extension to report unmatched keys, not create
  them.
- **"Do not add, delete, reorder or sort rows."** The source sets
  `skip_leading_rows: 1`, so row 1 is the header; a sort that captures it
  corrupts the external table's column mapping.
- **"Do not rename anything in `goal_name` or `goal_type`."** They are join keys
  — a rename stops matching rather than erroring.

## Handing SRE a question

When the workbook contradicts itself or a value is ambiguous, SRE gets a
plain-language question, not the reconciliation output. No `goal_name` /
`goal_granularity` / `grade_level = -9` vocabulary, no schoolids — name the
school, name the two candidate numbers, name which tab each came from, and say
what you need back. Keep it to one or two questions; batch them into a single
message the user can forward as-is.

## Goals-sheet gap rows

When the scaffold gains a school or grade, it can have enrollment with no goal
to compare against. Check first; this is an ad hoc query, so substitute the
year:

```sql
select s.region, s.school, s.grade_level
from `teamster-332318.kipptaf_tableau.int_tableau__fresh_enrollment_scaffold` s
left join `teamster-332318.kipptaf_google_sheets.stg_google_sheets__finalsite__goals` g
  on s.schoolid = g.schoolid
  and s.grade_level = g.grade_level
  and g.enrollment_academic_year = <year>
  and g.goal_name = 'Seat Target'
where s.enrollment_academic_year = <year>
  and s.schoolid != 0
  and g.schoolid is null
order by 1, 2, 3
```

Exclude `schoolid = 0` (the region rollup rows) or every one of them reads as a
gap. Rows returned are school × grade combinations the dashboard will show
enrollment for with no goal.

For each gap, project the most recent existing year's combination set forward
and list every
`(enrollment_academic_year, region, schoolid, school, grade_level, goal_granularity, goal_type, goal_name)`
missing from the current year. The doc's _Which goals exist at which
granularity_ says which combinations live at which level. A genuinely new school
or grade has no prior-year pattern: flag it for the analyst to choose goal types
rather than skipping it.

- **`School` rows** (`grade_level = -9`), keyed by `schoolid`: copy that
  school's own `(goal_type, goal_name)` set forward. The set is uniform across
  almost every school; Miami Tech lacks the lottery categories (`Accepted`,
  `Offers`, `Pending Offers`), and a per-school copy handles that without
  special-casing (see [sre-workbook.md](sre-workbook.md), _Miami Tech is a
  matriculation school_).
- **`School/Grade Level` rows**, keyed by `(schoolid, grade_level)`: the same
  rule per grade.
- **`Region/Grade Level` rows** (Inquiries, Applications, Deferred, Waitlisted
  and so on), keyed by `(region, grade_level)`: one row per grade per region,
  not one region-wide row.

Hand the rows back under the sheet handoff contract in the entry file, then
rebuild the goals models and confirm the rows reached the table (row count and a
value sample, plus `__TABLES__.last_modified_time`) before saying it's done.
