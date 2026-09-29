## Procedure: A student's score is missing from the dashboard

Almost always an unresolved `localstudentidentifier`.

1. **Confirm the score reached the warehouse.** Query
   `int_pearson__all_assessments` for the student, by `statestudentidentifier`
   rather than by local id — the local id is the thing under suspicion.
2. **Check whether the detector already flags it.** Run
   `test_incorrect_student_number_pearson`. Its failure rows carry
   `studenttestuuid`, both identifiers, the name and the test code. Whether
   `localstudentidentifier` is null is what tells you the mode; the test code
   tells you the assessment.
3. **Read which failure mode it is** — they need different fixes:

   | Symptom                                  | Mode              | Fix                 |
   | ---------------------------------------- | ----------------- | ------------------- |
   | `localstudentidentifier` null            | absent            | crosswalk sheet row |
   | `localstudentidentifier` present, wrong  | present-but-wrong | crosswalk sheet row |
   | no enrollment for that year and district | unmatchable       | **not the sheet**   |

   **Classify by mode, not by vendor.** Either vendor can produce either mode.
   Today's failures happen to split cleanly -- Pearson wrong, Cambium absent --
   but the Cambium reading is one administration's worth of data and is not a
   property of the vendor. See the reference doc.

   The absent mode is recoverable from `statestudentidentifier` and there is a
   standing recommendation to automate it. The present-but-wrong mode never is,
   so the sheet is permanent either way.

   **A wrong identifier that is itself a valid `student_number` will not show up
   here at all.** The join succeeds against the wrong student and the detector
   stays silent. If someone reports a score attached to the wrong kid, that is
   this, and no test will find it for you.

   **Before writing any row, confirm the student has an enrollment in the test's
   own academic year and district.** The sheet only overrides the identifier;
   the join still needs year and district to match an enrollment with
   `rn_year = 1`. If there is no such enrollment, a sheet row changes nothing
   and becomes permanent dead weight. This is the unmatchable category and it is
   an Ops question, not a sheet one -- see the reference doc. Check the academic
   year before spending time on it: the dashboard publishes a rolling window, so
   a flagged row old enough to fall outside it is not worth chasing.

   ```sql
   select academic_year, _dbt_source_project, student_number
   from `teamster-332318`.kipptaf_powerschool.base_powerschool__student_enrollments
   where student_number = <candidate> and rn_year = 1
   order by academic_year
   ```

   A name that resolves only when you search across other years or districts is
   the signature of this category, not a lead.

4. **Add the sheet row.** Sheet `1BubU91_j6jrmi6DC0A9QilwPQy0gZZMkvmQ6bifkKsM`,
   named range `src_pearson__student_crosswalk`. Two columns:

   | Column              | Value                              |
   | ------------------- | ---------------------------------- |
   | `Student_Test_UUID` | from the failure row, verbatim     |
   | `Student_Number`    | the correct network student_number |

   The sheet is named for Pearson but serves every NJ vendor. **Cambium
   corrections go in this same tab** -- `int_pearson__all_assessments` aliases
   Cambium's `student_test_uuid` to `studenttestuuid` before the join, so it
   reaches them with no code change. One row per test, not per student: a
   student with four bad test rows needs four rows here.

5. **Re-check by reading the sheet external live** through ADC
   (`.claude/context/claude_ai_Google_Cloud_BigQuery.md`):

   ```python
   client.query('''
     select count(*) as crosswalk_rows
     from `teamster-332318`.kipptaf_google_sheets.src_google_sheets__pearson__student_crosswalk
   ''')
   ```

   Confirm the row count rose by what you added, then re-run the detector once
   the models rebuild. Not from the prod `stg_` table (see _Gotchas_).

**Do not quote the student's name in a PR, issue, or Slack.** Quote the UUID.

---

## Procedure: Generate crosswalk rows for every flagged test

Use this instead of resolving rows one at a time when the detector has a batch
outstanding. The logic lives in
[`src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql`](../../../src/dbt/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql);
this is the runbook. It is modelled on `collegeboard-id-crosswalk`, which solves
the same problem for AP.

**PII.** Output carries names, dates of birth and student numbers. Terminal and
local scratch only -- never a PR, issue, commit or any file under version
control. Write results to a file and report only counts.

### What the rules require

Three criteria, in the order they bind:

1. **Enrollment gate, hard, every tier.** The candidate must have an enrollment
   row for the test's own `academic_year` and `_dbt_source_project` with
   `rn_year = 1`. Without it the sheet cannot help at all -- see the unmatchable
   category above.
2. **Grade corroboration.** Codes ending `03`-`08` encode the grade, so
   enrollment `grade_level` must equal it: a **hard gate**, mismatch routes to
   `flagged_for_review`. HS codes (`ALG01`, `ALG02`, `GEO01`, `ELA09`, `ELA10`,
   `ELAGP`, `MATGP`, `SCI11`) do not encode grade -- students sit Algebra I in
   grade 8 or 9 and the pathway tests in 11 -- so there it is **informational
   only and never gates**.
3. **Identity**: state id, first name, last name, date of birth.

| tier | identity evidence                               | note                                 |
| ---- | ----------------------------------------------- | ------------------------------------ |
| A    | state id + first + last + DOB                   | strongest                            |
| B    | state id + first + last, no usable DOB          | weakest auto-resolving tier          |
| C    | DOB + first + last, state id does **not** match | catches a wrong state id             |
| D    | DOB + last, first differs                       | nicknames; never auto-resolved alone |

**DOB is not available everywhere, and that is not a vendor property.**
`stg_pearson__njsla` / `_njsla_science` / `_parcc` carry `birthdate` only
because they `select * except (...)`, so it rides through unnamed.
`stg_cambium__njgpa` and `stg_pearson__njgpa` use explicit column lists that
omit it, though the raw files have it. Cambium therefore runs on Tier B. Adding
`birth_date` to the cambium package staging model would lift it to Tier A; that
is a package column add and needs the cross-project staging dance.

### Steps

1. **Count first.** Run the detector and report how many rows are outstanding,
   split by mode. Ask before running the match.
2. **Compile and run:**

   ```bash
   uv run dbt compile --project-dir src/dbt/kipptaf --target prod \
     --select "path:analyses/state_assessment_tiered_crosswalk_match.sql"
   ```

   Then execute the compiled SQL. Write the result to a local CSV rather than
   printing it -- 36-character UUIDs also trip the output scanner, so a printed
   result often comes back redacted anyway.

3. **Report the bucket split** -- `resolved`, `flagged_for_review`, `ambiguous`,
   `no_match` -- and the tier distribution. Ask before handing over rows.
4. **Deliver `resolved` in batches of 20**, as a plain two-column delimited
   block inside a fenced code block, `Student_Test_UUID` then `Student_Number`,
   so it pastes into two sheet columns without markdown pipes riding along. Wait
   after each batch. Never dump every batch at once.
5. **Present `flagged_for_review` separately**, as a table for individual
   decisions -- never in a paste block. These are grade-gate failures and
   Tier-D-only matches.
6. **Present `no_match` separately** and say which kind: no enrollment that year
   (unmatchable, not a sheet problem) versus enrolled but no tier satisfied.
7. **Present `ambiguous` separately**, as a table, never in a paste block. These
   rows carry **no** `proposed_student_number` on purpose — more than one
   student satisfied a tier, and the query withholds the candidate rather than
   emitting an arbitrary one. A person picks among the candidates or decides
   none of them fit. Never guess, and never default to the first.
8. **Audit after the paste.** See below.

### Procedure: Audit the crosswalk against the rules

Replays every existing sheet row through the tiers using its raw pre-repair
identifier and compares the rules' pick to what a human entered. Run it after
any batch of entries, and periodically.

Outcomes: `agrees`, `ambiguous`, `no_pick_identity`, `no_pick_not_enrolled`, and
`DISAGREES`.

**A disagreement is serious** -- it means a sheet row points at a different
student than the evidence supports. Investigate before assuming the rules are
wrong; the sheet has no test protecting it.

The 2026-09-17 baseline was 81 rows: 66 agree, 2 ambiguous, 7
`no_pick_identity`, 6 `no_pick_not_enrolled`, **0 disagreements**. The reference
doc carries the interpretation. Compare against that baseline rather than
treating any non-agreeing row as new.

Resist adding a tier to absorb `no_pick_identity` rows. A new tier is justified
only by a deterministic, generalizable pattern, the same bar the AP protocol
sets for its no-match bucket -- otherwise the rules drift toward rubber-stamping
whatever is already in the sheet, which destroys their value as an independent
check.

---
