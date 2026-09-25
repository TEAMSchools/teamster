# NJ SLEDS Student Course Roster — grade and credit backfill

Fills `AlphaGradeEarned` and `CreditsEarned` on the loaded Student Course Roster
extract and writes a submission-ready CSV per region. Every other column passes
through byte-identical to the native PowerSchool extract.

This is a named exception to the runbook's source-fix-only cleaning model — see
the design spec for the rationale and its four narrowing constraints.

## Cycle

`cd` into this directory first. Every script imports its sibling modules by bare
name (`from submission_query import ...`), so none of them resolve correctly run
from anywhere else:

```bash
cd docs/superpowers/nj-sleds-roster/submission
```

Then run these three steps each time a fresh extract arrives.

1. Reload the extract base tables into `cokafor` (existing reload script).
1. Run the validation gate:

   ```bash
   uv run --with google-cloud-bigquery python validate_submission.py
   ```

1. Create the view and export:

   ```bash
   uv run --with google-cloud-bigquery python build_submission.py OUTDIR
   ```

`build_submission.py` runs the gate itself and refuses to export on any failure,
so step 2 is only for iterating.

## The gate is red on arrival — this is expected

As of the 2026-07-29 extract, two check groups fail and are expected to keep
failing until someone acts on the source data:

- `check_in_scope_rows_have_grades` reports **108** in-scope rows with no letter
  grade (Newark HS 20, Newark MS 55, Camden HS 30, Camden MS 3).
- `check_credits_earned` reports **`missing = 50`** — HS rows with no
  `CreditsEarned`.

Both describe the same underlying gap: for these rows, PowerSchool holds no
usable `Y1` stored grade and no usable live final grade either, so this tool has
nothing to fill in from. It is not a query bug, and there is no flag or override
that makes it go away — the gate has no bypass, on purpose.

**Required action:** someone with PowerSchool access must post the missing
grades for those students and sections, or exclude the affected sections from
the extract pull, then re-pull and reload the extract. Re-run the gate after the
reload. If the residue drops to zero, `build_submission.py` will export; until
then, seeing `FAILED` here is the tool working as designed, not a defect to
chase.

## Ungraded worklist

The validation gate reports counts, not rows — useful for knowing the submission
is blocked, useless for actually clearing the block. `export_worklist.py` fills
that gap: it exports one row per in-scope, ungraded student/section so someone
with PowerSchool access can resolve them directly.

Run it any time, regardless of the gate's state:

```bash
uv run --with google-cloud-bigquery python export_worklist.py OUTDIR
```

This creates `cokafor.rpt_student_course_ungraded` and writes
`NJ_Student_Course_Ungraded_{region}.csv`. Unlike `build_submission.py`, it is
**not gated** — see its module docstring for why gating the fix-it tool on the
thing it exists to fix would be circular.

Each row carries `reason` (why the row has no grade) and `section_shape`
(whether the whole section is affected or just this student). As of the
2026-07-29 extract the 108 rows break down like this:

| Reason                                       | Section shape                    | Rows |
| -------------------------------------------- | -------------------------------- | ---: |
| no grade in either source                    | whole section ungraded           |   41 |
| no grade in either source                    | partial — classmates were graded |   34 |
| conflicting grades                           | partial                          |   31 |
| grade exists but outside the handbook domain | partial                          |    2 |

What each combination implies:

- **Whole section ungraded (41 rows):** the section appears never to have been
  graded. If it genuinely should not be reported, the fix is PowerSchool's
  "Exclude from Course Roster Reports" checkbox on the section's Course
  Submission Information panel (see the audit runbook). Then re-pull and re-load
  the extract.
- **Partial, classmates were graded (34 rows):** the section was graded and
  these individual students were missed. Excluding the section would wrongly
  drop the students who do have grades — post the missing grades instead.
- **Conflicting grades (31 rows):** a grade exists, but sources or reporting
  terms disagree, so the query refuses to pick one. Reconcile in PowerSchool.
  These are the cheapest to clear.
- **Grade exists but outside the handbook domain (2 rows):** the only available
  grade was `F*`, a warehouse-internal marker that is not a legal
  `AlphaGradeEarned` value. Determine the real grade and correct it in
  PowerSchool.

The worklist CSV is PII-bearing (local student and section IDs) — same handling
as the submission CSV: write it to `.claude/scratch/` (gitignored), never commit
it, never paste row-level values anywhere external.

After fixing a source record, the extract must be re-pulled and re-loaded before
the gate reflects the fix — re-running the gate against the old extract will
still show the same failures.

## Re-baselining per cycle

Two constants in `validate_submission.py` are per-cycle baselines, not derivable
truths, and must be re-measured by hand whenever a new extract is loaded:

- `BASELINE_BAND_ROWS` — the `(region, grade_band)` row counts. Band composition
  legitimately shifts between extract pulls, and the band logic is exactly what
  this baseline cross-checks, so deriving it from the query itself would be
  circular.
- `BASELINE_STORED_COVERAGE` — the `(region, grade_band)` floor of rows with a
  matched stored `Y1` grade. It is a floor, not an equality, but still needs
  re-measuring so a real regression doesn't hide under a stale floor.

To re-baseline: after reloading the extract, run the same `group by` queries the
two check functions run against the new data
(`select region, grade_band, count(*) ... group by region, grade_band` for the
band counts; the `countif(stored_letter is not null)` variant for stored
coverage), replace the literal dict values with the new counts, and update the
"measured from" date comment above each constant.

## Files

| File                     | Responsibility                                       |
| ------------------------ | ---------------------------------------------------- |
| `submission_query.py`    | The SQL, the 25-column order, the legal grade domain |
| `validate_submission.py` | The pre-upload gate; `--self-test` proves it fires   |
| `build_submission.py`    | Creates the view, gates, exports per-region CSV      |
| `export_worklist.py`     | Ungraded worklist, not gated — see above             |

## PII

The exported submission CSVs carry names, dates of birth, and state IDs. The
worklist CSVs carry local student and section IDs only, still PII. Write both
kinds to `.claude/scratch/` (gitignored), hand the submission CSVs only to the
state-access uploader, and never commit either or paste row-level values
anywhere external.

## Unverified: CSV encoding, quoting, and line endings

The export writes UTF-8 **without** a byte-order mark and with LF line endings —
the defaults of `csv.writer` and `Path.open` on this platform. The existing
reload scripts read the native PowerSchool extract files with `utf-8-sig`, which
only makes sense if the native files carry a UTF-8 BOM. That implies the
export's encoding may already differ from what NJSLEDS's own extract produces,
and neither the BOM question nor CRLF-vs-LF has been confirmed against what the
state's upload portal actually accepts.

**This must be confirmed before the first real upload.** Compare a native
extract file's encoding and line endings (for example `file` and a hex dump of
its first few bytes) against one of these exported CSVs, and adjust the writer
if they don't match.

## Known blocker outside this scope

The CDS defect is still live: 20,652 of 43,493 rows carry a bad County or School
code, including every Camden row. The fix is the one-pass School Setup change on
3 Newark and 5 Camden schools. A clean grade backfill does not make the file
submittable on its own.
