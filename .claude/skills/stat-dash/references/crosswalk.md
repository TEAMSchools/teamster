# The student crosswalk sheet

## Procedure: A student's score is missing from the dashboard

Almost always an unresolved `student_number`. Background: doc
[_Repairing a student number_](../../../../docs/models/stat-dashboard-data-model.md#repairing-a-student-number).

1. Confirm the score reached the warehouse. Query
   `int_assessments__state_nj_scores` for the student by `state_student_id`, not
   by `student_number`; the local id is the thing under suspicion. A Cambium
   attempt with `test_status` other than `completed` is filtered out upstream of
   this model and of the detector, so it never shows here and no crosswalk row
   can bring it back (see [after-a-load.md](after-a-load.md)). No row at all, by
   state id, means the file never loaded: check the Cambium or Pearson asset's
   latest materialization in Dagster before anything in this procedure.
2. Check whether the detector flags it. Run
   `test_incorrect_student_number_pearson`. Its failure rows carry
   `student_test_uuid`, both identifiers, the name, the year and the test code.
   Whether `student_number` is null tells you the mode.
3. Read which failure mode it is; they need different fixes:

   | Symptom                                  | Mode              | Fix                 |
   | ---------------------------------------- | ----------------- | ------------------- |
   | `student_number` null                    | absent            | crosswalk sheet row |
   | `student_number` present, wrong          | present-but-wrong | crosswalk sheet row |
   | no enrollment for that year and district | unmatchable       | not the sheet       |

   Classify by mode, not by vendor. Either vendor can produce any mode. As of
   2026-09-29 the outstanding Pearson rows are all unmatchable and the Cambium
   ones absent, but the Cambium reading rests on one administration's file
   (clean where populated in Spring 2026), which says nothing about the next.

   The absent mode is recoverable through the tiered match below, never through
   a state-id fallback in the model (doc _Decisions_). The present-but-wrong
   mode has no derivable rule, so the sheet stays either way.

   A wrong identifier that is itself a valid `student_number` does not show up
   here. The join succeeds against the wrong student and the detector stays
   silent. A report of a score on the wrong student is this, and no test will
   find it.

   Before writing any row, confirm the student has an enrollment in the test's
   own academic year and district. The sheet only overrides the identifier; the
   join still needs year and district to match an enrollment with `rn_year = 1`.
   Without one, a sheet row changes nothing and never expires: the unmatchable
   case, an Ops question. Check the year first: the dashboard publishes a
   rolling window (the current year and the seven before it), so an older
   flagged row is not worth chasing.

   ```sql
   select academic_year, _dbt_source_project, student_number
   from `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments
   where student_number = <candidate> and rn_year = 1
   order by academic_year
   ```

   This is the table the detector and the matcher use. The dashboard instead
   joins `int_extracts__student_enrollments` on
   `pearson_local_student_identifier` with `rn_year = 1` and `grade_level > 2`,
   so a row can pass the detector and still drop from the dashboard. When a
   repaired row still does not appear, check it there.

   A name that resolves only in another year or district is the signature of the
   unmatchable case, not a lead. The unmatchable rows outstanding on 2026-09-29
   are all AY2017-18, outside the window, each matching one student by name in
   some other year or district. The candidate explanations: the test is filed to
   the wrong district; the 2017-18 enrollment record is missing from PARCC-era
   history (the concentration in the oldest years points here); or the name
   match is a different person. None of them is a sheet fix.

4. Add the sheet row. Sheet `1BubU91_j6jrmi6DC0A9QilwPQy0gZZMkvmQ6bifkKsM`,
   named range `src_pearson__student_crosswalk`. Two columns:

   | Column              | Value                              |
   | ------------------- | ---------------------------------- |
   | `Student_Test_UUID` | from the failure row, verbatim     |
   | `Student_Number`    | the correct network student_number |

   The sheet is named for Pearson but serves every NJ vendor. Cambium
   corrections go in this same tab: `int_assessments__state_nj_scores` joins the
   sheet on `student_test_uuid` after the vendor union. One row per test, not
   per student. `Student_Test_UUID` carries `unique` and `not_null` tests at
   `severity: error`, so a duplicated UUID fails the build. Renaming the sheet
   off the Pearson name is a separate change; do not start it here.

5. Re-check by reading the sheet external live through ADC
   (`.claude/context/claude_ai_Google_Cloud_BigQuery.md`):

   ```python
   client.query('''
     select count(*) as crosswalk_rows
     from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__pearson__student_crosswalk
   ''')
   ```

   Confirm the row count rose by what you added, then re-run the detector once
   the models rebuild. Not from the prod `stg_` table.

Do not quote the student's name in a PR, issue, or Slack. Quote the UUID.

---

## Procedure: Generate crosswalk rows for every flagged test

Use this instead of resolving rows one at a time when the detector has a batch
outstanding. The logic lives in
[`src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql`](../../../../src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql);
this is the runbook. It is modelled on `collegeboard-id-crosswalk`, which solves
the same problem for College Board.

PII. Output carries names, dates of birth and student numbers. Terminal and
local scratch only, never a PR, issue, commit or any file under version control.
Write results to a file and report only counts.

### What the rules require

Three criteria, in the order they bind:

1. Enrollment gate, hard, every tier. The candidate must have a
   `base_powerschool__student_enrollments` row for the test's own
   `academic_year` and `_dbt_source_project` with `rn_year = 1`.
2. Grade corroboration. Codes ending `03`-`08` encode the grade, so enrollment
   `grade_level` must equal it: a hard gate, mismatch routes to
   `flagged_for_review`. HS codes (`ALG01`, `ALG02`, `GEO01`, `ELA09`, `ELA10`,
   `ELAGP`, `MATGP`, `SCI11`) do not encode grade, so there it is informational
   only.
3. Identity: state id, first name, last name, date of birth. Names are compared
   as letters only, accents and case folded, on both sides, so a hyphen,
   apostrophe or inner space in one system's spelling does not defeat a tier.

| tier | identity evidence                           | note                                 |
| ---- | ------------------------------------------- | ------------------------------------ |
| A    | state id + first + last + DOB               | strongest                            |
| B    | state id + first + last, no usable DOB      | weakest auto-resolving tier          |
| C    | DOB + first + last, state id does not match | catches a wrong state id             |
| D    | DOB + last, first differs                   | nicknames; never auto-resolved alone |

Tier B rests on the state id, which collides across students
([#3954](https://github.com/TEAMSchools/teamster/issues/3954)); what makes it
safe is the name agreement, not the state id alone. The first Cambium repairs
were accepted on exactly that evidence: a state id resolving 1:1 to an
enrollment plus both names.

DOB is not available everywhere, and that is not a vendor property. The matcher
reads it only from `stg_pearson__njsla`, `_njsla_science` and `_parcc`, which
carry `birthdate` because they `select * except (...)`. `stg_pearson__njgpa` and
all three Cambium staging models (`stg_cambium__njsla`, `__eoc`, `__njgpa`) use
explicit column lists that omit it, though the raw files have it, so every
Cambium row runs on Tier B. Adding `birth_date` to the cambium package staging
models would lift them to Tier A; that is a package column add and needs the
cross-project staging dance.

### Steps

1. Count first. Run the detector and report how many rows are outstanding, split
   by mode. Ask before running the match.
2. Compile and run:

   ```bash
   uv run dbt compile --project-dir src/dbt/kipptaf --target prod \
     --select "path:analyses/state_assessment_tiered_crosswalk_match.sql"
   ```

   Then execute the compiled SQL. Write the result to a local CSV rather than
   printing it; 36-character UUIDs also trip the output scanner, so a printed
   result often comes back redacted anyway.

3. Report the bucket split (`resolved`, `flagged_for_review`, `ambiguous`,
   `no_match`) and the tier distribution. Ask before handing over rows.
4. Deliver `resolved` in batches of 20, as a plain two-column delimited block
   inside a fenced code block, `Student_Test_UUID` then `Student_Number`, so it
   pastes into two sheet columns without markdown pipes riding along. Wait after
   each batch. Never dump every batch at once.
5. Present `flagged_for_review` separately, as a table for individual decisions,
   never in a paste block. These are grade-gate failures and Tier-D-only
   matches.
6. Present `no_match` separately and say which kind: no enrollment that year
   (unmatchable, not a sheet problem) versus enrolled but no tier satisfied.
7. Present `ambiguous` separately, as a table, never in a paste block. These
   rows carry no `proposed_student_number` on purpose: more than one student
   satisfied a tier, and the query withholds the candidate rather than emit an
   arbitrary one. A person picks among the candidates or decides none fit. Never
   guess, and never default to the first.
8. Audit after the paste. See below.

### Procedure: Audit the crosswalk against the rules

Replays every existing sheet row through the tiers using its raw pre-repair
identifier and compares the rules' pick to what a human entered. Run it after
any batch of entries, and periodically. Write per-row detail to a local file;
report counts only.

Outcomes: `agrees`, `ambiguous`, `no_pick_identity`, `no_pick_not_enrolled`, and
`DISAGREES`.

A disagreement is serious: a sheet row points at a different student than the
evidence supports. Investigate before assuming the rules are wrong.

Run it with [../scripts/audit_crosswalk.py](../scripts/audit_crosswalk.py) on
the compiled analysis; it prints counts only. Baseline 2026-09-29, after the
name normalization: 365 sheet rows, 329 agree, 0 disagree, the rest ambiguous,
flagged for review or with no pick. The sheet grows, so compare disagreements
and the shape of the non-agreeing rows, not totals. The doc's _Crosswalk sheet_
section carries the interpretation: leave non-reproducing rows alone and look at
the date of birth first. Take `ambiguous` counts only from runs made after the
analysis gained its `ambiguous` bucket; older runs dropped those rows and
undercount.

Resist adding a tier to absorb `no_pick_identity` rows. A new tier is justified
only by a deterministic, generalizable pattern, the same bar the College Board
protocol sets for its no-match bucket. Otherwise the rules drift toward
rubber-stamping whatever is already in the sheet, which destroys their value as
an independent check.
