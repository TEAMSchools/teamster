# Cambium EOC score file ingestion — design

Issue: [#5481](https://github.com/TEAMSchools/teamster/issues/5481)

## Problem

New Jersey now ships the end-of-course (EOC) tests — Algebra I, Algebra II,
Geometry — in their own District Summative Record File, separate from NJSLA. The
Newark and Camden files sit in a new `eoc` folder under each region's Couchdrop
`cambium` folder. No asset matches them, so the Couchdrop sensor skips them
silently and `int_pearson__all_assessments` holds 0 EOC rows for `academic_year`
2025 (it held 384 Newark and 152 Camden rows in 2024).

Paterson has no EOC file this year and will next year.

## Decisions

- **Two Dagster assets, not one.** `build_sftp_file_asset` raises on more than
  one file per partition, and the NJSLA and EOC files share the `2026|Spring`
  key. One asset would need a third partition dimension, which re-keys the
  existing `njsla` asset in 3 regions and leaves old GCS files under the same
  external-table wildcard. A separate `eoc` asset adds without changing anything
  that works.
- **One staging model.** `stg_cambium__njsla` reads both sources. The headers
  are byte-identical, and Pearson-era EOC rows already lived in
  `stg_pearson__njsla`, so kipptaf needs no new union member or source entry.
- **`test_grade` and `assessmentgrade` are NULL for EOC rows**, matching every
  Pearson year back to 2015. `test_grade` is the grade of the test form, and
  `dim_assessments` puts it into the assessment key as `grade_level`. An EOC
  form has no grade; Cambium's `Grade 11` on every EOC row is not a real value.
  Filling it with the student's grade would split one Algebra I assessment into
  a row per student grade. This departs from the issue's "test_grade reflecting
  the real grade".
- **The student's grade travels separately** as `gradelevelwhenassessed`,
  carried through both union layers into kipptaf. On every non-EOC row in both
  vendors it equals `test_grade` (0 mismatches, Newark Cambium 2025 and Pearson
  2024), because NJ tests students on grade. It differs only on EOC rows.

## Design

### Dagster (Newark and Camden)

`src/teamster/code_locations/kipp{newark,camden}/cambium/assets.py` gain:

```python
eoc = build_sftp_file_asset(
    asset_key=[*key_prefix, "eoc"],
    remote_dir_regex=rf"{remote_dir_regex_prefix}/eoc",
    remote_file_regex=build_remote_file_regex(
        partitions_def=partitions_def,
        district_code=DISTRICT_CODE,
        filename_suffix_regex=r"_SLA_EOC",
    ),
    avro_schema=NJSLA_SCHEMA,
    ssh_resource_key=ssh_resource_key,
    partitions_def=partitions_def,
)
```

The asset is appended to `assets` and to each region's `couchdrop/sensors.py`
`asset_selection`. The existing `njsla` asset's `remote_dir_regex` ends in
`/njsla` and `re.match` anchors at the start, so it cannot match a file in
`/eoc`.

### cambium package

- `models/sources-external.yml`: add `src_cambium__eoc`, a copy of
  `src_cambium__njsla` with asset key `[project, cambium, eoc]` and the
  `cambium/eoc/` GCS prefix.
- `stg_cambium__njsla.sql`: the first CTE reads
  `dbt_utils.union_relations(relations)`, where `relations` is
  `src_cambium__njsla` plus `src_cambium__eoc` when
  `var("cambium_eoc_enabled", true)`. The CTE already enumerates its columns, so
  the union's `_dbt_source_relation` drops out and the contract is unchanged
  apart from the rename below. A `source()` in the unrendered branch never
  enters the graph, so a district with the var off parses without the source.
- In that first CTE, `assessment_grade` becomes NULL when `subject` is
  `Algebra I`, `Algebra II` or `Geometry`. `test_grade` then derives NULL
  through the existing `regexp_extract`.
- `discipline`: the three EOC subjects map to `Math`.
- `grade_level_when_assessed` is renamed `gradelevelwhenassessed` in
  `stg_cambium__njsla` and `stg_cambium__njgpa`, matching the Pearson column
  shape these models restate. No consumer reads the snake_case name.

Every other derived column already produces the Pearson-era EOC shape
(`subject_area`, `aligned_subject`, `module_code`, `aligned_test_code`,
`assessment_name = 'NJSLA'`, `assessment_type = 'state_nj_njsla'`, the
proficiency bands), verified against the 2024 Pearson rows.

### Paterson

`src/dbt/kipppaterson/dbt_project.yml` sets `cambium_eoc_enabled: false` and
disables `src_cambium__eoc` beside the existing `src_cambium__njgpa` disable.
Adding Paterson later is the asset, the sensor line, and removing those two
lines.

### Grade-when-assessed through the unions

Add `gradelevelwhenassessed` to the `include` list of the pearson package's
`int_pearson__all_assessments` and of kipptaf's `int_pearson__all_assessments`.
`stg_pearson__njsla`, `_njsla_science` and `_parcc` already cast it to int;
`stg_pearson__njgpa` lacks it and null-fills. `union_relations` null-fills a
listed column absent from a relation, so kipptaf compiles before the district
Pearson relations rebuild in prod.

### Tests (`stg_cambium__njsla.yml`)

- `subject` `accepted_values` gains the three EOC subjects.
- `test_grade` `not_null` is scoped with a `where` excluding the EOC subjects.
- `studenttestuuid` `unique` already spans both files, which also catches any
  future overlap between them.
- Descriptions updated for `subject`, `discipline`, `test_grade`,
  `assessmentgrade` and the renamed `gradelevelwhenassessed`, in both cambium
  properties files and both `int_pearson__all_assessments` properties files.

## Verification

1. `uv run pytest tests/libraries/test_cambium_assets.py` with the two `eoc`
   assets added to its `ASSETS` and `REGIONS` lists. The cross-feed test proves
   no feed's asset matches another feed's file.
2. `dbt parse` in kipppaterson with the var off.
3. Branch deployment: materialize the Newark and Camden `eoc` assets, stage
   `src_cambium__eoc` into `zz_stg` with the `gs://teamster-test` override (user
   authorization required), build `stg_cambium__njsla` in both districts.
4. Row checks: 382 Newark and 122 Camden EOC rows; EOC rows carry
   `discipline = 'Math'` and NULL `test_grade` / `assessmentgrade`; NJSLA row
   counts unchanged.
5. kipptaf dbt Cloud CI green.
6. Post-merge: launch the prod `eoc` assets immediately, before the first
   automation tick requests `stg_cambium__njsla` against an empty prefix.

## Out of scope

`rpt_tableau__academic_goals_rollup` filters
`not (assessmentgrade = 'Grade 8' and subject like 'Algebra%')`. With the NULL
`assessmentgrade` Pearson sent for EOC codes, and this design keeps, that
predicate is NULL and drops every Algebra row, not only 8th-grade Algebra. This
design preserves that behavior. Rewriting the filter on
`gradelevelwhenassessed = 8` changes dashboard output and belongs in a follow-up
issue for the dashboard owner.
