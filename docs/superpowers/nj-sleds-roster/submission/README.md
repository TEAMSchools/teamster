# NJ SLEDS Student Course Roster — grade and credit backfill

Fills `AlphaGradeEarned` and `CreditsEarned` on the loaded Student Course Roster
extract and writes a submission-ready CSV per region. Every other column passes
through byte-identical to the native PowerSchool extract.

This is a named exception to the runbook's source-fix-only cleaning model — see
the design spec for the rationale and its four narrowing constraints.

## Cycle

Run these three steps each time a fresh extract arrives.

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

## Files

| File                     | Responsibility                                       |
| ------------------------ | ---------------------------------------------------- |
| `submission_query.py`    | The SQL, the 25-column order, the legal grade domain |
| `validate_submission.py` | The pre-upload gate; `--self-test` proves it fires   |
| `build_submission.py`    | Creates the view, gates, exports per-region CSV      |

## PII

The exported CSVs carry names, dates of birth, and state IDs. Write them to
`.claude/scratch/` (gitignored), hand them only to the state-access uploader,
and never commit them or paste row-level values anywhere external.

## Known blocker outside this scope

The CDS defect is still live: 20,652 of 43,493 rows carry a bad County or School
code, including every Camden row. The fix is the one-pass School Setup change on
3 Newark and 5 Camden schools. A clean grade backfill does not make the file
submittable on its own.
