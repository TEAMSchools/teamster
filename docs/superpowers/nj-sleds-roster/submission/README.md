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

## PII

The exported CSVs carry names, dates of birth, and state IDs. Write them to
`.claude/scratch/` (gitignored), hand them only to the state-access uploader,
and never commit them or paste row-level values anywhere external.

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
