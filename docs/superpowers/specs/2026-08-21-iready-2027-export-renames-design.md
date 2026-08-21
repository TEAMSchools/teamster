# i-Ready 2026-2027 export renames — design

Refs #4949

## Context

Curriculum Associates renamed the i-Ready SFTP exports for the 2026-2027 school
year. None of our asset regexes match the new filenames, so FY27 i-Ready
ingestion is partially or fully stopped in every region.

Vendor source of truth:
`faq-what-changes-can-I-expect-with-iReady-exports-for-the-2026_2027-school-year`
(Curriculum Associates, 04/26, W3519034). A copy lives in
`.claude/scratch/i-Ready updates/`; extracted text is in
`.claude/scratch/iready_vendor_faq.txt`.

All SFTP observations below were taken on 2026-08-21 against both
`/exports/fl-kipp_miami` and `/exports/nj-kipp_nj`. Raw listings and header
diffs are in `.claude/scratch/iready_probe.json`,
`.claude/scratch/iready_miami_listing.txt`, and
`.claude/scratch/iready_years.json`.

## What changed

### Subject token: `ela` becomes `reading`

Headers are byte-identical to the old files (65, 31, and 34 columns
respectively), so this is a filename change only.

| Previous                                            | New                                                     |
| --------------------------------------------------- | ------------------------------------------------------- |
| `personalized_instruction_summary_ela_CONFIDENTIAL` | `personalized_instruction_summary_reading_CONFIDENTIAL` |
| `iready_instruction_by_lesson_ela_CONFIDENTIAL`     | `iready_instruction_by_lesson_reading_CONFIDENTIAL`     |
| `iready_pro_instruction_by_lesson_ela_CONFIDENTIAL` | `iready_pro_instruction_by_lesson_reading_CONFIDENTIAL` |
| `standards_results_by_test_ela_CONFIDENTIAL`        | `standards_results_by_test_reading_CONFIDENTIAL`        |
| `standards_results_ytd_ela_CONFIDENTIAL`            | `standards_results_ytd_reading_CONFIDENTIAL`            |

### Diagnostic Results becomes i-Ready Inform Results

i-Ready Inform is the vendor's new name for the assessment previously called
i-Ready Diagnostic. This is a rename of one continuous dataset, not a new
report.

| Previous                                          | New                                                   |
| ------------------------------------------------- | ----------------------------------------------------- |
| `diagnostic_results_ela_CONFIDENTIAL`             | `i-ready_inform_results_reading_english_CONFIDENTIAL` |
| `diagnostic_results_math_CONFIDENTIAL`            | `i-ready_inform_results_math_CONFIDENTIAL`            |
| `diagnostic_results_reading_spanish_CONFIDENTIAL` | `i-ready_inform_results_reading_spanish_CONFIDENTIAL` |

Two naming irregularities drive the design: the prefix is `i-ready` (hyphenated,
unlike every other export), and the reading subject token is `reading_english`,
not `reading`.

Field renames inside this export:

| Previous                           | New                                |
| ---------------------------------- | ---------------------------------- |
| `Baseline Diagnostic (Y/N)`        | `Baseline Assessment (Y/N)`        |
| `Most Recent Diagnostic YTD (Y/N)` | `Most Recent Assessment YTD (Y/N)` |
| `Diagnostic Gain`                  | `Assessment Gain`                  |
| `Diagnostic Language` (math only)  | `Assessment Language` (math only)  |

One genuinely new field: `Tactile Graphics`, on all subjects.

### Fields already absorbed

The July 2026 work in `9cf84eb97` and `4637ec3d9` already declared every other
new column in this vendor release: `items_completed`, `items_correct`,
`percent_items_correct` on i-Ready Pro Instruction by Lesson, and the Number
Sense K-2 and Number Relationships and Operation Concepts K-2 columns on
Personalized Instruction Summary. Only `tactile_graphics` and the four
`assessment_*` renames remain undeclared.

## Current production impact

Verified against Dagster on 2026-08-21.

| Asset                                                 | State                                                                 |
| ----------------------------------------------------- | --------------------------------------------------------------------- |
| `kippmiami/iready/personalized_instruction_summary`   | `math` materializes daily; `ela` stopped 2026-07-18. No FY27 reading. |
| `kippmiami/iready/diagnostic_results`                 | Nothing since 2026-07-18. FY27 partition holds 3,933 FY26 rows.       |
| `kippmiami/iready/personalized_instruction_by_lesson` | Reading not matched. No FY27 reading.                                 |
| `kippmiami/iready/instruction_by_lesson` (pro)        | Reading not matched. No FY27 reading.                                 |

Newark is on the same footing. Miami is roughly five weeks into its school year
with no FY27 reading instruction data and no FY27 assessment data at all.

The FY27 `diagnostic_results` partition is the sharper problem. Every July the
vendor's `Current_Year` folder lags its own rollover, so the new fiscal year's
partition transiently holds the prior year's file. It normally self-corrects
when the vendor rolls over. This year it will not, because the export was
renamed — so `_dagster_partition_academic_year=2026` is permanently pinned to
FY26 content unless we intervene.

## Design decisions

### Decision 1: keep the partition subject as `ela` (option A2)

**Chosen: A2.** The `subject` partition dimension stays
`StaticPartitionsDefinition(["ela", "math"])`. The vendor's new `reading` token
is translated at the ingestion boundary in both directions:

- The **sensor** maps a matched filename token back to a partition value
  (`reading` becomes `ela`).
- The **asset** maps a partition value forward to the token it should look for
  in the remote filename (`ela` becomes `reading`, for academic years at or
  after the cutover).

This is deliberately a boundary translation, not a new concept in the warehouse.
`_dagster_partition_subject` keeps the value `ela` forever, so **no dbt changes
are required for this decision at all** — including the 22 hardcoded
`_dagster_partition_subject = 'ela'` comparisons in the high-school
growth-measure tables of `stg_iready__diagnostic_results`.

#### Trade-offs, stated for review

The engineer taking this over should feel free to overrule this in favour of A1.
Both are defensible; the argument is genuinely close.

**What A2 buys:**

- Zero dbt changes for the subject rename. Zero downstream churn across the
  roughly 40 kipptaf models.
- Continuous history in one partition: FY21 through FY28 reading data all lives
  under `subject=ela`, so no query needs to know when the vendor renamed things.
- No orphaned partitions. A1 would leave `reading` partitions permanently
  missing for FY21-FY26 in the Dagster UI.
- The partition always pulls the canonically-named current file. The stale
  `_ela_` file left behind in `Current_Year` can trigger a sensor run but can
  never be the file that gets fetched (see the mechanism below).

**What A2 costs:**

- **The partition key no longer matches the filename.** Someone debugging
  `subject=ela` in FY27 will look for `..._ela_...` on the SFTP and not find it.
  This is the real cost and it is a maintenance-comprehension cost, paid
  forever. It is mitigated only by the translation living in one documented
  helper.
- **It requires an academic-year threshold constant.** The alias cannot key on
  "is this the latest partition." That rule works today and breaks next July,
  when FY27 moves out of `Current_Year` into a `2026/` archive folder that will
  contain `_reading_` files. So the cutover year is a hardcoded constant that a
  future reader must trust.
- **It carries vendor terminology debt.** `ela` is now our word, not i-Ready's.
  Every future i-Ready export that uses `reading` needs the same translation,
  and a Reading (Spanish) export will make the mismatch more visible.
- **It touches the shared asset builder.** `build_sftp_file_asset` gains a
  parameter used only by i-Ready. That said, it extends the
  `if group_name == "iready"` branch that already exists there for the
  `Current_Year` mapping, rather than adding a new special case.

**What A1 would buy instead:** partition keys that match filenames exactly, no
threshold constant, no shared-builder change, and a natural slot for
`reading_spanish` as a peer value. **What A1 would cost:** 22 one-line SQL edits
turning `= 'ela'` into `in ('ela', 'reading')`, a permanent split in how history
is keyed, and orphaned `reading` partitions for FY21-FY26.

A2 was chosen because the outage is live and A2's blast radius is confined to
two Python files, whereas A1 edits the most logic-dense model in the i-Ready
lineage during an incident fix.

### Decision 2: clean year boundary for Diagnostic to Inform (option B2)

**Chosen: B2.** Two Dagster assets with a hard fiscal-year boundary:

- `diagnostic_results` is capped at `end_fiscal_year=2026`.
- A new `inform_results` asset starts at `start_fiscal_year=2027`.

The alternative (B1) was a single asset with a regex accepting both prefixes.
That was rejected because, composed for `subject=math`, it matches **both**
`diagnostic_results_math_CONFIDENTIAL.csv` and
`i-ready_inform_results_math_CONFIDENTIAL.csv` in `Current_Year`.
`build_sftp_file_asset` raises on multiple matches, so B1 would need
`ignore_multiple_matches=True` and would then resolve by newest mtime. That is
correct today, but a vendor re-touch of the stale Diagnostic file would silently
win and quietly replace FY27 data with FY26 data. B2 makes that failure mode
impossible.

#### Refinement: union inside staging, not in kipptaf

The two assets are unioned **inside `stg_iready__diagnostic_results`**, not by
adding a parallel staging model and a four-way union in
`int_iready__diagnostic_results`.

This matters because `stg_iready__diagnostic_results` holds the only copy of a
large body of transformation logic: the placement-to-integer mappings, the
three-level placement rollup, and the 22-case high-school typical- and
stretch-growth-measure tables. A parallel staging model would either duplicate
that logic or require extracting it into a macro. Unioning at the source end of
the existing model keeps one contract, one copy of the logic, and — crucially —
means **no changes at all to `int_iready__diagnostic_results`, to the kipptaf
source declarations, or to any of the roughly 40 downstream models.**

The fiscal-year boundary is expressed as an explicit filter on each branch of
the union, which also disposes of the stray FY27 Diagnostic partition described
above:

```sql
-- diagnostic branch
where _dagster_partition_academic_year < 2026

-- inform branch
where _dagster_partition_academic_year >= 2026
```

### Decision 3: alias new vendor column names to existing internal ones

The Inform export's renamed fields are aliased **back** to our current internal
names rather than propagated:

| Vendor (new)                     | Internal (kept)                  |
| -------------------------------- | -------------------------------- |
| `assessment_gain`                | `diagnostic_gain`                |
| `baseline_assessment_y_n`        | `baseline_diagnostic_y_n`        |
| `most_recent_assessment_ytd_y_n` | `most_recent_diagnostic_ytd_y_n` |
| `assessment_language`            | `diagnostic_language`            |

`tactile_graphics` is genuinely new and enters under its own name.

This keeps the roughly 40 downstream models untouched. It is explicitly naming
debt: our column names will lag the vendor's terminology, and
`most_recent_diagnostic_gain` in `int_iready__diagnostic_results` will describe
an Inform measurement. Paying that debt is a rename sweep across the whole
i-Ready lineage and should be its own change, not part of an outage fix.

## Phase 1: restore FY27 ingestion

### Dagster

A new module holds the boundary translation, so the cutover year and the token
map are stated once:

```python
# src/teamster/libraries/iready/subjects.py

IREADY_SUBJECT_RENAME_ACADEMIC_YEAR = 2026
"""First `academic_year` partition whose remote filenames use the renamed
subject tokens. Equals FY2027; the vendor cut over during July-August 2026."""

REMOTE_SUBJECT_ALIASES = {"ela": "reading"}
"""Partition subject value -> the token that appears in the remote filename."""

PARTITION_SUBJECT_BY_REMOTE_TOKEN = {"reading": "ela"}
"""Inverse of the above, for deriving a partition key from a matched filename."""
```

`build_iready_sftp_asset` gains a `remote_subject_aliases` parameter and
forwards it to `build_sftp_file_asset` as a plain keyword argument. It is
deliberately **not** put in asset metadata — the sensor needs only the inverse
map, which is uniform across every i-Ready asset, so no per-asset metadata
plumbing (and no `JsonMetadataValue` coercion question) is required.

In `build_sftp_file_asset`, the existing `if group_name == "iready"` branch is
extended to compose the **file** regex with the aliased subject token. Today
that branch composes only the directory regex and lets the file regex be
composed after the `if`/`else` with the raw partition key; the file-regex
composition moves inside the branch so the alias can be applied:

```python
remote_subject = subject_key

if int(academic_year_key) >= IREADY_SUBJECT_RENAME_ACADEMIC_YEAR:
    remote_subject = subject_aliases.get(subject_key, subject_key)
```

The alias is uniformly `{"ela": "reading"}` across all four assets. The
`reading` versus `reading_english` difference is absorbed by placing
`(_english)?` **outside** the named group — required anyway, because
`regex_pattern_replace`'s group scanner does not permit nested parentheses
inside `(?P<name>...)`.

Resulting regexes, with the fiscal-year span each asset covers:

`personalized_instruction_summary` — FY2025 to current:

```text
personalized_instruction_summary_(?P<subject>ela|math|reading)_CONFIDENTIAL\.csv
```

`personalized_instruction_by_lesson` — FY2023 to current:

```text
(personalized|iready)_instruction_by_lesson_(?P<subject>ela|math|reading)(_CONFIDENTIAL)?\.csv
```

`instruction_by_lesson` (pro) — FY2025 to current:

```text
iready_pro_instruction_by_lesson_(?P<subject>ela|math|reading)_CONFIDENTIAL\.csv
```

`diagnostic_results` — FY2021 to **FY2026**, regex unchanged:

```text
diagnostic_results_(?P<subject>ela|math)(_CONFIDENTIAL)?\.csv
```

`inform_results` (new) — **FY2027** to current:

```text
i-ready_inform_results_(?P<subject>math|reading)(_english)?_CONFIDENTIAL\.csv
```

The sensor applies `PARTITION_SUBJECT_BY_REMOTE_TOKEN` to
`group_dict["subject"]` before building the `MultiPartitionKey`, in the same
place it already special-cases `academic_year == "Current_Year"`.

**Why the stale `_ela_` file is harmless.** For a Personalized Instruction asset
in `Current_Year`, the sensor's uncomposed regex matches both `_ela_` (stale,
mtime 2026-07-18) and `_reading_`. Both map to partition `ela`, and the sensor
already groups run requests by `(job_name, partition_key)`, so they collapse
into one run. The asset then composes `reading` for that partition and fetches
the reading file. The stale file can act as a trigger but can never be the
payload. This is worth a comment in the code, because it is not obvious.

`inform_results` reuses the extended `DiagnosticResults` pydantic model, so both
assets share one Avro schema. New fields to declare on it:

- `tactile_graphics`
- `assessment_gain`
- `baseline_assessment_y_n`
- `most_recent_assessment_ytd_y_n`
- `assessment_language`

The model is already a superset carrying both `comprehension_*` and
`reading_comprehension_*` from a previous vendor rename, so this follows the
established pattern.

### dbt

1. `src/dbt/iready/models/sources-external.yml` — add
   `src_iready__inform_results`, hive-partitioned over
   `iready/inform_results/*`, with `asset_key` of
   `[project_name, iready, inform_results]`.
1. `src/dbt/iready/models/staging/stg_iready__diagnostic_results.sql` — union
   the two sources at the top of the model with the fiscal-year filters and the
   column aliasing from Decision 3, then leave the rest of the model unchanged.
1. `src/dbt/iready/models/staging/properties/stg_iready__diagnostic_results.yml`
   — add `tactile_graphics` to the enforced contract.

No changes to `kipptaf`. No changes to `int_iready__diagnostic_results`,
`sources-kippmiami.yml`, or `sources-kippnj.yml`.

### Stray GCS objects

Capping `diagnostic_results` at FY26 orphans the already-written
`_dagster_partition_academic_year=2026/` objects under
`iready/diagnostic_results/` in both regions. The staging filter above makes
them invisible to every consumer, which is the safe and reversible fix and is
sufficient on its own.

Physically deleting that GCS prefix is optional cleanup. It is a destructive
shared-resource operation and must be run by a human with the prefix named
explicitly — do not script it as part of this change.

## Phase 2: Reading (Spanish) readiness

`i-ready_inform_results_reading_spanish_CONFIDENTIAL` is in the vendor's rename
table but has not appeared in either region. Spanish reading is a distinct
assessment, not a renaming of an existing one, so when it arrives it should
become a genuinely new `subject` partition value (`reading_spanish`), **not** an
alias onto `ela`.

The vendor also notes that Reading (Spanish) gains `Rush Flag`, `Percentile`,
`Annual Typical Growth Measure`, and `Percent Progress to Annual Typical Growth`
— all of which already exist on the English and Math exports, so the superset
schema already covers them.

No work now. Phase 1 should simply avoid foreclosing it, which adding a third
static partition value later does not.

## Phase 3: standards results (needs its own spec)

`standards_results_by_test` and `standards_results_ytd` have never been
ingested. They do not fit the existing i-Ready asset shape and should not be
forced into this change:

- **One file per grade.** Names carry a trailing `_2` through `_8`, so seven
  files exist per subject per year. This breaks the one-file-per-partition
  assumption in `build_sftp_file_asset`, which raises on multiple matches. Grade
  likely becomes a third partition dimension.
- **The column set varies per grade and per state.** Headers carry
  standard-specific columns such as
  `ELA.2.R.1.1 Story Elements: Grade 2: Score (%)`. A fixed Avro superset would
  need hundreds of columns and would break whenever a state revises its
  standards. The right shape is almost certainly long rather than wide, either
  unpivoted in the asset or loaded as a repeated field and unpivoted in dbt.
- **Header cells contain embedded newlines** inside quoted names, for example
  the Grade 2 grammar and punctuation standard. The column slugifier and
  `file_to_records` both need checking against this before anything else is
  designed.

Recommend a separate brainstorm and spec. Ingesting these is a new capability,
not a restoration, and it has no outage pressure behind it.

## Phase 4: retire `instructional_usage_data`

This lineage is dead and should be deleted rather than extended. Verified:

- No Dagster asset exists in any code location.
- `stg_iready__instructional_usage_data` is disabled in **both**
  `src/dbt/kippmiami/dbt_project.yml` and `src/dbt/kippnewark/dbt_project.yml`.
- `snapshot_iready__instructional_usage_data` is `enabled: false`.
- `int_iready__instructional_usage_data` is referenced only by that disabled
  snapshot and its own properties file. Nothing else consumes it —
  `rpt_tableau__iready_apm`'s `iu` alias is
  `stg_iready__personalized_instruction_summary`, not this model.
- The SFTP files are stale since 2025-07-21 in both regions and are absent from
  the vendor rename table.

Deletion set: the staging model and its properties in `src/dbt/iready`, the two
`dbt_project.yml` disable stanzas, the two kipptaf source declarations, the
intermediate model and its properties, the snapshot entry in
`kipptaf/snapshots/iready.yml`, and the snapshot source in
`kipptaf/models/iready/sources-bigquery.yml`.

`src/dbt/iready/CLAUDE.md` also states that only `kippnewark` disables this
model, which is stale — fix it in the same change.

## Testing and verification

1. **Unit tests for the boundary translation.** `subjects.py` is pure functions;
   cover both directions and the year threshold, including the FY26 boundary and
   an archive year below it. No network needed.
1. **Sensor test.** `tests/sensors/sftp/test_sensors_sftp_iready.py` — cursors
   in `test_iready_sftp_sensor_kippnewark` are hardcoded and will need updating,
   and a new cursor key is needed for `inform_results`.
1. **Asset integration tests.** `tests/assets/test_assets_iready_sftp.py` needs
   a case for `inform_results` in both regions. Note two pre-existing problems
   the engineer will hit: `_test_asset` picks a **random** partition when none
   is given, and `diagnostic_results` spans partitions 2020 through 2025 while
   the Miami SFTP only retains `2024/`, `2025/`, and `Current_Year` — so that
   test is already flaky for want of source files. Also,
   `test_iready_personalized_instruction_by_lesson_kippmiami` and
   `test_iready_instruction_by_lesson_kippmiami` import the same asset, so one
   of them tests nothing new.
1. **dbt build.** From each consuming project:
   `uv run dbt build --select stg_iready__diagnostic_results+ --project-dir src/dbt/kippmiami`
   and the same for `kippnewark`.
1. **Data verification.** After the first materialization, confirm for each
   region that FY27 partitions carry FY27 rows, by comparing the partition
   column against the file's own academic-year column:

   ```sql
   select
       _dagster_partition_academic_year,
       _dagster_partition_subject,
       academic_year,
       count(*) as n,
   from {{ ref("stg_iready__diagnostic_results") }}
   where _dagster_partition_academic_year >= 2026
   group by 1, 2, 3
   order by 1, 2, 3
   ```

   Any row where `academic_year` reads `2025-2026` under partition `2026` is the
   rollover artifact described below, not a code defect.

## Risks

- **The vendor's `Current_Year` folder still holds some FY26 content.** NJ's
  `iready_instruction_by_lesson_reading` (385 MB, dropped 2026-08-04) contains
  FY26 rows, so the first materialization of that asset's FY27 partition will
  ingest last year's data under this year's partition key. This is the
  pre-existing seasonal rollover artifact, not something Phase 1 introduces, and
  it self-corrects when the vendor refreshes the folder. Use the verification
  query above to confirm, and re-materialize once real FY27 content lands.
- **The cutover-year constant is a trust point.** If the vendor's rename had
  applied from a different academic year than FY27, or applies differently per
  region, `IREADY_SUBJECT_RENAME_ACADEMIC_YEAR` would silently resolve the wrong
  filename. Observed evidence says FY27 in both regions.
- **A2's partition-to-filename mismatch is permanent** and will confuse future
  debugging. This is the accepted cost of Decision 1; see the trade-offs there.
- **Reading (Spanish) will widen the mismatch.** Once `reading_spanish` exists
  as its own partition value alongside an `ela` partition that actually means
  English reading, the naming will read oddly. Worth revisiting Decision 1 at
  that point.

## Open questions

- Should the naming debt from Decision 3 get a tracking issue now, or wait until
  someone is annoyed by it?
- Does Camden or Paterson have its own i-Ready SFTP subfolder that needs the
  same treatment? Only `fl-kipp_miami` and `nj-kipp_nj` were checked, and the
  two existing code locations cover only those.
