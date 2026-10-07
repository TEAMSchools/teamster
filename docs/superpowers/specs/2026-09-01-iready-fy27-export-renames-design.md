# i-Ready FY27 export renames — design

Restores FY2027 i-Ready ingestion in all regions after Curriculum Associates
renamed the SFTP exports for the 2026-2027 school year.

Anchored to [#4949](https://github.com/TEAMSchools/teamster/issues/4949).

This supersedes
`docs/superpowers/specs/2026-08-21-iready-2027-export-renames-design.md` (PR
#4951). That document reached the same conclusion on the central partition
question by a different route, but several of its supporting facts are wrong —
see _Corrections to the prior spec_ below. Inherit the decision, not the
document.

## Context

Curriculum Associates renamed the i-Ready SFTP exports for FY2027. None of our
asset regexes match the new filenames, so FY27 ingestion is partially or fully
stopped in every region.

All observations below were taken live on **2026-09-01** against the i-Ready
SFTP and the Dagster+ prod deployment. Where this document states a fact, it was
checked, not carried forward.

## What changed at the vendor

### The subject token `ela` became `reading`

| Previous                                            | New                                                     |
| --------------------------------------------------- | ------------------------------------------------------- |
| `personalized_instruction_summary_ela_CONFIDENTIAL` | `personalized_instruction_summary_reading_CONFIDENTIAL` |
| `iready_instruction_by_lesson_ela_CONFIDENTIAL`     | `iready_instruction_by_lesson_reading_CONFIDENTIAL`     |
| `iready_pro_instruction_by_lesson_ela_CONFIDENTIAL` | `iready_pro_instruction_by_lesson_reading_CONFIDENTIAL` |

### Diagnostic Results became i-Ready Inform Results

| Previous                               | New                                                   |
| -------------------------------------- | ----------------------------------------------------- |
| `diagnostic_results_ela_CONFIDENTIAL`  | `i-ready_inform_results_reading_english_CONFIDENTIAL` |
| `diagnostic_results_math_CONFIDENTIAL` | `i-ready_inform_results_math_CONFIDENTIAL`            |

Two naming irregularities matter to the design: the prefix is `i-ready`
(hyphenated, unlike every other export), and the reading subject token is
`reading_english`, not `reading`.

**Inform is the same dataset, verified by header diff rather than assumed:**

| Pair                                                            | Old cols | New cols | Shared | Same order |
| --------------------------------------------------------------- | -------- | -------- | ------ | ---------- |
| `diagnostic_results_math` → `i-ready_inform_results_math`       | 50       | 51       | 47     | yes        |
| `diagnostic_results_ela` → `..._inform_results_reading_english` | 60       | 61       | 57     | yes        |

Identical in both regions. The entire delta is 3 renamed columns and 1 new one:

```text
Baseline Diagnostic (Y/N)        -> Baseline Assessment (Y/N)
Most Recent Diagnostic YTD (Y/N) -> Most Recent Assessment YTD (Y/N)
Diagnostic Gain                  -> Assessment Gain
                                 +  Tactile Graphics   (new)
```

## Production impact

FY27 files land daily at ~07:20 UTC (Miami) and ~07:26 UTC (NJ). We match none
of them.

| Asset                                                 | State on 2026-09-01                                                 |
| ----------------------------------------------------- | ------------------------------------------------------------------- |
| `kippmiami/iready/diagnostic_results`                 | Last materialized 2026-07-18. FY27 partition holds 3,933 FY26 rows. |
| `kippnewark/iready/diagnostic_results`                | Last materialized 2026-07-18, same minute.                          |
| `kippmiami/iready/personalized_instruction_summary`   | `math` daily; no `ela` since 2026-07-18.                            |
| `kippmiami/iready/personalized_instruction_by_lesson` | `math` daily; no reading.                                           |

Miami is 6 weeks into its school year with no FY27 reading instruction data and
no FY27 assessment data at all.

The FY27 `diagnostic_results` partition is the sharper problem: it materialized
once from a stale FY26 file and, with the export renamed, has no path to
self-correct. Anything reading `_dagster_partition_academic_year=2026` is
serving last year's assessment data as this year's.

## SFTP facts the design depends on

Verified by listing `/exports` and its subfolders on 2026-09-01.

- **Archive folders contain only old-prefix files.** `2024/` and `2025/` hold
  `diagnostic_results_{ela,math}_CONFIDENTIAL.csv` and
  `personalized_instruction_summary_{ela,math}_CONFIDENTIAL.csv` in both
  regions. No `i-ready_inform_results` file exists in any archive folder.
- **`2023/` is empty (0 files) in both regions.** Partitions for FY2024 and
  earlier hold GCS data from prior ingests but can never be re-fetched.
- **The stale `Current_Year` files are not duplicates of the archive.** The
  `2025/` copies were written 2026-06-30 and are smaller; the `Current_Year`
  copies ran on to 2026-07-18. Deleting the `Current_Year` copies is safe for
  our pipeline — we ingested the 07-18 version — but it is not a no-op.
- **The vendor will not produce another `_ela_` file.** The July 2026 leftovers
  are the last ones.
- **No `reading_spanish` file exists in any region.**

## Design

### Decision 1: the subject partition stays `["ela", "math"]`

The partition value remains `ela` for reading, in every fiscal year. The
vendor's rename is absorbed by translating the partition subject to a filename
token at the SFTP boundary.

This is forced, not preferred. The GCS object path is derived from the partition
key by the IO manager, and `MultiPartitionsDefinition` is a cartesian product of
two static lists — one asset cannot use `ela` for old years and `reading` for
new ones. Given that, every alternative fails a stated requirement:

| Alternative                             | Why it was rejected                                                                                                                                |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Partition becomes `reading` everywhere  | Re-materializing an archive year writes FY24 data to a `_dagster_partition_subject=reading` path.                                                  |
| Add `reading` as a 3rd subject value    | Every future year gains an `ela` partition that can never materialize, growing annually.                                                           |
| Two assets per dataset, split at FY2027 | Does not help the 3 Personalized Instruction datasets, whose filename prefix never changed. Costs 4 extra assets, 4 external sources and 4 unions. |

Consequences worth stating plainly: the partition key no longer names the file
it came from, and the translation must be applied in opposite directions in the
asset and the sensor. Both are accepted.

### Decision 2: the era is keyed on the partition year, not the folder

`build_sftp_file_asset` already branches on whether a partition is the newest
fiscal year, in order to map it to the vendor's `Current_Year` folder. That test
is the wrong one for filenames. Next July, FY27 rolls into a `2026/` archive
carrying the **new** names, so an era test based on "is this the current year"
would then translate FY27 back to `ela` and break.

The filename era is a fixed boundary — partition key `2026` (FY2027), the first
year the vendor used new names — and is independent of the folder branch.

| Partition year | Folder                        | Filename token for `ela` |
| -------------- | ----------------------------- | ------------------------ |
| `< 2026`       | `2020/` … `2025/`             | `ela`                    |
| `>= 2026`      | `Current_Year`, later `2026/` | `reading`                |

### Decision 3: dbt translates the raw token, and nothing else

`stg_iready__diagnostic_results` already emits `subject` as `Reading`/`Math`, so
the ~40 downstream models that join on `iready_subject` need no change and the
vendor's rename is, semantically, already absorbed. The only place `ela` still
surfaces is the raw `_dagster_partition_subject` column, which staging
translates to `reading`.

Two columns are deliberately left alone:

- **`discipline` stays `ELA`.** It is shared cross-assessment vocabulary used by
  FAST, the college assessments and `int_assessments__scaffold`. Changing it for
  i-Ready alone would make i-Ready the only source reporting a different value.
- **`grad_unpivot_subject` stays `ela`.** It is a graduation-requirements token
  that happens to spell the same; renaming it breaks joins to PowerSchool rather
  than relabeling i-Ready.

The translation must land in the final select, after the 22 growth-measure
comparisons, or those comparisons stop matching. That leaves a column named
`_dagster_partition_subject` whose value no longer equals the GCS partition it
names. **Open question for code review:** confirm with analysts that this is
acceptable, or keep the raw column honest and add a separately-named translated
column instead. This is a naming call, not a design change.

## Implementation

### Dagster

New module `src/teamster/libraries/iready/subjects.py`:

```python
RENAME_ACADEMIC_YEAR = 2026  # partition key of FY2027, first year of new export names
REMOTE_SUBJECT_TOKENS = {"ela": "reading"}  # partition subject -> current-era filename token


def is_legacy_year(academic_year: str) -> bool:
    return academic_year != "Current_Year" and int(academic_year) < RENAME_ACADEMIC_YEAR
```

`build_iready_sftp_asset` gains a `legacy_remote_file_regex` parameter. Its
value for each asset is **exactly the regex in the repo today**, which makes the
diff self-evidently correct:

| Asset                                | `legacy_remote_file_regex`                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------------ |
| `personalized_instruction_summary`   | `personalized_instruction_summary_(?P<subject>ela\|math)_CONFIDENTIAL\.csv`                |
| `personalized_instruction_by_lesson` | `(personalized\|iready)_instruction_by_lesson_(?P<subject>ela\|math)(_CONFIDENTIAL)?\.csv` |
| `instruction_by_lesson` (pro)        | `iready_pro_instruction_by_lesson_(?P<subject>ela\|math)_CONFIDENTIAL\.csv`                |
| `diagnostic_results`                 | `diagnostic_results_(?P<subject>ela\|math)(_CONFIDENTIAL)?\.csv`                           |

The current-era regexes become:

```text
personalized_instruction_summary_(?P<subject>ela|math|reading)_CONFIDENTIAL\.csv
(personalized|iready)_instruction_by_lesson_(?P<subject>ela|math|reading)(_CONFIDENTIAL)?\.csv
iready_pro_instruction_by_lesson_(?P<subject>ela|math|reading)_CONFIDENTIAL\.csv
i-ready_inform_results_(?P<subject>ela|math|reading)(_english)?_CONFIDENTIAL\.csv
```

The `reading` alternative exists for the **sensor**, which matches uncomposed.
The **asset** never sees it: `regex_pattern_replace` substitutes the whole named
group with the translated token.

Note that `(_english)?` sits outside the named group. Composing `ela` for the
assessment asset yields
`i-ready_inform_results_reading(_english)?_CONFIDENTIAL\.csv`, which matches the
live reading file; composing `math` yields a pattern matching only the Inform
math file.

In the existing `if group_name == "iready"` block of
`src/teamster/libraries/sftp/assets.py`: when
`is_legacy_year(academic_year_key)`, compose `legacy_remote_file_regex` with the
partition subject unchanged. Otherwise compose the current regex with the
subject mapped through `REMOTE_SUBJECT_TOKENS`.

In `src/teamster/libraries/iready/sensors.py`: after a path matches, map the
captured remote token back to the partition subject (`reading` becomes `ela`)
before building the `MultiPartitionKey`.

In `src/teamster/libraries/iready/schema.py`, add 4 fields to
`DiagnosticResults`: `assessment_gain`, `baseline_assessment_y_n`,
`most_recent_assessment_ytd_y_n`, `tactile_graphics`. Derive the exact slugified
names from the ingest slugifier rather than guessing them. The model is already
a superset carrying both `most_recent_diagnostic_y_n` and
`most_recent_diagnostic_ytd_y_n` from a prior vendor rename, so this follows
established precedent.

### dbt

All changes are in `src/dbt/iready/`. Verified blast radius: nothing outside
that directory reads i-Ready's `_dagster_partition_subject` — the only other
references belong to RenLearn.

In `src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql`:

1. Coalesce the 3 renamed columns, old name first so history wins:
   `coalesce(diagnostic_gain, assessment_gain) as diagnostic_gain`, and the same
   for the two `Y/N` columns.
1. Add `tactile_graphics`.
1. Translate `_dagster_partition_subject` from `ela` to `reading` in the final
   select.

In
`src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml`,
add `tactile_graphics` to the enforced contract.

No union, no new external source, no subject normalization, and the 22
growth-measure comparisons are untouched. The subject `CASE` is deliberately
**not** hoisted into a CTE — with the token pinned it buys nothing.

## Self-healing and cleanup

**No multiple-match risk anywhere.** In `Current_Year`, the composed pattern for
`2026|ela` names the `i-ready_inform_results` prefix, which the stale
`diagnostic_results_*` files cannot match. `ignore_multiple_matches` is not
needed on any asset.

**The polluted FY27 partition self-heals.** The stale `_ela_` file and the live
`_reading_` file both map to partition `2026|ela`, and the sensor groups run
requests by `(job_name, partition_key)`, so they collapse into one run that
fetches the Inform file and overwrites the 3,933 stale rows. No dbt guard and no
GCS deletion are required.

Two manual, optional follow-ups:

- Mark historical partitions materialized in Dagster, rather than backfilling.
  History stays physically at `_dagster_partition_subject=ela`, which is where
  the translation leaves it.
- Ask Curriculum Associates to archive and remove the stale `Current_Year`
  files. This is cleanup only — nothing in the design depends on it, which is
  deliberate, because the vendor's July rollover lag recurs annually.

## Risks

- **A future vendor bulk-rename of archive folders would break the era gate.**
  `is_legacy_year` keys on the partition's academic year, not on which token the
  file on disk carries. If Curriculum Associates ever renamed `2020/`–`2025/`
  files to the `reading` token — the way they already did for
  `Current_Year`/FY2027 — `partition_subject("reading", "2025")` would still
  return `reading`, naming a partition that does not exist. This fails loudly,
  which is correct, but the design depends on archive folders staying on the old
  names forever; it has no self-healing path if the vendor renames them
  retroactively.

## Verification

1. `uv run dbt build --select stg_iready__diagnostic_results+`.
1. On a branch deployment, materialize one FY27 partition and one archive
   partition per asset per region. Confirm the archive run fetches an `_ela_`
   file and the FY27 run fetches a `_reading_` one.
1. Confirm the FY27 `diagnostic_results` partition row count moves off 3,933 and
   carries a current completion date.

## Out of scope

Each gets its own issue.

- **`standards_results` ingestion.** Never ingested. Per-grade files (`_2`
  through `_8`) with grade- and state-specific columns and embedded newlines in
  quoted header cells; needs a third partition dimension and a long-not-wide
  shape. Verified to have no urgency: the files exist only in Miami, and the
  FY27 `_reading_` copies are byte-for-byte the same sizes as the July `_ela_`
  copies across all 7 grades, so they are renamed July files, not live data.
- **`instructional_usage_data` retirement.** No Dagster asset, staging disabled
  in both district projects, snapshot disabled, no consumer, SFTP files frozen
  since 2025-07-21.
- **Missing NJ `iready_pro_instruction_by_lesson_math`.** No such file exists in
  `nj-kipp_nj`, and `kippnewark/iready/instruction_by_lesson` has only ever
  materialized `ela`. This is a vendor configuration gap, not rename fallout,
  and will now surface as a permanently missing `2026|math` partition.

## Corrections to the prior spec

Recorded so the errors are not inherited. Each was checked against the live SFTP
or the current code on 2026-09-01.

- **The 4th field rename does not exist.** The prior spec and #4949 both claim
  `Diagnostic Language` became `Assessment Language` on the math export. Neither
  column appears in either file, in either region. Do not build an alias for it.
- **Miami retains archives back to 2020**, not "only `2024/`, `2025/` and
  `Current_Year`". `2023/` and earlier are present but empty.
- **The multiple-match argument overlooked `ignore_multiple_matches`.** The
  prior spec ruled out a merged asset on the grounds that
  `build_sftp_file_asset` raises on multiple matches, without noting the flag
  that disables it or that matches are already sorted newest-first. The merged
  asset was rejected here for different and better reasons.
- **`standards_results` is Miami-only and carries no live FY27 data**, which the
  prior spec did not establish before scoping it into the same change.

## Open questions

1. Whether translating `_dagster_partition_subject` to `reading` is acceptable
   to analysts, or whether the raw column should stay honest with a separate
   translated column alongside it. To be settled in code review.
1. Whether Paterson history matters. `/exports/nj-paterson` was last written
   2026-08-04 and is scheduled to fold into the NJ export; its FY26 and prior
   data will not backfill retroactively.
