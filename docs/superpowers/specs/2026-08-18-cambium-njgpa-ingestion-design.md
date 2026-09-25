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
   extract) picks it up without code changes of its own.

   One consumer's **output** does change, intentionally:
   `int_topline__state_assessments_weekly` currently reports empty NJ 11th-grade
   state proficiency for AY2025 and becomes NJGPA-driven. See the verification
   plan.

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
# One list feeds BOTH the regex alternation and the partition values, so they
# cannot drift. See D8: an unknown season token must fail to MATCH rather than
# produce an invalid partition key, which would stall the region's whole sensor.
ADMINISTRATIONS = ["Spring", "Fall", "FALL", "FallBlock"]

njgpa = build_sftp_file_asset(
    asset_key=[CODE_LOCATION, "cambium", "njgpa"],
    remote_dir_regex=rf"/data-team/{CODE_LOCATION}/cambium/njgpa",
    remote_file_regex=(
        r"(?P<administration_year>\d{4})"
        # longest-first so `FallBlock` is not shadowed by `Fall`
        rf"_(?P<administration>{'|'.join(sorted(ADMINISTRATIONS, key=len, reverse=True))})"
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
            "administration": StaticPartitionsDefinition(ADMINISTRATIONS),
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
1. Derive `test_date` as the earliest non-null unit online start timestamp
   across units 1 through 4, **coalesced to a parsed
   `assessmentsessionactualstartdatetime`** — required, because the unit
   timestamps are ELA-only. See _Verified source characteristics_ below.
1. Derive `academic_year` as `cast(left(assessment_year, 4) as int)`.
1. Carry `test_score_complete` through as `numeric` even though Cambium sends it
   entirely null, so the vendor difference is visible in the contract rather
   than appearing downstream as a `union_relations` null-fill artifact.

Uniqueness test on `student_test_uuid`, verified 1:1 with rows in both files
(252 of 252, 598 of 598), plus `not_null` on `test_date`. Every staging test
carries `config: severity: error` — both district projects set
`data_tests: +severity: warn` as the default, so a staging test without an
explicit severity silently degrades to a warning and never fails CI.

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
| `administration_period`     | `if(upper(period) like 'FALL%', 'Fall', period)` — see below                       |
| `module_code`               | `testcode` (no NJSLA Science code remap applies to NJGPA)                          |
| `test_grade`                | `case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end` — see D3            |
| `testscorecomplete`         | passthrough, genuinely NULL from Cambium — see D2                                  |
| `_dbt_source_relation`      | passthrough from `union_relations` — see below                                     |
| `_dbt_source_project`       | `{{ extract_source_project("union_relations") }}`                                  |

**`administration_period` normalizes case-insensitively.** Pearson's model uses
a bare `if(period = 'FallBlock', 'Fall', period)`, which is correct for
Pearson's observed values. But D8 establishes that the fall token drifts in
spelling and case, and the file's own `period` column is a separate field from
the filename token. If Cambium's `period` arrives as `FALL`, an exact-match
normalization leaves it as `'FALL'` — which produces a **separate**
`dim_assessment_administrations` tuple from the Pearson `'Fall'` rows and splits
the Fall series on the state assessments dashboard, invisibly (the resolver
joins the same value on both sides, so nothing errors). `administration_period`
also carries `not_null` and `accepted_values: [Spring, Fall]` tests so a novel
value fails loudly instead of forking a series.

**`_dbt_source_relation` must be selected explicitly.** It is in the union's
`include` list and all four existing relations carry it. An earlier draft
omitted it from the alignment model — it is only _read_ inside
`extract_source_project` — which would have null-filled it for all 813 rows in a
column documented as the union's source-relation identifier. Blast radius today
is limited (the only readers join on `_dbt_source_project` instead), but it
breaks the `_dbt_source_relation` / `_dbt_source_project` pairing invariant in
`kipptaf/CLAUDE.md` for a one-word fix.

**Deviation worth naming:** `kipptaf/CLAUDE.md` says uniqueness tests and
`materialized: table` belong on the per-region staging models, not the
kipptaf-level union view. This model has both. That is deliberate — it is not a
pure passthrough (every vendor translation lives here) and the existing
`stg_pearson__njgpa` also sets `materialized: table` — but it is a documented
deviation rather than an oversight.

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
  **push** path filters in `.github/workflows/deploy-prod-kippnewark.yaml` and
  `deploy-prod-kippcamden.yaml`
- `src/teamster/libraries/cambium/**` also added to the **`pull_request`** path
  filters in both workflows. The `pull_request` lists exclude `src/dbt/*` source
  projects by design (dbt Cloud CI covers those) but do enumerate every library
  individually, `pearson` included. Without it, a future PR that regenerates
  only the Cambium Pydantic schema gets no branch deployment — which is exactly
  the situation the rollout depends on for staging a new Avro schema.
- `.devcontainer/scripts/postCreate.sh` — hardcodes `dbt deps --project-dir` per
  project. Without a cambium line, a fresh Codespace has no `dbt_packages/` for
  the new project and cannot parse it. **Hook-protected**: must be handed to the
  user as a manual application block, not edited directly.
- `.vscode/scripts/update-dependencies.sh` — the `DBT_PROJECTS` array, so
  cambium is included in `dbt deps --upgrade`. Not hook-protected.
- `scripts/CLAUDE.md` — a Script Catalog row for the schema generator.
- `src/dbt/CLAUDE.md` project inventory, count, and dependency map. In the map,
  `cambium ──────┤` goes **second**, between `amplify` and `deanslist`: the
  first row carries a corner glyph (`amplify ──────┐`), so inserting above it
  breaks the drawing and misplaces it alphabetically.
- `docs/reference/automations.md` — needs regenerating, but **not** in a
  Codespace: `gen-automations-doc.py` skips code locations that fail to import
  (kipptaf and kippmiami both do, on unset credentials) and would drop them from
  the catalog. Hand off to a full environment.

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

**Chosen: option D — `coalesce` at the single consumer.** Change
`int_students__graduation_path_codes` from `n.testscorecomplete = 1` to
`coalesce(n.testscorecomplete, 1) = 1`. One line, in the one model that cares.
Cambium's genuinely-null column flows through untouched, no vestigial constant
enters the shared stream, and the follow-up item this decision would otherwise
have created is closed in the same change.

This supersedes an earlier choice to synthesize `1 as testscorecomplete` in the
alignment model. That option was picked to avoid touching a graduation-pathway
model at all, but it buys that at the cost of a hardcoded constant in a shared
column plus a deferred cleanup, and the `coalesce` edit is smaller than the
constant's explanatory comment.

Cambium's `test_score_complete` is 100 percent NULL in both files, and
`union_relations` null-fills absent columns, so **some** deliberate handling is
mandatory: left alone, every Cambium NJGPA score silently drops out of
graduation-pathway determination.

**Evidence that the predicate is already a no-op:** `testscorecomplete` is `1`
on every row of both regions' Pearson staging tables — 3,081 Newark, 1,049
Camden, no other value and no nulls. The staging filter
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

**Alternative A — retire the predicate entirely.** Drop
`n.testscorecomplete = 1` rather than coalescing it. Provably a no-op for all
4,130 existing rows. Rejected only because `coalesce` keeps the intent legible
at the call site: a future vendor that genuinely reports incompleteness would
still be filtered, where a deleted predicate would admit it silently.

**Alternative B — synthesize `1 as testscorecomplete`** in the alignment model.
Touches no existing model, which is why it was chosen first. Rejected on review:
it puts a hardcoded constant in a column documented as vendor-reported, and
leaves a cleanup for later.

**Alternative C — derive it**, as `if(test_status = 'completed', 1, 0)`.
Post-filter it evaluates to 1 for every row, so it is alternative B with extra
indirection.

**Consequence for the shared stream:** `testscorecomplete` is now genuinely NULL
for Cambium rows, so the description on
`int_pearson__all_assessments.testscorecomplete` ("Score completeness indicator
as reported by Pearson") must be updated in the same change — a constant or a
null is only defensible if it is discoverable where an analyst reads the column.

### D3 — `test_grade` is `11`, keyed on `test_code` rather than a bare constant

**Chosen.** Neither Cambium field reproduces Pearson's behavior, so the value
has to be asserted. It is written as a `case` over `test_code` rather than a
literal:

```sql
case test_code when 'ELAGP' then 11 when 'MATGP' then 11 end as test_grade,
```

Same value for both codes that exist, but self-documenting, and it yields NULL
rather than a confidently wrong `11` if NJ ever adds a graduation-proficiency
test code at another grade.

Pearson's `assessmentgrade` is `Grade 11` on all 4,130 post-filter rows, every
administration and both regions, while the _student's_ grade
(`gradelevelwhenassessed`) is 12 for fall retakers. The table below is computed
over the **unfiltered** `src_pearson__njgpa` external (`gradelevelwhenassessed`
is not carried into `stg_pearson__njgpa`), so its rows total 4,269 rather than
4,130 — the difference is the not-attempted rows the staging filter removes. The
conclusion is unaffected: `assessmentgrade = 'Grade 11'` and `test_grade = 11`
on all 4,130 filtered rows, no other value and no nulls.

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

**Asserting 11 also prevents nondeterminism.** `dim_assessments` dedups with
`partition_by="assessment_type, source_assessment_id, module_code, test_type"`
and `order_by="title"`, and `title` is the constant `'NJGPA'`. Had Cambium
emitted grade 10 for ELA, the ELAGP row would have had two tied candidate grade
levels with no tiebreaker, and `grade_level_tested` could have flipped between
builds.

Note that `grade_level` is **not** in that dedup partition, so the NJGPA row
count in `dim_assessments` is 2 either way — a row-count check cannot detect
this failure. The verification plan asserts `grade_level_tested = 11` on both
`state_nj_njgpa` rows instead.

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
holds Spring 2025 (FY25) while `pcfbk25` holds Fall 2025 (FY26). Naming the new
dimension for what it literally is — the number in the filename — avoids
encoding a wrong assumption.

**What `2026` means is genuinely unknown from one Spring file**, and an earlier
draft over-claimed here. `2026_Spring` is equally consistent with "calendar year
of the administration" (under which Fall 2026 ships as `2026_Fall`) and with
"ending year of school year 2025-26" (under which it ships as `2027_Fall`). The
partition list is robust to both: for an administration in fiscal year _F_, the
calendar year is at most _F_ and the school-year-end year is exactly _F_, so
`range(2026, F + 1)` covers either reading. Both `2026_Fall` and `2027_Fall` are
valid keys today.

Academic year still comes from the file's own `assessment_year` field, exactly
as Pearson does. The partition is a file-addressing scheme, never a semantic.

Residual, inherited rather than introduced: `CURRENT_FISCAL_YEAR` is captured at
module load, so a code location not redeployed between July 1 and a fall drop
would be one year short. `pearson/assets.py` carries the identical exposure.

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

**An earlier draft called this failure "contained, loud, and a one-line fix."
Two of those three were wrong**, and the correction changes the design.

Verified in the installed Dagster source and reproduced directly: the partition
key is validated inside `resolve_run_requests`, which processes **every** run
request for the tick in a single pass, so one bad key raises before
`SensorExecutionData` is returned and the **whole tick fails**. On
`TickStatus.FAILURE`, `_daemon/sensor.py` skips the cursor write
(`_should_update_cursor_on_failure` defaults to `False`), so the cursor never
advances, the offending file is re-listed on the next tick, and the failure
repeats indefinitely. Reproduced:

```text
declared keys: ['Spring|2026', 'Spring|2027', 'Fall|2026', 'Fall|2027']
  Spring     has_partition_key=True
  Fall       has_partition_key=True
  FALL       has_partition_key=False
  FallBlock  has_partition_key=False
```

Practical effect: an unrecognized season token stalls **all six Couchdrop assets
in that region** — Pearson NJGPA, NJSLA, NJSLA Science, student list report,
student test update, and the Finalsite status report — until someone redeploys.
Loud, yes; contained, no.

Declaring `["Spring"]` alone is therefore **strictly worse**, not an equivalent
alternative: it guarantees the stall on the first fall file whatever the token
is, where `["Spring", "Fall"]` at least avoids it if the token is exactly
`Fall`.

**Design: derive the regex alternation and the partition list from one list.**

```python
ADMINISTRATIONS = ["Spring", "Fall", "FALL", "FallBlock"]
# regex:      rf"(?P<administration>{'|'.join(sorted(ADMINISTRATIONS, key=len, reverse=True))})"
# partitions: StaticPartitionsDefinition(ADMINISTRATIONS)
```

The two cannot drift, because they are the same list. A known token matches and
partitions cleanly; an unknown token **fails to match at all**, so no run
request is built, no tick fails, and every other asset on the sensor keeps
running. The cost is a few never-materialized partitions, which is free.

Verified end to end rather than assumed: the alternation survives
`regex_pattern_replace` (its group-body character class admits `|`),
`compose_regex` substitutes the partition value back and the asset re-finds the
real file, and `Winter` / `Autumn` correctly do not match. The
`sorted(..., key=len, reverse=True)` matters — plain list order puts `Fall`
ahead of `FallBlock`, which then matches only by backtracking.

The residual exposure is a genuinely novel token: the file is skipped silently
rather than stalling the region. That is detected by the asset simply not
materializing for an administration — which the fall-administration checklist
below makes an explicit step — and it is a far better failure than a region-wide
ingestion outage.

Downstream, `administration_period` normalizes case-insensitively so `FALL`,
`Fall`, and `FallBlock` all collapse to `Fall`; see _Alignment and union_ above.

Worth confirming the token with NJDOE ahead of the fall administration; no
longer a reason to block, because no plausible token now stalls the sensor.

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

**`assessmentgrade` gains a second value.** Pearson sent `Grade 11` on all 4,130
rows — one distinct value. Cambium sends `Grade 10` on every ELAGP row and
`Grade 11` on every MATGP row. D3 correctly refuses to derive `test_grade` from
it, but the raw column still flows into the shared stream, so
`int_pearson__all_assessments.assessmentgrade`'s description ("Assessment grade
level as reported by Pearson") becomes wrong for 407 rows and must be updated in
the same change. No metric breaks — the only reader is
`rpt_tableau__academic_goals_rollup`, whose predicate
(`assessmentgrade = 'Grade 8' and subject like 'Algebra%'`) cannot match NJGPA.

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

**Test mode.** `testmode` (not `test_mode` — that column does not exist) is `O`
(online) on every row, and no paper attempt date field exists in the new layout.

**Unit timestamps are ELA-only — `test_date` cannot derive from them alone.**
This is the single most consequential difference from Pearson and an earlier
draft of this spec got it wrong, describing it as "units 3 and 4 are null."
Measured on the post-filter survivors:

| File          | Test code | Rows | Rows with any unit online start | Rows with `assessmentsessionactualstartdatetime` |
| ------------- | --------- | ---- | ------------------------------- | ------------------------------------------------ |
| Newark (7325) | ELAGP     | 282  | 282                             | 282                                              |
| Newark (7325) | MATGP     | 282  | **0**                           | 282                                              |
| Camden (1799) | ELAGP     | 125  | 125                             | 125                                              |
| Camden (1799) | MATGP     | 124  | **0**                           | 124                                              |

Units 3 and 4 are null everywhere, but units 1 and 2 are null for **every
Mathematics row**. Deriving `test_date` from the unit timestamps alone yields
NULL on 406 of 813 rows — and that is a silent, total data loss downstream, not
a cosmetic gap:

1. `int_assessments__resolved_section_enrollments` filters
   `where test_date is not null and localstudentidentifier is not null`.
1. `fct_assessment_scores_enrollment_scoped` **inner joins** that model.
1. So no Cambium Mathematics score would ever reach the fact, Cube, or any
   fact-backed dashboard.

Nothing would fail. `int_pearson__all_assessments` still gains its 813 rows, the
uniqueness test still holds, and `dim_assessment_administrations` still creates
the MATGP administration so the FK reports zero orphans. For contrast, Pearson
has 0 of 4,130 null `test_date`.

**The fallback, verified in BigQuery rather than assumed.**
`assessmentsessionactualstartdatetime` is populated on 813 of 813 survivors in
format `MMDDYYYYHHMM`. `safe_cast('031720261030' as timestamp)` returns NULL, so
a plain cast cannot read it;
`date(safe.parse_datetime('%m%d%Y%H%M', '031720261030'))` returns `2026-03-17`.
So `test_date` mirrors Pearson's `coalesce(online, fallback)` shape:

```sql
coalesce(
    date(earliest_test_start_timestamp), date(session_start_datetime)
) as test_date,
```

Unit start wins where both exist, which preserves current ELA behavior exactly
and only fills Math. The two sources agree on the calendar date for all 407 rows
where both exist, so the coalesce order has no observable effect on today's
data; unit-start-first is kept because it matches the Pearson model and is the
more precise source.

`test_date` carries a `not_null` test, and the verification plan asserts
non-null **per `test_code`**, never in aggregate: an aggregate check passes at
50% null.

## Rollout sequence

Order matters. A brand-new external source cannot be staged until its asset has
materialized at least once, because AVRO autodetect needs at least one file.

1. **Ops** — create the two Couchdrop folders and drop each region's file into
   its own folder.
1. **Merge-blocked code** — all of the above, on this branch.
1. **Pre-merge** — open the PR non-draft so the branch deployment builds,
   materialize both assets there, then stage the externals against the test
   bucket with a `cloud_storage_uri_base` override of
   `gs://teamster-test/dagster/<project>` and `ext_full_refresh: true`.
1. **Pre-merge, and easy to miss** — build the district staging models into the
   `zz_stg_*` schemas that dbt Cloud CI actually reads:

   ```bash
   uv run dbt build --select stg_cambium__njgpa \
     --project-dir src/dbt/kippnewark --target staging
   uv run dbt build --select stg_cambium__njgpa \
     --project-dir src/dbt/kippcamden --target staging
   ```

   Staging the **externals** is not sufficient. The kipptaf source points at a
   district **model** (`zz_stg_<region>_cambium.stg_cambium__njgpa`), which does
   not exist until it is built. `kipptaf/CLAUDE.md` → _Single-PR cross-project
   workflow_ is explicit that a district model modified in the PR needs a
   `--target staging` build, and `dbt clone` cannot substitute here at all —
   there is no prod relation to clone from for a brand-new model.

   Without this step CI fails deterministically: `dbt_utils.union_relations`
   calls `get_columns_in_relation` on a missing relation, yields an empty column
   superset, and the outer select fails `Name asian not found` — or
   `int_pearson__all_assessments` raises `There were no columns found to union`.
   Loud, but avoidable.

   Also seed `zz_stg_kipptaf` itself — under `--target staging` kipptaf reads
   its own models from there.

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
1. **`test_date` is non-null per `test_code`**, not in aggregate — `count(*)`
   and `countif(test_date is null)` grouped by `test_code`, expecting zero nulls
   for both ELAGP and MATGP. An aggregate check passes at 50 percent null, which
   is exactly the failure mode this guards.
1. **`fct_assessment_scores_enrollment_scoped` carries both subjects** — count
   Cambium Spring 2026 rows grouped by `module_code`, expecting ELAGP and MATGP
   in comparable numbers. The fact is where the `test_date` failure would have
   surfaced, and only here.
1. `dim_assessments` — assert `grade_level_tested = 11` on both
   `type = 'state_nj_njgpa'` rows. **Not** a row-count check: `grade_level` is
   absent from the dedup partition, so the count stays at 2 whether or not D3
   was applied, and a row-count check cannot detect the failure it was meant to
   catch.
1. `test_grade` is 11 on every Cambium row.
1. `int_students__graduation_path_codes` returns NJGPA rows for Cambium
   students. Confirms the D2 `coalesce` worked.
1. **Column-name checks on the union must run `--target staging`.** A dev-target
   compile of a union wrapper expands to nothing and still compiles clean
   (`src/dbt/CLAUDE.md` → _Validating a NEW union wrapper locally_), so a
   dev-target grep is vacuous and reads as a pass. Run after the district
   `--target staging` builds in the rollout, and check the passthrough columns
   (`asian`, `academic_year`, `` `period` ``, `` `subject` ``, `test_date`,
   `white`) as well as the aliased ones — the passthroughs are precisely the
   ones that depend on the union expansion.
1. **`int_topline__state_assessments_weekly` changes** — this is expected, not a
   regression, but it must be looked at. That model joins
   `int_pearson__all_assessments` with no assessment filter, hardcodes
   `'Spring' as test_round`, and is scoped to `academic_year >= 2025`. AY2025
   currently holds only 304 NJGPA Fall rows and zero NJSLA rows, so NJ
   11th-grade topline state proficiency is empty today and becomes NJGPA-driven.
   Fan-out is not a risk: every AY2025 Pearson NJGPA row is
   `gradelevelwhenassessed = 12` while every Cambium row is grade 11, so no
   student appears in both.
1. `test_incorrect_student_number_pearson` singular test — expect a small number
   of failures for the students with no local identifier, resolved by the
   crosswalk step. It inherits `severity: warn`, so it will not break the build.
1. `localstudentidentifier` join rate against `stg_powerschool__students` per
   region, as a coverage check.
1. `trunk check --force` on every changed file.

## Deferred work

1. **Rename the NJ state assessment stream** away from
   `int_pearson__all_assessments` to something vendor-neutral (D1, alternative
   C). The Pearson-named student crosswalk sheet
   (`stg_google_sheets__pearson__student_crosswalk`) belongs in the same rename
   — Ops will be adding Cambium UUIDs to a sheet named for the previous vendor.
1. **NJSLA and NJSLA Science on Cambium**, once those files are seen.

## Risks

| Risk                                             | Mitigation                                                                                                                                                                                                                                                  |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fall season token differs from `Fall`            | Regex and partition list derive from one shared list, so an unknown token is skipped rather than stalling the region's whole sensor (D8)                                                                                                                    |
| Filename pattern changes between administrations | Regex is the contract; confirm with NJDOE before the next administration                                                                                                                                                                                    |
| Cambium adds a column mid-year                   | Avro check warns on drift; declare the field in the Pydantic model. **Then re-encode**: old and new schema files coexist and a mixed scan drops the new field for the whole scan — only `scripts/reencode_avro_partitions.py` fixes it, not a cache refresh |
| Cambium **removes or renames** a column          | Nothing detects this today — see below. Mitigated by a non-empty assertion on `stg_cambium__njgpa`                                                                                                                                                          |
| `period` arrives as `FALL` rather than `Fall`    | `administration_period` normalizes case-insensitively and carries `accepted_values`, so a novel value fails rather than forking the Fall series                                                                                                             |
| `dim_assessments` grade level flips              | Prevented by D3; the verification plan asserts `grade_level_tested = 11`, not a row count                                                                                                                                                                   |
| Both districts' files land in one folder         | Asset raises on multiple matches rather than ingesting the wrong district                                                                                                                                                                                   |

**The removed-or-renamed-column risk deserves expanding, because it is the exact
class of change that created this project and nothing in the pipeline catches
it.** `check_avro_schema_valid` computes
`extras = record_fields - schema_fields` and warns only on **extras**; a missing
key produces no extras, and every generated field defaults to null, so fastavro
writes null silently and the check passes clean.

Concretely: if Cambium renames `Summative Flag`, then `summative_flag` becomes
all-NULL, the staging filter returns **zero rows**, `union_relations` tolerates
an empty relation, and `unique` / `not_null` on `student_test_uuid` both pass
vacuously on zero rows. NJGPA disappears from graduation-pathway determination
with no failing test anywhere. Adding `not_null` to more columns does not help —
a zero-row model passes those too. The fix is an explicit non-empty assertion as
a singular test in `src/dbt/cambium/tests/`.
