# Cambium TIDE NJGPA ingestion — design

Refs #4899

## Context

New Jersey moved NJGPA score reporting from Pearson Access Next to Cambium TIDE
beginning with the Spring 2026 administration. Two SY25-26 district summative
record files are in hand:

| File                                                      | District code                      | Code location | Rows |
| --------------------------------------------------------- | ---------------------------------- | ------------- | ---- |
| `2026_Spring_7325_District_Summative_Record_File_GPA.csv` | 7325 (TEAM Academy Charter School) | `kippnewark`  | 598  |
| `2026_Spring_1799_District_Summative_Record_File_GPA.csv` | 1799 (KIPP Cooper Norcross)        | `kippcamden`  | 252  |

The Fall 2025 NJGPA administration arrived through Pearson (207 Newark rows,
`period` of Fall, academic year 2025). Spring 2026 is the first Cambium
administration and carries the same academic year, so the two vendors coexist
inside one academic year. Cambium must union alongside the Pearson models, not
replace them.

## Why this is a new source, not schema drift

Only **11 of 225** column names survive slugification into the existing NJGPA
Avro schema. Pearson shipped camel-case headers and Cambium ships spaced
headers, and `slugify(separator="_")` does not split camel case:

| Header as shipped | Slugified         | Vendor  |
| ----------------- | ----------------- | ------- |
| `LastOrSurname`   | `lastorsurname`   | Pearson |
| `Last or Surname` | `last_or_surname` | Cambium |

The 11 accidental overlaps are single-word or already-spaced headers: `asian`,
`gender`, `home_language`, `homeless`, `homeless_primary_nighttime_residence`,
`onlinepcr1`, `onlinepcr2`, `period`, `retest`, `subject`, `white`.

So `src_pearson__njgpa` cannot absorb these files. Appending them to that GCS
prefix would also corrupt the existing external table: AVRO externals autodetect
from the last-alphabetical file, and a mixed-schema scan drops fields for the
whole scan.

The filename convention changed as well. The old pattern carried a 2-digit year
plus `spr` or `fbk`; the new pattern carries a 4-digit year, a full season word,
and the district code.

## Goals

1. Ingest the Cambium NJGPA summative record file per region on the existing
   Couchdrop SFTP sensor.
2. Land it in the warehouse as a contract-enforced staging model.
3. Union it into the existing NJ state assessment stream so that every current
   consumer (dashboards, graduation pathway codes, topline weekly, the DeansList
   extract) picks it up with no change in behavior.
4. Preserve reporting continuity across the vendor boundary.

## Non-goals

- **NJSLA and NJSLA Science.** Those feeds may also move to Cambium, but the
  files have not been seen and the layout cannot be assumed to match NJGPA. The
  project is structured so that adding a feed later is additive: a new Pydantic
  model, a new asset, a new source entry, a new staging model. Nothing designed
  here needs to change.
- **Renaming the NJ state assessment stream.** `int_pearson__all_assessments`
  will carry Cambium data under a Pearson name. This is misleading and should be
  fixed, but a rename touches roughly 15 files across dashboards and extracts,
  and bundling it with a new pipeline makes both harder to review. Recorded as
  follow-up work in _Deferred work_ below.
- **Backfilling Pearson history.** Nothing about the Pearson models changes.

## Architecture

```text
Couchdrop SFTP  /data-team/<region>/cambium/njgpa/
      |
      |  couchdrop_sftp_sensor (existing, one line added per region)
      v
Dagster asset  <region>/cambium/njgpa          [build_sftp_file_asset]
      |
      |  io_manager_gcs_avro
      v
GCS  gs://teamster-<region>/dagster/<region>/cambium/njgpa/
      |
      |  BigQuery AVRO external table
      v
src_cambium__njgpa                             [dbt/cambium, per region]
      v
stg_cambium__njgpa                             [dbt/cambium, Cambium vocabulary]
      v
stg_cambium__njgpa                             [kipptaf, region union + alignment]
      v
int_pearson__all_assessments                   [kipptaf, one added relation]
      v
dim_assessment_administrations, dim_assessments, fct_assessment_scores_enrollment_scoped,
rpt_tableau__state_assessments_dashboard, int_students__graduation_path_codes, and ~10 more
```

### Ingestion (Dagster)

**`src/teamster/libraries/cambium/schema.py`** — a Pydantic `NJGPA` model
subclassing `SFTPFile`, with all 225 fields typed `str | None = None`, matching
the Pearson library's convention. Generated mechanically from the actual CSV
headers by a throwaway script; not hand-typed.

**`src/teamster/code_locations/<region>/cambium/`** — `__init__.py`, `schema.py`
(calls `py_avro_schema.generate()`), and `assets.py`:

```python
njgpa = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "cambium", "njgpa"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/cambium/njgpa",
    remote_file_regex=(
        r"(?P<administration_year>\d{4})_(?P<administration>[A-Za-z]+)"
        r"_7325_District_Summative_Record_File_GPA\.csv"
    ),
    avro_schema=NJGPA_SCHEMA,
    ssh_resource_key="ssh_couchdrop",
    partitions_def=MultiPartitionsDefinition(
        {
            "administration_year": StaticPartitionsDefinition(
                [
                    str(year)
                    for year in range(2026, CURRENT_FISCAL_YEAR.fiscal_year + 1)
                ]
            ),
            "administration": StaticPartitionsDefinition(["Spring", "Fall"]),
        }
    ),
)
```

Camden is identical with `1799` in place of `7325`.

**Sensor** — one entry appended to each region's `couchdrop/sensors.py`
`asset_selection`. The sensor lists the region's Couchdrop tree recursively and
matches each asset's own `remote_dir_regex` and `remote_file_regex` metadata, so
a new subfolder needs no sensor configuration beyond that entry. Named regex
groups become the partition key; the per-asset cursor of max file mtime keeps
each file firing once.

**`definitions.py`** — the new module's assets added to each region's asset
list.

### Source project: `src/dbt/cambium/`

Modeled on `src/dbt/pearson/`. Contents:

- `dbt_project.yml` — `+schema: cambium`, `staging: +contract: enforced: true`,
  `bigquery_external_connection_name: null` (overridden by consumers)
- `packages.yml`, `package-lock.yml`
- `models/sources-external.yml` — `src_cambium__njgpa` as an AVRO external over
  `{{ var('cloud_storage_uri_base', ...) }}/cambium/njgpa/*`, with
  `meta.dagster.asset_key` of `[{{ project_name }}, cambium, njgpa]`, using the
  standard target-conditional schema prefix pattern
- `models/staging/stg_cambium__njgpa.sql` plus
  `models/staging/properties/stg_cambium__njgpa.yml`
- `CLAUDE.md` naming the project's purpose and its consumer-discovery command

This layer stays in **Cambium's own vocabulary**. Its responsibilities:

1. Cast strings to their real types — `test_scale_score` and
   `test_performance_level` to `numeric`, the identifiers to `int64`, the unit
   start and end fields to `timestamp`.
1. Apply the attemptedness filter carried over verbatim from Pearson:
   `where summative_flag = 'Y' and test_attemptedness_flag = 'Y'`.
1. Derive `test_date` as the date of the earliest non-null unit online start
   timestamp across units 1 through 4.
1. Derive `academic_year` as `cast(left(assessment_year, 4) as int)`.

Uniqueness test on `student_test_uuid`, verified 1:1 with rows in both files
(252 of 252, 598 of 598).

Registered as a package in `kippnewark` and `kippcamden` only. Paterson has
`stg_pearson__njgpa` disabled and does not sit for NJGPA, so adding the package
there would build an empty model over a nonexistent external.

### Alignment and union: `src/dbt/kipptaf/models/cambium/`

- `sources-kippnewark.yml`, `sources-kippcamden.yml` — regional source entries
  for `stg_cambium__njgpa`, with `meta.dagster.asset_key` and `group: cambium`,
  using the region schema pattern (dev-only prefix)
- `staging/stg_cambium__njgpa.sql` plus properties — unions the two regions via
  `dbt_utils.union_relations` and maps into the shared shape

This model is the single place where Cambium becomes NJ-state-assessment-shaped.
Every translation decision lives here so a reviewer has one file to read.

**Direct renames:**

| Cambium column                              | Shared column                          |
| ------------------------------------------- | -------------------------------------- |
| `state_student_identifier`                  | `statestudentidentifier`               |
| `local_student_identifier`                  | `localstudentidentifier`               |
| `first_name`                                | `firstname`                            |
| `last_or_surname`                           | `lastorsurname`                        |
| `assessment_grade`                          | `assessmentgrade`                      |
| `assessment_year`                           | `assessmentyear`                       |
| `test_code`                                 | `testcode`                             |
| `test_performance_level`                    | `testperformancelevel`                 |
| `test_scale_score`                          | `testscalescore`                       |
| `student_test_uuid`                         | `studenttestuuid`                      |
| `student_with_disabilities`                 | `studentwithdisabilities`              |
| `hispanic_or_latino_ethnicity`              | `hispanicorlatinoethnicity`            |
| `american_indian_or_alaska_native`          | `americanindianoralaskanative`         |
| `black_or_african_american`                 | `blackorafricanamerican`               |
| `native_hawaiian_or_other_pacific_islander` | `nativehawaiianorotherpacificislander` |
| `two_or_more_races`                         | `twoormoreraces`                       |
| `multilingual_learner`                      | `englishlearnerel`                     |

`asian`, `white`, `period`, and `subject` already match.

**Derivations, all mirroring `stg_pearson__njgpa` exactly:**

| Shared column               | Expression                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `assessment_name`           | `'NJGPA'`                                                                          |
| `is_proficient`             | `testperformancelevel = 2`                                                         |
| `testperformancelevel_text` | 2 to `Graduation Ready`, 1 to `Not Yet Graduation Ready`                           |
| `discipline`                | `if(subject = 'Mathematics', 'Math', 'ELA')`                                       |
| `subject_area`              | `if(subject = 'English Language Arts/Literacy', 'English Language Arts', subject)` |
| `administration_period`     | `if(period = 'FallBlock', 'Fall', period)`                                         |
| `module_code`               | `testcode` (no NJSLA Science code remap applies to NJGPA)                          |
| `test_grade`                | `11` — constant, see D3                                                            |
| `testscorecomplete`         | `1` — constant, see D2                                                             |
| `_dbt_source_project`       | `{{ extract_source_project("union_relations") }}`                                  |

`is_bl_fb` is omitted. It is in the union's `include` list but
`stg_pearson__njgpa` does not produce it either, so `union_relations` null-fills
it for both NJGPA relations.

### Marts

**`int_pearson__all_assessments`** — add `ref("stg_cambium__njgpa")` to the
`dbt_utils.union_relations` relations list. One line. Because the alignment
model emits the exact shared column names, all downstream consumers work
unchanged.

**`dim_assessment_administrations`** — add a `state_nj_njgpa_cambium`
administrations CTE reading `ref("stg_cambium__njgpa")`, parallel to the
existing `state_nj_njgpa_administrations`. This is **required**, not cosmetic:
the administration surrogate key hashes `academic_year` and
`administration_period` alongside region, and academic year 2025 with period
Spring is a new tuple — Pearson's academic year 2025 holds only Fall. Without
this CTE, the `relationships` test on
`fct_assessment_scores_enrollment_scoped.assessment_administration_key` orphans
every Cambium score.

**`dim_assessments`** — add a parallel CTE. Strictly not required: the surrogate
key is `(assessment_type, module_code, source_assessment_id, test_type)`, which
excludes grade level and academic year, so Cambium's ELAGP and MATGP rows dedup
into the existing Pearson rows and hash identically. Added anyway so the
dimension does not silently depend on Pearson history remaining in place
forever. See D7.

**`fct_assessment_scores_enrollment_scoped`** — no change. It reads
`int_pearson__all_assessments` and constructs the administration key from the
same eight hash inputs.

**Repository plumbing:**

- `src/dbt/cambium/**` and `src/teamster/libraries/cambium/**` added to the
  push-path filters in `.github/workflows/deploy-prod-kippnewark.yaml` and
  `deploy-prod-kippcamden.yaml`
- `docs/reference/automations.md` sensor tables updated with the new asset
- `src/dbt/CLAUDE.md` project inventory and dependency map updated

## Decisions for the data engineer to confirm

Each decision below is reversible. The alternatives are recorded with the
evidence so none of this needs re-deriving.

### D1 — vendor translation lives in kipptaf, not the source project

**Chosen.** `src/dbt/cambium/` cleans Cambium in Cambium's vocabulary; kipptaf's
`stg_cambium__njgpa` does the region union and the mapping to shared names. This
matches how the repository already layers, and puts the risky semantic decisions
in a file a reviewer will read.

**Alternative A** — emit shared names directly from the source project. Smallest
diff, one added line downstream. Rejected because a Cambium source model that
speaks Pearson is confusing, and D2 and D3 would be buried in a source-package
file nobody revisits.

**Alternative C** — rename the stream to something vendor-neutral as part of
this change. Correct end state; deferred as its own PR.

### D2 — `testscorecomplete` is synthesized as a constant `1`

**Chosen**, at the user's direction, because it changes no existing model.

Cambium's `test_score_complete` is 100 percent NULL in both files.
`int_students__graduation_path_codes` filters `n.testscorecomplete = 1`, and
`union_relations` null-fills absent columns, so without a value every Cambium
NJGPA score would silently drop out of graduation-pathway determination.

**Evidence that a constant is faithful:** `testscorecomplete` is `1` on every
row of both regions' Pearson staging tables — 3,081 Newark, 1,049 Camden, no
other value and no nulls. The staging filter
`where summative_flag = 'Y' and test_attemptedness_flag = 'Y'` has already
removed everything that would fail the predicate. The same filter behaves
identically on the Cambium files:

| Measure                                        | Camden (1799) | Newark (7325) |
| ---------------------------------------------- | ------------- | ------------- |
| Rows                                           | 252           | 598           |
| Survive the summative and attemptedness filter | 249           | 564           |
| Of those, `test_status` of `completed`         | 249 (100%)    | 564 (100%)    |
| Of those, missing a scale score                | 0             | 0             |

The `pending` (5) and `invalidated` (1) rows in the Newark file are already
excluded by the flag filter.

**Alternative A — retire the predicate.** Drop `n.testscorecomplete = 1` from
`int_students__graduation_path_codes`. Provably a no-op for all 4,130 existing
rows, so it changes nothing today, and it removes the trap for the next vendor
permanently. **Recommended as follow-up work**, ideally as its own commit with
this evidence attached, since it edits a graduation-pathway model.

**Alternative C — derive it**, as `if(test_status = 'completed', 1, 0)`.
Semantically faithful to the original intent, but post-filter it evaluates to 1
for every row, so it is the chosen option with extra indirection.

### D3 — `test_grade` is a hardcoded `11`

**Chosen.** Neither Cambium field reproduces Pearson's behavior.

Pearson's `assessmentgrade` is `Grade 11` on all 4,130 rows, every
administration and both regions, while the _student's_ grade
(`gradelevelwhenassessed`) is 12 for fall retakers:

| Region | Administration | `assessmentgrade` | Student grade | Rows  |
| ------ | -------------- | ----------------- | ------------- | ----- |
| Newark | Spring         | Grade 11          | 11            | 2,434 |
| Newark | Spring         | Grade 11          | 12            | 2     |
| Newark | FallBlock      | Grade 11          | 12            | 535   |
| Newark | Fall           | Grade 11          | 12            | 207   |
| Camden | Spring         | Grade 11          | 11            | 714   |
| Camden | Spring         | Grade 11          | 12            | 4     |
| Camden | FallBlock      | Grade 11          | 12            | 267   |
| Camden | Fall           | Grade 11          | 12            | 106   |

So `test_grade` is already a constant 11 today, retakers included — and there
are 12th-grade retakers in spring as well as fall.

Cambium's `assessment_grade` is the **test design level**: `Grade 10` for ELA
(the subtest is `NJ-GEN-SUM-GT-ELA-NJGPA-COMBINED-10`) and `Grade 11` for Math,
while `grade_level_when_assessed` is 11 for every row in both files. Deriving
from `assessment_grade` splits ELA into a grade-10 and a grade-11 series at the
vendor boundary; deriving from `grade_level_when_assessed` sends every fall
retaker to grade 12. Only the constant matches current behavior.

**The constant also prevents nondeterminism.** `dim_assessments` dedups with
`partition_by="assessment_type, source_assessment_id, module_code, test_type"`
and `order_by="title"`, and `title` is the constant `'NJGPA'`. Had Cambium
emitted grade 10 for ELA, the ELAGP row would have had two tied candidate grade
levels with no tiebreaker, and `grade_level_tested` could have flipped between
builds.

**Alternative** — report fall retakers as grade 12 by deriving from
`grade_level_when_assessed`. A defensible reporting choice, but a change from
today's behavior for the roughly 1,100 historical fall rows' worth of equivalent
future data, and it would need a matching change to the Pearson model to stay
consistent.

The student's actual grade is not lost: `grade_level_when_assessed` survives in
`src/dbt/cambium`, and the enrollment-scoped fact resolves enrollment
independently.

### D4 — new Couchdrop folder per region

**Chosen and verified in place.** `/data-team/kippnewark/cambium/njgpa/` and
`/data-team/kippcamden/cambium/njgpa/`, both created 2026-08-18 with each
region's file present at the expected byte size (647,606 Newark; 306,106
Camden).

The parent of each `cambium` folder is exactly the `folder_id` already
configured in that region's `build_couchdrop_sftp_sensor` call —
`1B24uuik9MuBf-pKrrRn1lt3cWVtVAYJE` for Newark,
`1BKZgGl_LcHIOVLrDo8eMMZLGFsc2Nk1o` for Camden — so the sensor's recursive
listing reaches the new subtree with no sensor configuration change beyond the
asset-selection entry.

**Alternative** — reuse `/data-team/<region>/pearson/njgpa/`. No folders to
create, but two unrelated schemas would share a directory with both assets
watching it, and the Pearson regex would have to keep excluding Cambium
filenames every future administration.

### D5 — the year partition dimension is `administration_year`, not `fiscal_year`

**Chosen.** Pearson's dimension is named `fiscal_year` but is not one: `pcspr25`
holds Spring 2025 (FY25) while `pcfbk25` holds Fall 2025 (FY26). Cambium's
`2026_Spring` is the calendar year of the administration, which is consistent
across seasons because a fall administration always falls in the same calendar
year as its academic year's start. Naming the dimension for what it actually is
avoids encoding a wrong assumption.

Academic year still comes from the file's own `assessment_year` field, exactly
as Pearson does. The partition is a file-addressing scheme, never a semantic.

### D6 — district code hardcoded per region

**Chosen.** `7325` in the Newark regex, `1799` in Camden.
`build_sftp_file_asset` raises on multiple matches, so a `\d+` wildcard would
break the moment a stray file from the other district landed in a folder.
Depends on D4 keeping the regions separate.

**Verified** against the real paths and adversarial cases. Both live files match
their own region's pattern and yield `administration_year` of `2026` and
`administration` of `Spring`. A Camden-coded file placed in the Newark folder
does **not** match, which is the protection this decision buys. No historical
Pearson NJGPA filename matches either Cambium pattern, and no Cambium path
matches the Pearson pattern — no cross-contamination in either direction.

### D7 — `dim_assessments` gets a Cambium CTE it does not strictly need

**Chosen** for explicitness. See _Marts_ above for why it is redundant today.
Skipping it is defensible and shrinks the diff by one CTE.

### D8 — the fall season token is unconfirmed, and the precedent is that it drifts

`Spring` is verified from the files in hand. `Fall` is an inference, and the
Pearson filename history on Couchdrop shows the vendor changing its own season
token between administrations:

| Administration | Pearson filename suffix |
| -------------- | ----------------------- |
| Fall 2024      | `..._GPA_FallBlock.csv` |
| Fall 2025      | `..._GPA_FALL.csv`      |
| Spring         | `..._GPA_Spring.csv`    |

So the fall token changed spelling **and** case across consecutive years under
the previous vendor. `Fall`, `FALL`, and `FallBlock` are all plausible for
Cambium.

The regex tolerates any of them — `(?P<administration>[A-Za-z]+)` matches all
three — so the only thing needing a change is the `StaticPartitionsDefinition`
value list. The failure mode is contained: the sensor extracts the token, builds
a `MultiPartitionKey`, and Dagster rejects an unrecognized partition key with a
visible sensor error. Loud, not silent data loss, and a one-line fix.

Worth confirming with NJDOE ahead of the fall administration; not worth blocking
this change on.

**Consequence for the partition values:** declaring `["Spring", "Fall"]` is a
guess for half the list. An alternative is to declare `["Spring"]` only and add
the fall value when the first fall file is seen, which makes the guess explicit
rather than latent. Either way the fall administration cannot land unnoticed.

### D9 — project named `cambium`, scoped to NJGPA

**Chosen** at the user's direction. Vendor-named, matching `pearson`, `iready`,
and `renlearn`. NJSLA is excluded because its Cambium layout is unknown.

## Verified source characteristics

Established by profiling both files and querying the existing Pearson tables.

**Carries over unchanged:**

| Field                       | Value                                                     |
| --------------------------- | --------------------------------------------------------- |
| `test_code`                 | `ELAGP`, `MATGP` — identical to Pearson                   |
| `subject`                   | `English Language Arts`, `Mathematics` — identical        |
| `test_performance_level`    | 1 and 2 — same Graduation Ready mapping                   |
| `period`                    | `Spring`                                                  |
| `assessment_year`           | `2025-2026`, parses to academic year 2025                 |
| `student_with_disabilities` | `N`, `IEP`, `504`, `B` — same domain                      |
| `student_test_uuid`         | Unique per row in both files                              |
| `local_student_identifier`  | 5 to 6 digit numerics, matching the existing distribution |

**Newly null**, populated under Pearson: `test_reading_scale_score`,
`test_writing_scale_score`, `test_reading_csem`, `test_writing_csem`,
`test_csem_probable_range`, `test_score_complete`, `student_uuid`,
`battery_form_id`, `raw_score`, `studentgrowthpercentile`. Only
`test_score_complete` has a downstream consumer (D2); the rest are unreferenced
outside the Pearson staging model but still need declaring in the enforced
contract.

**New and worth keeping:** `oppkey`, `thetascore`, `theta_score_se`,
`scale_score_se`, `test_status`, subclaim `Label`, `RawScore`, `ScaleScore` and
`ScaleScoreSE` fields (Pearson supplied only a category), subclaims 6 through 8,
`composition_rubric_score`, `writing_prompt_essay_type`, `justproficientmean`,
`assessmentsubtestidentifier`.

**Out-of-district testing.** Two rows in the Newark file were tested at `8223`
(Legacy Treatment Services), with `accountable_district_code` still `7325`. The
Pearson models key on accountable district, so this needs no special handling —
noting it so it is not mistaken for bad data.

**Test mode.** `test_mode` is `O` (online) on every row, and no paper attempt
date field exists in the new layout. `test_date` therefore derives from the unit
online start timestamps alone. If paper testing appears,
`assessmentsessionactualstartdatetime` (format `MMDDYYYYHHMM`) is the fallback.

**Unit count.** Cambium carries units 1 through 4; Pearson carried 1 through 3.
Units 3 and 4 are entirely null in both files today, but `test_date` should take
the earliest across all four.

## Rollout sequence

Order matters. A brand-new external source cannot be staged until its asset has
materialized at least once, because AVRO autodetect needs at least one file.

1. **Ops** — create the two Couchdrop folders and drop each region's file into
   its own folder.
1. **Merge-blocked code** — all of the above, on this branch.
1. **Pre-merge** — open the PR non-draft so the branch deployment builds,
   materialize both assets there, then stage the externals against the test
   bucket with a `cloud_storage_uri_base` override of
   `gs://teamster-test/dagster/<project>` and `ext_full_refresh: true`, so dbt
   Cloud CI can build.
1. **Merge.**
1. **Immediately post-merge** — launch both assets in prod. External sources are
   excluded from the dependency gate, so the first post-deploy tick otherwise
   requests the staging model and fails `stage_external_sources` against a still
   empty prod prefix.
1. **Post-merge** — re-stage the prod externals.
1. **Ops** — add student crosswalk rows for the students with no local
   identifier, once their Cambium UUIDs are visible in the warehouse.

## Verification plan

1. `uv run dagster definitions validate` for both code locations.
1. Asset materializes in the branch deployment with the expected record counts:
   598 Newark, 252 Camden.
1. Avro schema validity check passes with no drift warning.
1. `dbt build --select stg_cambium__njgpa+` in each region and in kipptaf.
1. `stg_cambium__njgpa` row counts after the attemptedness filter: 564 Newark,
   249 Camden.
1. `int_pearson__all_assessments` gains exactly 813 rows for academic year 2025
   period Spring, and its existing uniqueness test still passes.
1. `dim_assessment_administrations` gains the Spring 2026 tuples, and the
   `relationships` test on
   `fct_assessment_scores_enrollment_scoped.assessment_administration_key` shows
   zero orphans.
1. `dim_assessments` row count is unchanged — Cambium dedups into the existing
   NJGPA rows. A change here means D3 was not applied correctly.
1. `test_grade` is 11 on every Cambium row.
1. `int_students__graduation_path_codes` returns NJGPA rows for Cambium
   students. Confirms D2 worked.
1. `test_incorrect_student_number_pearson` singular test — expect a small number
   of failures for the students with no local identifier, resolved by the
   crosswalk step.
1. `localstudentidentifier` join rate against `stg_powerschool__students` per
   region, as a coverage check.
1. `trunk check --force` on every changed file.

## Deferred work

1. **Retire the `testscorecomplete = 1` predicate** in
   `int_students__graduation_path_codes` (D2, alternative A). Provably a no-op
   today; removes the trap for the next vendor.
1. **Rename the NJ state assessment stream** away from
   `int_pearson__all_assessments` to something vendor-neutral (D1, alternative
   C).
1. **NJSLA and NJSLA Science on Cambium**, once those files are seen.

## Risks

| Risk                                             | Mitigation                                                                         |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| Fall season token differs from `Fall`            | Sensor raises on invalid partition key; one-line fix (D8)                          |
| Filename pattern changes between administrations | Regex is the contract; confirm with NJDOE before the next administration           |
| Cambium adds columns mid-year                    | Avro schema check warns on drift; fix by declaring the field in the Pydantic model |
| `dim_assessments` grade level flips              | Prevented by D3; the verification plan asserts an unchanged row count              |
| Both districts' files land in one folder         | Asset raises on multiple matches rather than ingesting the wrong district          |
