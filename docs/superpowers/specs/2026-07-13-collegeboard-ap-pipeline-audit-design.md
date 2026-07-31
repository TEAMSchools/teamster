# College Board AP Pipeline Audit — Design Spec

**Date:** 2026-07-13 **Issue:**
[#4390](https://github.com/TEAMSchools/teamster/issues/4390) **Status:**
Approved

## Problem

Four distinct gaps let this year's AP scores go missing or silently mislabeled
on `rpt_tableau__ap_assessment_dashboard` (the CARAT dashboard):

1. **Crosswalk ID gaps.** `stg_google_sheets__collegeboard__ap_id_crosswalk`
   maps College Board AP IDs (`College_Board_ID`) to PowerSchool student numbers
   (`PowerSchool_Student_Number`). New AP takers each year aren't in the sheet
   yet, so their scores can't resolve to a student. The dbt test
   `int_collegeboard__ap_unpivot__crosswalk_resolves` catches this
   (`kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`
   lists the unresolved `ap_number_ap_id` values), but resolving each one has
   been a manual, one-student-at-a-time BigQuery lookup (plug in first name,
   last name, and DOB, rerun, repeat) — 173 times for the 2025-2026 admin.
2. **Ingestion-side staleness.** Raw AP files dropped to the Couchdrop/Google
   Drive folder land in the partitioned `kipptaf/collegeboard/ap` asset, but
   `stg_collegeboard__ap`'s automation condition currently includes a
   `school_year = N+1` partition in its range (extending to
   `CURRENT_FISCAL_YEAR.fiscal_year + 1`), which is always unmaterialized — that
   trips the condition's `not (any_deps_missing)` gate and blocks
   `stg_collegeboard__ap` from auto-rebuilding after a new file lands. This will
   recur every year until the automation condition itself is fixed (tracked
   separately), so until then, someone has to notice new raw data sitting
   unpicked-up and manually trigger the materialization.
3. **Codes/course-crosswalk completeness.** Two Ops-maintained Google Sheets
   feed the whole pipeline: `stg_google_sheets__collegeboard__ap_codes` (CB
   exam/irregularity code → description) and
   `stg_google_sheets__collegeboard__ap_course_crosswalk` (CB test name →
   PowerSchool `ap_course_subject` code). A code that appears in a real (scored)
   raw file row but not in `ap_codes`, or a PowerSchool course clearly meant to
   be AP (by name) but never tagged with `ap_course_subject` in PowerSchool's
   course setup, breaks resolution silently — no error, the record just doesn't
   show up correctly.
4. **Downstream lineage risk.** Fixing the crosswalk sheet doesn't by itself
   prove the fix reaches the dashboard. `int_collegeboard__ap_unpivot` sits
   between the crosswalk and the dashboard, and (discovered during this design)
   its `dbt_utils.deduplicate(partition_by="powerschool_student_number", ...)`
   step has a real bug: when multiple different students are unresolved at once,
   they all share a `NULL` `powerschool_student_number`, and the dedup silently
   keeps only one arbitrary row across all of them — hiding the rest until the
   crosswalk resolves them. (Out of scope to fix here; flagged for a follow-up
   issue.) Nothing currently confirms a crosswalk fix actually flows through to
   `int_collegeboard__ap_unpivot` and the dashboard.

## Goals

- Detect when raw AP data has landed but `stg_collegeboard__ap` hasn't picked it
  up yet, and — with the user's explicit approval — trigger the materialization.
- Replace the one-at-a-time crosswalk lookup with a single bulk query that
  matches most gaps automatically.
- Catch codes and course-tagging gaps upstream, before they silently break
  resolution.
- After a crosswalk fix, verify it actually reaches
  `int_collegeboard__ap_unpivot` and the dashboard — not just the sheet.
- Surface results as chat tables (batched, easy to copy/paste in the VS Code
  terminal) — no scratch files.
- Package the workflow as a reusable skill so this doesn't require re-deriving
  the queries every year.

## Out of Scope

- Writing directly to the Google Sheet (no available tool can edit Sheet cells —
  Drive MCP only creates/reads files).
- Fuzzy/similarity name matching (edit distance, phonetic matching, etc.). Only
  deterministic transforms (case-fold, diacritic-strip, hyphen/space
  token-splitting, exact ±1-year day-count comparison) are used.
- Resolving a residual `no_match` case automatically — whatever's left after all
  tiers still needs a human to investigate. (For the validated 2025-2026
  backlog, that residual was zero — see below — but future years' causes may
  differ.)
- Detecting or flagging _why_ a given crosswalk gap exists (see below) on a
  per-row basis, and any Ops escalation or College Board account-merge workflow
  — the action taken (add a new `CB ID → student_number` row) is the same
  regardless of cause, so there's nothing to branch on.
- Fixing PowerSchool course setup (the AP-course-tagging check surfaces a gap; a
  human fixes it in PowerSchool — no write access here) or fixing the
  `int_collegeboard__ap_unpivot` dedup bug (tracked as a separate follow-up, not
  part of this skill).

## Why Crosswalk Gaps Happen

A `College_Board_ID` can be missing from the crosswalk sheet for two distinct
reasons:

1. **First-time tester** — the student has never taken an AP exam with a CB
   account before, so no ID existed to add previously.
2. **Duplicate CB account** — the student already has a crosswalk entry under a
   _different_ `College_Board_ID`, but somehow ended up with a second CB account
   (and therefore a second ID) for this admin. College Board's account-merge
   process is long and tedious enough that KTAF doesn't pursue it — the
   practical fix is just adding the new ID as another mapping to the same
   `student_number`.

Both cases resolve identically (add the row), so the skill doesn't need to
distinguish them to act — but the skill should say this explanation out loud
when it presents results, so the user understands what's happening and why,
rather than wondering if a "new" ID means something went wrong.

## Ingestion Refresh Design

Before touching the crosswalk at all, the skill checks whether
`stg_collegeboard__ap` actually reflects the latest raw drop:

1. Compare materialization timestamps: `get_asset_health` /
   `get_asset_materializations` on the raw `kipptaf/collegeboard/ap` partitions
   (per school × school_year) vs. the staging asset
   `kipptaf/collegeboard/stg_collegeboard__ap`.
2. If a raw partition materialized more recently than `stg_collegeboard__ap`'s
   last materialization, staging is stale — most likely blocked by the
   future-partition automation-condition gap described above.
3. **Always ask before launching anything.** Preview the run (`launch_run` with
   `confirm=False`) and explain to the user why it's needed (which partitions
   are newer, and that the automation condition is blocked by the unmaterialized
   future-year partitions) before firing it with `confirm=True`. Never trigger a
   production materialization without that explicit go-ahead, even though this
   is expected to recur annually.
4. After the run succeeds, re-check asset health to confirm
   `stg_collegeboard__ap` picked up the new data. `int_collegeboard__ap_unpivot`
   does not need a separate manual trigger — it rematerializes on its own via
   the automation condition once `stg_collegeboard__ap` succeeds (observed
   behavior from the 2025-2026 fix).
5. Only once staging is confirmed fresh does the skill move on to the codes
   completeness and crosswalk-gap matching below.

## Codes Completeness Check

Before trusting `ap_codes` / `ap_course_crosswalk` for anything downstream,
confirm every code the raw file actually uses (on a **scored** row — a record
with a real `exam_grade`) is present in
`stg_google_sheets__collegeboard__ap_codes`:

1. Unpivot `exam_code_01`-`exam_code_30` and
   `irregularity_code_{1,2}_01`-`irregularity_code_{1,2}_30` off
   `stg_collegeboard__ap`, filtered to rows where the paired `exam_grade` is not
   null.
2. Anti-join distinct exam codes against `ap_codes` where
   `` `domain` = 'Exam Codes' ``, and distinct irregularity codes against
   `` `domain` = 'Irregularity Scores' ``.

**Must scope to scored rows only.** Validated: exam codes `1`/`2` appear in the
raw file but only on rows with zero score (`exam_grade is null`) — empty
placeholder slots, not real codes. Including unscored rows produces false
positives on every run. Scoped correctly (2025-2026 validation): **0 gaps** —
every code that actually matters is already covered.

**When a gap is found, don't just report it — help fix it:**

1. **Identify** the missing code(s) and which domain each belongs to
   (`Exam Codes` vs. `Irregularity Scores`), as above.
2. **Look up the meaning.** College Board publishes an official "AP Student
   Datafile for Schools and Districts [Year] Layout Format" PDF at
   `apcentral.collegeboard.org` (e.g. `ap-datafile-layout-2026.pdf`), updated
   annually, documenting the exact code tables. Search for the layout doc
   matching the relevant admin year, then **fetch and read the actual PDF** —
   don't trust a search-result summary at face value. (Validated during design:
   a `WebSearch` summary for this returned a suspicious, repetitive-looking code
   list that doesn't match how sparse/varied real code tables look — the doc
   exists and is findable, but the skill must read the source itself, not relay
   an AI-search paraphrase, before telling the user what a code means.)
3. **Hand off, don't write.** Present the user the missing code(s), the
   looked-up description, and the direct URL to the `ap_codes` sheet tab
   (`https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE`,
   tab `src_collegeboard__ap_codes`) so they can add the row manually — same "no
   write access to Sheets" constraint as the crosswalk fix.

## AP Course Tagging Check

`ap_course_subject` (the field
`stg_google_sheets__collegeboard__ap_course_crosswalk` maps to) comes from
PowerSchool's NJ state course-extension table (`stg_powerschool__s_nj_crs_x`,
joined by `coursesdcid`) — a course-setup field a human sets directly in
PowerSchool, entirely independent of the crosswalk sheet. `is_ap_course` on
`base_powerschool__course_enrollments` is literally defined as
`ap_course_subject is not null`, so a course that already has the field set
can't fail this check by definition — the real gap is a course whose **name**
signals AP but was never tagged:

```sql
select distinct
  cc_academic_year,
  cc_course_number,
  courses_course_name,
  ap_course_subject
from `teamster-332318`.kipptaf_powerschool.base_powerschool__course_enrollments
where cc_academic_year >= 2024
  and regexp_contains(courses_course_name, r'\bAP\b')
  and ap_course_subject is null
order by cc_academic_year, courses_course_name
```

Scoped to `academic_year >= 2024` per user direction (older history isn't
actionable). Validated (2025-2026): **exactly 1 gap** — course number
`ENG22110C4` ("AP Seminar", academic_year 2025) has no `ap_course_subject` set.
This is a PowerSchool course-setup miss with no PII involved — surfaced to the
user to route to whoever owns PowerSchool course setup (not this skill's job to
fix; no PS write access here). **Flag unconditionally, not just when it affects
this cycle's matching** — a course still gets flagged even if the corresponding
exam type happens to already resolve fine through a different, correctly-tagged
course (as happened with the validated `ENG22110C4` case: a sibling "Seminar"
course elsewhere was already tagged and is what the Tier C/D course-enrollment
corroboration check matched against). The tagging gap is real regardless of
whether it happens to break anything this year.

## Matching Design

All matching is scoped per-gap to `academic_year = enrollment_school_year` (the
CB record's own year) against
`kipptaf_powerschool.base_powerschool__student_enrollments` — no manual year
parameter needed, so the same query works unchanged in future years.

1. **Tier A** — exact match on `date_of_birth` + `last_name` (case-folded).
2. **Tier B** — same DOB, but `last_name` compared with diacritics stripped on
   both sides via `REGEXP_REPLACE(NORMALIZE(x, NFD), r"\pM", "")` (handles CB's
   ASCII-only file format vs. accented PowerSchool names, e.g. `Peña` → `Pena`).
3. **Tier C** — same DOB, but `last_name` compared by token instead of whole
   string: split on hyphens/spaces on both sides (case-fold + diacritic-strip
   each token), match if any token is shared. Handles compound/hyphenated
   surnames recorded inconsistently between CB and PowerSchool — e.g. a CB
   single-word surname vs. a PS surname with a name-suffix (`Jr`, `II`, ...)
   appended, or a two-word surname where CB kept only one half and PS kept both
   (in either direction), or a hyphen on one side vs. a space on the other.
   Still a deterministic string transform, not similarity scoring.
4. **Tier D** — DOB exactly 365 or 366 days apart
   (`ABS(DATE_DIFF(...)) IN (365, 366)` — equivalent to "same month/day, year
   off by exactly one" accounting for leap years) **and** both `first_name` and
   `last_name` match exactly (post case-fold/diacritic-strip). Handles a
   DOB-year transcription mismatch between CB and PowerSchool. Requires both
   names to match (not just last name) since loosening the DOB itself raises
   collision risk more than Tier C does.
5. **Tiebreak** — when Tiers A-D together yield more than one distinct
   `student_number` for a gap, narrow further using `first_name` (same case-fold
   / diacritic-strip logic, plus stripping non-alphanumeric characters so an
   apostrophe in a name doesn't block the match either).

Each gap buckets into:

| Bucket               | Meaning                                                 | Validated count (2025-2026) |
| -------------------- | ------------------------------------------------------- | --------------------------- |
| `resolved`           | Tier A/B match, or Tier C/D match with gender agreement | 173                         |
| `flagged_for_review` | Tier C/D match but gender _disagrees_ — see below       | 0                           |
| `no_match`           | No PS candidate found at all                            | 0                           |

Query validated live against the full 173-gap backlog during design (see
conversation, PII redacted here per repo policy — real names/DOBs are not
committed to git). Tiers A/B alone resolved 157 directly + 3 via tiebreak (one
tiebreak pair was same-DOB/same-surname twins, correctly split by first name).
The remaining 13 all initially landed in `no_match`; reviewing each one by hand
surfaced two deterministic, generalizable causes (9 compound/hyphenated-surname
cases → Tier C, 3 DOB-year-off-by-one cases → Tier D, 1 case that turned out to
already be covered by Tier C once re-checked carefully). Adding Tiers C and D
resolved all 13, and — verified by comparing old vs. new `student_number` for
every gap that already had a clean Tier A/B match — introduced zero regressions.

This is not a guarantee that every future year's backlog reaches 0 `no_match` —
see "Continuous Improvement" below.

## Confidence Corroboration for Tier C/D

Tiers C and D loosen a matching field (partial surname / DOB year), which is a
strictly wider net than Tiers A/B. Rather than asserting these matches are
certain, the skill checks two independent signals — validated against all 13
Tier C/D matches from the 2025-2026 backlog:

1. **Gender agreement (hard gate).** Compare `gender` on `stg_collegeboard__ap`
   against `gender` on
   `kipptaf_powerschool.base_powerschool__student_enrollments` for the matched
   `student_number` + academic_year. Gender has no legitimate reason to differ
   between the two systems, so a mismatch moves that row from `resolved` to
   `flagged_for_review` instead of including it in the copy-paste batch. All 13
   Tier C/D matches agreed on gender in the 2025-2026 validation — 0 flagged.
2. **AP course enrollment (informational, not a gate).** For Tier C/D matches
   only, check whether the matched student was enrolled in the course
   corresponding to the exam, in
   `kipptaf_powerschool.base_powerschool__course_enrollments` for the same
   academic_year. This can't reuse `int_collegeboard__ap_unpivot` — that model
   only emits a row once the crosswalk already resolves the student, which is
   exactly what's being checked, so an unresolved candidate is invisible to it.
   Instead, unpivot `exam_code_01`-`exam_code_30` directly off
   `stg_collegeboard__ap` for just the candidate rows, resolve each to a
   `test_name` via `stg_google_sheets__collegeboard__ap_codes`
   (`domain = 'Exam Codes'`), then to one or more `ps_ap_course_subject_code`
   values via `stg_google_sheets__collegeboard__ap_course_crosswalk`
   (`data_source = 'CB File'`, comma-split). Ops manually tags this crosswalk's
   `ps_ap_course_subject_code` to match `base_powerschool__course_enrollments`
   `ap_course_subject` — **not** `cc_course_number` (a plain PS course code like
   `ENG01005C3`; comparing against that is always false). Match on
   `ap_course_subject`, filtered to `rn_course_number_year = 1` and
   `not is_dropped_section` (per `src/dbt/kipptaf/CLAUDE.md`'s guidance on this
   model's known duplicate-row issue). **ID-space + district-union note:**
   everything else in this skill matches to PowerSchool's human-facing
   `student_number` — `base_powerschool__course_enrollments` keys enrollments by
   `cc_studentid`, PowerSchool's internal numeric ID, bridged via
   `base_powerschool__student_enrollments.studentid` (same academic_year). Both
   tables are network-wide union models over district-level source tables, so
   `studentid` values aren't globally unique — the join also needs
   `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` matching on both sides
   (the `union_dataset_join_clause` macro's raw-SQL equivalent, since this runs
   outside dbt) or it can silently cross-match a student in one district to a
   course-enrollment row from another. Validated against all 13 Tier C/D
   matches: 100% had a matching course enrollment. Presence is corroborating
   evidence; absence is _not_ evidence against the match — testing without
   taking the class (and vice versa) is normal, since College Board doesn't
   require enrollment in the course to sit the exam. Surfaced as an annotation
   on the Tier C/D rows, not used to include/exclude anything.

Tier A/B rows skip both checks — the match is already tight enough that this
would just be noise.

## Continuous Improvement — No-Match Root Cause Review

Whatever remains in `no_match` after Tiers A-D is not a dead end. Before handing
that bucket to the user as "needs manual investigation," the skill should try to
characterize _why_ each one didn't match — the same process used during design
(with results discussed in chat, never written to a committed file, since it
necessarily involves real student names):

1. Loosen the DOB constraint (any academic_year, not just the gap's own year)
   and look for the same last_name/token — reveals students who exist in PS
   under a different year (e.g., withdrawn, or an enrollment-year mismatch).
2. Loosen the last_name constraint (same DOB, any last_name in the same year) —
   reveals a name that changed or was recorded very differently.
3. If a case reveals a new deterministic, generalizable pattern (not one-off
   noise), that's a signal to add another tier — the same way Tier C and D were
   derived from the 2025-2026 backlog. If it's genuinely one-off (e.g., the
   student really isn't in PowerSchool at all), it stays a manual case.

This step is diagnostic, not a promise to keep expanding tiers forever — the
goal is to keep the manual-review bucket small and to make future additions
evidence-based rather than speculative.

## Downstream Lineage Verification

Fixing the crosswalk sheet doesn't prove the fix reaches the dashboard — confirm
it does, once the post-paste reconciliation (below) shows the sheet itself is
correct:

1. **`int_collegeboard__ap_unpivot`** — compare row count for the target
   academic_year before vs. after. Validated (2025-2026): 398 → 658 rows after
   this session's fix. Caveat: this model's
   `dbt_utils.deduplicate(partition_by="powerschool_student_number", ...)` step
   silently drops all but one row when multiple students share a `NULL`
   `powerschool_student_number` (see Problem #4) — so a "before" count taken
   while gaps are still unresolved may itself be an undercount of how many
   scores were actually missing. Don't treat the before-count as ground truth;
   treat the after-count (once the crosswalk is fully resolved) as the number
   that matters.
2. **`rpt_tableau__ap_assessment_dashboard`** — confirm scored rows
   (`test_name is not null`) for the target academic_year increased. Validated:
   643 rows with scores after the fix. This view lives in `kipptaf_tableau` (not
   a generic "extracts" dataset — find the actual schema via
   `INFORMATION_SCHEMA.TABLES` if unsure, not by guessing).
3. **The Tableau workbook itself** — found via the exposure definition in
   `src/dbt/kipptaf/models/exposures/tableau.yml`
   (`college_admission_readiness_assessments_tracker_carat`, i.e. "CARAT", LSID
   `286156c4-2f9e-4983-926b-63c9b11f44f4`, Dagster-owned refresh
   `cron_schedule: 0 6 * * *`) — use the exposure file to find the workbook,
   don't guess at dataset/table names. Since
   `rpt_tableau__ap_assessment_dashboard` is a live BigQuery view (not a
   materialized extract), steps 1-2 already reflect what a live connection would
   show; if the workbook instead uses an extract, cross-check via the Tableau
   MCP (`get-workbook` / `list-datasources` with the LSID) against the
   `0 6 * * *` refresh cadence.

Present a short summary comparing counts at each stage (crosswalk sheet →
`int_collegeboard__ap_unpivot` → dashboard) so a break anywhere in the chain is
visible, not just "the sheet was updated."

## Output Format

No files. Results are delivered progressively in chat (see Workflow) so the user
doesn't lose track of where they are, in different shapes depending on purpose:

- **Codes completeness** and **AP course tagging** results: small plain-text or
  markdown summaries early in the run — no PII in either (codes and course names
  only).
- A one-line **pre-audit summary** (raw student count, exam-score count, gap
  count) before running the crosswalk match — plain text.
- A **tier breakdown** (counts per Tier A/B/C/D + tiebreak +
  `flagged_for_review` + residual `no_match`) after running the match, before
  showing any data — plain text.
- If a batch contains any Tier C/D rows, a small **markdown review table**
  immediately above the paste block for just those rows (tier tag,
  course-enrollment note) — for eyeballing, not pasting.
- `resolved`: one batch of 20 rows at a time as a **plain delimited block**
  (`College_Board_ID<tab>PowerSchool_Student_Number`, one pair per line, in a
  fenced code block) — not a markdown table, so it pastes cleanly into two Sheet
  columns without carrying pipe/dash formatting characters along. The skill
  waits for the user to confirm before showing the next batch.
- `flagged_for_review` (if any): rows where Tier C/D matched but gender
  disagreed — held out of the copy-paste batches entirely, shown as a markdown
  table (CB first/last/gender vs. PS first/last/gender) for the user to decide
  on individually, not a paste block.
- residual `no_match` (if any): a single markdown table with CB first/last name
  and DOB so the user can investigate — small enough (single digits to low teens
  historically) not to need batching.
- **Downstream lineage summary**: a small plain-text before/after count
  comparison across the three stages — aggregate counts only, no PII.

## PII Handling

Crosswalk-matching results include student names and DOB (indirect/direct
identifiers). Per repo policy this stays in chat/terminal only — never pasted
into a GitHub issue/PR/comment, Slack, or Asana. The skill's documentation must
repeat this constraint explicitly since it's meant to be picked up by future
sessions. The codes-completeness, AP-course-tagging, and downstream-lineage
checks carry no PII at all (codes, course names, aggregate counts) — no special
handling needed for those, though they stay in chat for consistency with the
rest of the skill's output.

## Workflow

1. **Ingestion check.** Check whether raw `kipptaf/collegeboard/ap` partitions
   materialized more recently than `stg_collegeboard__ap`. If so, explain why to
   the user and ask approval to launch a `stg_collegeboard__ap` run; only
   proceed once approved and the run succeeds.
2. **Codes completeness check.** Run once staging is fresh (expected to be
   rare/zero). For any gap found: identify the missing code + domain, look up
   its meaning by fetching the current College Board "AP Student Datafile ...
   Layout Format" PDF (don't trust a search-summary paraphrase — read the actual
   document), then hand the user the missing code, its looked-up description,
   and the direct URL to the `ap_codes` sheet tab so they can add it manually.
3. **AP course tagging check.** Independent of the crosswalk gaps; present any
   PowerSchool-side gaps found (`academic_year >= 2024`).
4. **Pre-audit summary.** Get cheap counts: total students in the raw file for
   the relevant admin (`stg_collegeboard__ap` row count for the year), total
   exam scores (`int_collegeboard__ap_unpivot` row count for the year), and the
   gap count (from
   `kipptaf_dbt_test__audit.int_collegeboard__ap_unpivot__crosswalk_resolves`).
   Present as: "The raw AP file has _N_ students resolving to _M_ exam scores.
   Of those, _G_ aren't in the crosswalk yet." Ask: "Ready for me to run the
   matching audit against PowerSchool?" Don't proceed until the user confirms.
5. **Run the tiered match** (Tiers A-D + tiebreak) against
   `kipptaf_powerschool.base_powerschool__student_enrollments` once approved.
6. **Corroborate Tier C/D matches.** For every Tier C/D match, check gender
   agreement (hard gate — mismatch moves the row to `flagged_for_review`) and AP
   course enrollment (informational annotation only) as described above.
7. **Tier breakdown.** Present counts per tier (how many resolved at Tier A, B,
   C, D, via tiebreak, how many `flagged_for_review`, and how many remain
   `no_match`). Ask: "Ready to start copy-pasting matches into the sheet?" Don't
   proceed until confirmed.
8. **Batch-by-batch delivery.** Present `resolved` one batch of 20 at a time
   (Tier C/D rows tagged with their tier and course-enrollment note). After each
   batch, ask "Ready for the next batch?" and wait for confirmation before
   showing the next one — never dump all batches in a single message. Present
   `flagged_for_review` separately, after the `resolved` batches, for the user
   to decide on individually.
9. User manually pastes each batch's rows into the Google Sheet as they go (or
   after the last batch — whichever the user prefers).
10. **Post-paste reconciliation.** Once the last batch has been delivered,
    monitor for the Google Sheet's sync to land: watch
    `stg_google_sheets__collegeboard__ap_id_crosswalk`'s row count (via Dagster
    asset health / BigQuery) until it increases by the number of resolved rows
    generated. Once it does, tell the user explicitly that a reconciliation
    check is about to run, then compare the generated `resolved` list against
    the actual new rows in that table to catch:
    - **missing rows** — a generated pair that never made it in (paste error,
      lost row)
    - **duplicate rows** — the same `College_Board_ID` appearing more than once,
      possibly mapped to different student numbers
    - **incorrect rows** — a `College_Board_ID` present but with a different
      `student_number` than generated (transcription/copy-paste error)
11. **Downstream lineage verification.** Once the sheet itself reconciles
    cleanly, follow the fix through `int_collegeboard__ap_unpivot` and
    `rpt_tableau__ap_assessment_dashboard` as described above, and present the
    before/after count summary.
12. User (or the agent, on request) re-runs the audit query to confirm the gap
    count dropped to the expected residual (0 for a fully-resolved run, or the
    remaining `no_match` count otherwise).
13. **No-match root-cause review** (if any remain) — see "Continuous
    Improvement" above.

## Skill Packaging

New skill: `.claude/skills/collegeboard-ap-data-ingest-protocol/SKILL.md`
(renamed from the original crosswalk-only scope to reflect the full pipeline
audit — ingestion freshness, crosswalk ID gaps, codes/course-tagging
completeness, and downstream lineage verification).

- **Triggers**: "resolve CB AP ID crosswalk gaps," "unmatched college board
  ids," "ap_id_crosswalk missing students," "new AP scores aren't showing up on
  the dashboard," "push the AP file to Dagster," "audit the AP codes/ course
  crosswalk," or any question about students or scores missing/ mislabeled on
  the AP score dashboard.
- **Contents**: the raw-vs-staging staleness check and approval-gated
  `stg_collegeboard__ap` run steps; the codes-completeness and AP-course-tagging
  checks; the pre-audit-summary and tier-breakdown confirmation gates; the Tier
  A-D + tiebreak SQL (parameter-free, self-scoping by year); the Tier C/D
  corroboration checks (gender hard-gate, course-enrollment annotation,
  including the `student_number` vs. `cc_studentid` ID-space + district-union
  note); the "why crosswalk gaps happen" explanation to surface alongside
  results; the one-batch-at-a-time chat-table delivery (batches of 20, confirm
  between each, plain delimited copy/paste format — not a markdown table — so
  rows paste cleanly into Sheet columns); the post-paste reconciliation check
  against `stg_google_sheets__collegeboard__ap_id_crosswalk`
  (missing/duplicate/incorrect rows); the downstream lineage verification steps
  (using the exposure YAML to find the Tableau workbook, not guessing dataset
  names); the no-match root-cause review process; and the PII-stays-local
  reminder (including: never write real student names/DOBs into a committed file
  — chat/terminal only).
