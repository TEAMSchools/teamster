# Goals — sources, values, and changing a goal

## Goals — sources, authoritative values, and traps

KIPP Forward owns the goals. Two source documents drive the SY26-27 rewrite:

| Document                                  | Id                                             | Owner                          |
| ----------------------------------------- | ---------------------------------------------- | ------------------------------ |
| `SY26-27 SAT Strategy` (Google Doc)       | `1FKXrTW5TY_7ORnQOvIOp4XWuUgKAi04pi0vqj2emNWs` | `kkenny@apps.teamschools.org`  |
| `SAT_GPA Goals Updated July 2026` (Sheet) | `1Mgfaxnte2M1N4_sfxhjeCe4oVpwBoaTTcSMfKXrkEuI` | `mmarrer@apps.teamschools.org` |

Neither will be shared with the ADC service account, so tab names and cell
addresses are unavailable — see `.claude/context/claude_ai_Google_Drive.md`.
**Ask which tab, or ask for a paste.** Do not report a cross-tab discrepancy
from a Drive MCP read; you cannot attribute content to a tab.

**The goals sheet contains a deprecated tab named `DO NOT USE THESE`** holding a
two-column `Class of / 1010+ SAT goal` table reading 23 / 28 / 33 percent. Those
are dead. Reading the workbook flat makes them look authoritative.

### Authoritative topline goals

Percent of students hitting the benchmark **by end of junior year**, by
graduating class. Confirmed identical in the strategy doc and the sheet's main
nine-column table:

| Class of | College Ready (1010+) | HS Grad Bar (890+) |
| -------- | --------------------- | ------------------ |
| 2027     | 22%                   | 45%                |
| 2028     | 28%                   | 55%                |
| 2029     | 34%                   | 60%                |
| 2030     | 40%                   | 70%                |
| 2031     | 47%                   | 80%                |

### Thresholds

Fourteen of the fifteen values hardcoded in
`rpt_tableau__college_assessment_dashboard_benchmark_calcs` match the strategy
doc. Two decisions have been taken:

- **`EA/ED-Ready` is retired.** The three hardcoded entries — PSAT 8/9 and
  PSAT10/NMSQT at 1100, SAT at 1200 — come out. SAT 1200 exists nowhere else, so
  check for downstream filters on that `benchmark_group` before deleting.
- **PSAT 8/9 HS Grad-Ready is 790, not the hardcoded 800.** Fixed on the
  scaffold rather than in code, so the number becomes data. Shipped — the model
  reads 790.

The rebuilt sheet also corrected an **inverted PSAT 8/9 percentage pair**. The
retired sheet had HS Grad-Ready at 0.34 against a threshold of 800 and
College-Ready at 0.60 against 860 — a harder bar with a higher expected share.
It now reads 0.50 and 0.30. PSAT10 and NMSQT were never inverted, so do not go
looking for the same fault there.

Subject thresholds used to be split across two systems — the College-Ready tier
(EBRW 480, Math 530) in `_benchmark_calcs`, the grad-bar tier (EBRW 450,
Math 440) in the goals sheet as `Board` metrics. **That is resolved: both tiers
live on the scaffold and `Board` is retired.** Every board threshold turned out
to be a scaffold value already — SAT combined 890 and 1010 are its HS Grad-Ready
and College-Ready cut scores, EBRW 450 and Math 440 its grad bars — so `Board`
was a duplicate encoding.

`_current` reports the two tiers as `benchmark_tier`, a three-way band of
College-Ready, HS Grad-Ready, or No Benchmark Met, replacing four wide
`met_min_board_*` flags. The board goal percentages do **not** survive: they
were distinct (0.25 and 0.28 for the 890 tier against the Benchmark goals' 0.45
and 0.35) because that view reports over test takers, but goals are now uniform,
so the NJ Grad Ready line takes the sheet's HS Grad-Ready value.

### The rebuilt goals tab — what shipped

The sheet was rebuilt on named range `src_google_sheets__kippfwd_goals_v3`,
**eleven** columns spanning A:K:

```text
academic_year, test_type, grade_level, cohort, score_type,
pct_1_attempt, pct_2_plus_attempts, pct_hs_grad_ready, pct_college_ready,
pct_hs_grad_ready_over_time, pct_college_ready_over_time
```

Staging unpivots all six percentage columns to long, so a metric is a row rather
than a column. Ten sheet rows become 54 — 34 per-grade rows (UNPIVOT drops
nulls, and every PSAT row is blank for `pct_2_plus_attempts`) plus 20 over-time
rows.

**The two `_over_time` columns exist because `_over_time` reports on neither
grade level nor cohort**, and the per-grade goals disagree for SAT. Staging
strips the suffix and sets `is_over_time_goal`, so both framings land under the
same four `expected_metric_type` values. Consequence: **a consumer reading this
staging model must filter `is_over_time_goal` or it sees both.**

Widening the range is the step that is easy to miss. Adding the columns to the
tab is not enough — the named range was A:I, and because the source declares
`columns:` explicitly with `skip_leading_rows: 1`, mapping is **positional**.
Out- of-range columns therefore read all-null rather than erroring, header
spelling is irrelevant, and the only symptom is that no row has
`is_over_time_goal` true. A column add also needs `stage_external_sources` with
`ext_full_refresh: true`; a value edit does not.

**The over-time values are provisional — they hold the dashboard steady, they
are not authoritative goals.** Each is set to what the report already displays:

| Score type                         | HS Grad-Ready | College-Ready | vs prod                     |
| ---------------------------------- | ------------- | ------------- | --------------------------- |
| `sat_total_score`                  | 0.35          | 0.17          | matches (Tableau's `MIN()`) |
| `psat10_total` / `psatnmsqt_total` | 0.55          | 0.28          | matches                     |
| `psat89_total`                     | 0.60          | 0.30          | prod's values, un-inverted  |

They are deliberately **not** the topline per-cohort goals above — class of 2027
is 45% / 22%, class of 2028 is 55% / 28%. KIPP Forward has not stated a
cohort-independent goal yet, so the placeholder is the status quo rather than a
guess. **Do not "correct" these to a topline value, and do not report them as a
discrepancy against the strategy doc.** Ask KIPP Forward what the over-time goal
should be.

Three things this resolved, all previously listed here as unmodellable:

- **School year** is now `academic_year`, a real column.
- **Thresholds left the goals sheet entirely.** They live on the scaffold as
  `a1_attempt_min_score`, `a2_plus_attempts_min_score`,
  `hs_grad_ready_min_score`, `college_ready_min_score`. `min_score` no longer
  means an attempt count on one row and a scale score on the next.
- **Region and school differentiators are gone**, not null — KIPP Forward
  stopped setting goals that way, so the free-text per-school cell has no
  successor.

`int_google_sheets__kippfwd__goals_unpivot` joins goals to scaffold and is what
consumers should read. Goal horizon (interim versus terminal for one cohort) is
still unmodelled; every current row is AY2026.

Declare `grade_level` and `cohort` as STRING in the source. The scaffold's
`expected_grade_level` holds comma-separated lists, and INT64 would foreclose
the same on the goals side while needing a sheet-coordinated external rebuild to
undo.

### Practice is first-class in the strategy

The strategy's third pillar commissions this work directly — track progress
"across baseline, practice and actual exams" with "group and individual" growth,
"overall and subject-specific". The testing calendar gives every grade a
`Date 1 (Practice)` and a `Date 2 (official)`. Grade 11 has **two** official
dates, so official administrations need round identity too, not just practice.

### Counting attempts — use the hub, never `count(*)`

`int_assessments__all_college_assessments` carries `attempt_lifetime` and
`yearly_attempts_totals`. Both count **distinct `test_date`**, on total rows
only, partitioned by `test_type`. Read those rather than counting rows anywhere.

`count(*)` is wrong on this data: 261 official sittings hold the same score
twice under different `rn_highest` values, so a row count credits one sitting as
two attempts. `dense_rank` on `test_date` is what makes the fix work — duplicate
dates share a rank, so the max of the rank is the distinct-date count.
`row_number` would not.

Section rows read null on both fields by design. An attempt is counted once per
sitting, not once per section sat.

`int_students__college_assessment_participation_roster` reads these rather than
deriving counts. Its grain now includes `test_type`, so **filter `test_type` as
well as `rn_lifetime = 1`** — a student with practice data returns one row of
each.

### Hunting duplicates in kippadb — key on subject

If you check `stg_kippadb__standardized_test` for duplicate records, the key
must be contact, date, test type **and subject**. Without subject, 1,548
students who legitimately sit several AP exams on one day read as 2,289
duplicates, and a delete list built from that would destroy real records.

Fingerprint every non-identity column, not just the score fields, before calling
a pair redundant — two records can share a score and differ on
`administration_round` or `scoring_irregularity`.

Verified real duplicates as of 2026-08: 87 ACT/SAT records (86 of them Camden
class of 2027 on the April 2026 school-day SAT) and 478 PSAT records from 2024.
One 2015 SAT pair has genuinely different scores and is not a duplicate.

### Where the new goals tab belongs

Put it in the **existing** kippfwd workbook,
`12yqEOmyeNrvzOkmrOFnKOpsHU0L19G7zoG3b9f5cIpI`, which already backs
`Scale Score Conversion`, `Scaffold`, and `Goals`. It is already readable by the
BigLake connection that Sheets external tables use, so no new access has to be
arranged — a different identity again from both the Drive MCP and ADC.

Pin `sheet_range:` to the exact tab name. That is what makes a dbt source immune
to a neighbouring `DO NOT USE THESE` tab. Note the shared-trigger cost: every
Sheets source on one URI re-triggers together, so editing the goals tab also
refreshes the conversion and scaffold tabs.

## Procedure: Change a goal value

For a new target from the Foundation or KIPP Forward: a percentage on the Goals
tab (`src_google_sheets__kippfwd_goals_v3`, A:K). No model hardcodes a goal, so
this is a sheet edit only. Follow _Handing sheet rows to the user_ in
[SKILL.md](../SKILL.md).

1. Read _The rebuilt goals tab — what shipped_ above. It says which cells are
   blank on purpose and which values (the `_over_time` columns) are provisional.
   Leave those alone unless the request names them.
2. Map the request to cells. A cell already at the new value needs nothing; say
   so. A blank cell stays blank unless the request explicitly adds a goal there
   — every PSAT `pct_2_plus_attempts` is blank because PSAT is given once, and
   UNPIVOT turns a filled blank into a new goal row.
3. Generate the whole tab with the edits applied:

   ```bash
   uv run python .claude/skills/carat-dashboard/scripts/dump_goals_tab.py \
       <scratchpad>/goals_tab.tsv \
       --set test_type=Official,score_type=sat_total_score pct_2_plus_attempts=0.95
   ```

   A class's goal is on the tab only while that class is in a grade the tab
   lists for this year; the topline per-class table is a strategy target, not
   tab rows. Read the dumped tab first and find the row. If the request names a
   class with no row this year, say so rather than inventing one. Key `--set` on
   the columns that name the goal: `test_type`, `score_type`, and `cohort` or
   `grade_level` for a per-class goal (they pair one-to-one within a year). It
   prints every cell it changed, old to new, and aborts when nothing matches.
   Check that list against the request before handing over the file.

4. Hand the user the file path and "paste over A1 of the Goals tab".
5. After the paste, rerun the script with no `--set` to a second file and diff
   the two. A value edit needs no `stage_external_sources`.
6. No manual rebuild is needed. The Google Sheets sensor
   (`build_google_sheets_asset_sensor`) polls the workbook's Drive
   `modifiedTime`, and an edit triggers
   `kipptaf/google_sheets/stg_google_sheets__kippfwd__goals` — about an hour
   after the paste on 2026-09-24. Tableau shows the value after its next extract
   refresh. Confirm with `mcp__dagster__get_asset_materializations` (a timestamp
   newer than the paste) and a query of the staging model. A long gap between
   materializations means nobody edited the sheet, not that edits are ignored.
7. Update every place that quotes a changed value, on a branch: _Authoritative
   topline goals_ above for a per-class HS Grad-Ready or College-Ready goal, and
   _Goals_ in the reference doc (its topline table and attempts paragraph).
