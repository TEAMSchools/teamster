# PR Batch C — locations & regions design

Closes #3720, #3689, #3690.

Single PR consolidating canonical location data, fixing FK coverage gaps across
six marts, unifying address attributes onto `dim_locations`, and adding a
business-unit FK from organizational units to `dim_regions`.

## Background

Three Batch C issues all touch `dim_locations` / `dim_regions`:

- **#3720** — `dim_locations` FK coverage gap across 6 marts (~309K orphans).
- **#3689** — unify address columns onto `dim_locations`; add `location_key` FK
  on `dim_work_assignment_locations`; remove 8 denormalized address cols.
- **#3690** — add `business_unit_code` to `dim_regions` for staff→region FK
  parity.

The 309K orphan rows resolve to **at most 59 distinct upstream identities**
across six source systems. The fix is mapping new upstream identifiers to the
existing 38 canonical locations — not adding canonical rows.

## Orphan landscape

| Child model                      | Source                             | Orphan rows |        Distinct codes | Fix                         |
| -------------------------------- | ---------------------------------- | ----------: | --------------------: | --------------------------- |
| `fct_support_tickets`            | Zendesk                            |     285,336 |                    45 | New canonical-master column |
| `dim_student_enrollments`        | PowerSchool sentinel               |      22,565 | 1 (`schoolid=999999`) | NULL FK on sentinel         |
| `dim_staffing_positions`         | Seat Tracker (ADP location string) |         823 |                     8 | New canonical-master column |
| `fct_job_candidate_applications` | SmartRecruiters                    |         364 |                     3 | New canonical-master column |
| `fct_staff_observations`         | SchoolMint Grow                    |          27 |                     1 | New canonical-master column |
| `dim_course_sections`            | PowerSchool sentinel               |           8 | 1 (`schoolid=999999`) | NULL FK on sentinel         |

PowerSchool `schoolid=999999` is the "Graduated/Exited" sentinel — semantically
not a physical location. The canonical master has no row with
`powerschool_school_id=999999`, so the LEFT JOIN from `stg_powerschool__schools`
to the master produces `NULL location_key` for sentinel rows naturally — no
magic-number check needed.

## Architecture

### Source topology

Today, two Google Sheets feed location data:

- `src_google_sheets__people__location_crosswalk` (alias grain — multiple `name`
  rows per `clean_name`, carries canonical attrs duplicated on every alias).
- `src_google_sheets__people__campus_crosswalk` (campus rollup).

The alias-grain sheet's `clean_name` rows duplicate canonical attributes on
every alias, and there is no schema home for cross-system identifiers (ADP
location code, SmartRecruiters location ID, SchoolMint Grow location ID, Zendesk
inbound field) or addresses.

This refactor introduces a canonical-grain master sheet. Final topology:

```text
src_google_sheets__people__locations  (NEW — canonical grain, 38 rows)
  → stg_google_sheets__people__locations  (renamed from stg_people__locations)
       ├──→ dim_locations  (applies Pathways/Whittier mart-scope filter here)
       ├──→ int_people__location_crosswalk  (joins canonical attrs onto aliases)
       └──→ 6 child mart models  (FK resolution)

src_google_sheets__people__location_crosswalk  (existing — TRIMMED to alias grain only)
  → stg_google_sheets__people__location_crosswalk
       └──→ int_people__location_crosswalk

src_google_sheets__people__campus_crosswalk  (existing — unchanged)
  → stg_google_sheets__people__campus_crosswalk
       └──→ (no longer joined by stg_google_sheets__people__locations;
             retained for any independent consumers)
```

### New canonical master sheet

`src_google_sheets__people__locations` — 1 row per canonical location (38 rows,
matching today's `dim_locations`). Owned by Ops.

Carries every canonical-grain attribute that today's `stg_people__locations`
exposes, plus the new structural columns:

**Existing canonical attrs** (migrated from the alias sheet): `location_name`
(canonical; matches the alias sheet's `clean_name` join key), `abbreviation`,
`region`, `business_unit`, `grade_band`, `powerschool_school_id`,
`deanslist_school_id`, `reporting_school_id`, `is_campus`, `is_pathways`,
`dagster_code_location`, `head_of_schools_employee_number`, `campus_name`.

> Naming note: the **alias sheet** uses `name` for the alias and `clean_name`
> for the canonical join key. The **new canonical master** uses `location_name`
> for the canonical name (no separate alias column — aliases stay on the alias
> sheet). The staging model `stg_google_sheets__people__locations` continues
> exposing the canonical column as `location_name` so existing consumers
> (`dim_locations`, `dim_student_enrollments`) need no rename.

**New columns — addresses** (#3689):

- `address_line_one`, `address_line_two`, `city`, `postal_code` — nullable
  (campus-rollup rows have no street address).

**New columns — inbound IDs** (resolve `location_key` FKs on facts):

- `adp_location_code` — ADP work-location code(s). Multi-valued where one
  canonical row corresponds to multiple ADP location strings (e.g. `Room 9` ←
  `Room 9 - 60 Park Pl`). Comma-separated in the sheet; unnested in the staging
  model.
- `smartrecruiters_location_id` — stable native ID.
- `schoolmint_grow_location_id` — stable native ID.
- `zendesk_<inbound_field>` — TBD at implementation time (verify which Zendesk
  ticket field carries the location join key — likely `organization_id`).

`coupa_address_name` and other 1:1 outbound mappings are explicitly **out of
scope** (see "Out of scope" below).

### Staging-layer changes

**Rename**: `stg_people__locations` → `stg_google_sheets__people__locations`.
Matches the `stg_google_sheets__<area>__<table>` convention; the model _is_ the
staging layer for the new sheet, so the legacy non-namespaced name no longer
applies.

**Behavior changes**:

- Source flips from `src_google_sheets__people__location_crosswalk` to
  `src_google_sheets__people__locations` — direct read from canonical-grain
  master.
- Drops the alias-dedup CTE (`dbt_utils.deduplicate`) — input is already
  canonical.
- Drops the LEFT JOIN to `src_google_sheets__people__campus_crosswalk` —
  `campus_name` is a column on the new master.
- Drops the Pathways/Whittier filter — moved to `dim_locations` (mart-scope
  filter belongs at the mart layer; staging carries all 38 rows so
  `int_people__location_crosswalk` resolves Pathways/Whittier aliases).
- Unnests multi-valued `adp_location_code` so each ADP string maps to exactly
  one canonical row.

### `int_people__location_crosswalk` rewrite

Output shape unchanged — alias-grain, same column list. Internal source flips:
canonical attrs come from `stg_google_sheets__people__locations` instead of
`stg_google_sheets__people__location_crosswalk`. Existing consumers untouched.

```sql
select
    lc.name as location_name,
    pl.location_name as location_clean_name,
    pl.abbreviation as location_abbreviation,
    pl.grade_band as location_grade_band,
    pl.region as location_region,
    pl.powerschool_school_id as location_powerschool_school_id,
    pl.deanslist_school_id as location_deanslist_school_id,
    pl.reporting_school_id as location_reporting_school_id,
    pl.is_campus as location_is_campus,
    pl.is_pathways as location_is_pathways,
    pl.dagster_code_location as location_dagster_code_location,
    pl.head_of_schools_employee_number
        as location_head_of_schools_employee_number,
    pl.campus_name,
from {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
inner join {{ ref("stg_google_sheets__people__locations") }} as pl
    on lc.clean_name = pl.name
```

### Alias sheet trimming

`src_google_sheets__people__location_crosswalk` retains only `name` (alias) and
`clean_name` (canonical join key). Ops removes the now-duplicated canonical
attribute columns (`abbreviation`, `grade_band`, `region`,
`powerschool_school_id`, `deanslist_school_id`, `reporting_school_id`,
`is_campus`, `is_pathways`, `dagster_code_location`,
`head_of_schools_employee_number`) after the new master is populated and the PR
is queued.

### Mart changes

**`dim_locations`**: same 38 rows, same `location_key = MD5(name)` (no hash
change — pure structural ADD per the column-naming audit's hash-change rules).
New columns: `address_line_one`, `address_line_two`, `city`, `postal_code`.
Mart-scope filter (`is_pathways = false AND name <> 'KIPP Whittier Elementary'`)
moves into this model.

**`dim_regions`**: adds `business_unit_code` (`STRING NOT NULL`, unique). 1:1
with the 5 existing regions. Values from ADP's canonical taxonomy: `KCNA`,
`KIPP_MIAMI`, `KIPP_TAF`, `KPAT`, `TEAM`.

**`dim_work_assignment_locations`**: adds `location_key` FK (resolved via the
new `adp_location_code` column on the canonical master). Drops 8 denormalized
columns (R9): `location_code`, `location_name`, `address_line_one`,
`address_line_two`, `city_name`, `postal_code`, `country_code`, `state_code`.

**SCD2 boundary normalization**. The model is a SQL transform (not a dbt
snapshot) that recomputes SCD2 boundaries from scratch each run via an
`attribute_hash` + `LAG` window over
`int_adp_workforce_now__workers__work_assignments`. Today's hash inputs include
5 address columns:

```text
home_work_location__name_code__code_value
home_work_location__address__line_one
home_work_location__address__city_name
home_work_location__address__postal_code
home_work_location__address__country_subdivision_level_1__code_value
```

Pure address mutations on the same `code_value` cut redundant boundaries on
every work-assignment SCD2 row at that location, even though the work-assignment
didn't change. Reducing `attribute_hash` inputs to `[location_key]` only —
resolved via the new crosswalk on `home_work_location__name_code__code_value` —
collapses these redundant boundaries automatically on the next run. No backfill
job required.

**Hash-change implication for `work_assignment_location_key`** (=
`MD5(item_id, effective_date_start)`): retained boundary rows keep their key;
collapsed redundant rows simply drop out of the dim. Pre-merge validation: for
each downstream consumer FKing to `work_assignment_location_key`, confirm the FK
set is a subset of the post- collapse key set (no orphans introduced by
collapse). Recorded in PR description.

**`dim_work_assignment_organizational_units`**: `business_unit_code` becomes an
FK to `dim_regions.business_unit_code`. Add relationships test.

### Source-system enrichment (no new intermediates)

`location_key` resolution attaches to each source system's existing natural
pivot point — the model that already serves as the join target for downstream
consumers — rather than creating new intermediates. This stays consistent with
the long-term direction of deconstructing wide denormalized marts into thin
star-schema facts that traverse FK chains for dimensional context.

| Source             | Pivot point (existing model)                | Resolution input                          |
| ------------------ | ------------------------------------------- | ----------------------------------------- |
| PowerSchool        | `stg_powerschool__schools`                  | `powerschool_school_id`                   |
| Zendesk            | `int_zendesk__tickets__custom_fields_pivot` | `zendesk_<inbound>` on master             |
| Seat Tracker (ADP) | `int_seat_tracker__snapshot`                | `adp_location_code` (multi-valued unnest) |
| SchoolMint Grow    | `int_schoolmint_grow__observations`         | `schoolmint_grow_location_id`             |
| SmartRecruiters    | _no upstream pivot — resolve at mart_       | `smartrecruiters_location_id`             |

Each pivot model gains a `location_key` column resolved by joining the canonical
master (`stg_google_sheets__people__locations`) on the source-specific
identifier. Where the source row has no resolvable location (PowerSchool
`schoolid=999999` "Graduated Students", unmapped upstream code), the LEFT JOIN
naturally produces `NULL location_key` — no magic-number check needed. The
relationship test on the consuming mart passes against the nullable FK pattern.

PowerSchool gets enrichment at the kipptaf-level staging layer
(`stg_powerschool__schools`) because the existing model is already the natural
join target for downstream marts (`dim_student_enrollments`,
`dim_course_sections`, and any future PS-derived fact). Mixing a
Google-Sheets-sourced column into a staging model is unusual but consistent with
kipptaf-staging's role as the project-level source-cleanup boundary.

Today `stg_powerschool__schools` is a bare `dbt_utils.union_relations(...)` call
— extending it in-place requires wrapping the union in a CTE so the
canonical-master join can sit downstream:

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__schools"),
                    source("kippcamden_powerschool", "stg_powerschool__schools"),
                    source("kippmiami_powerschool", "stg_powerschool__schools"),
                    source("kipppaterson_powerschool", "stg_powerschool__schools"),
                ]
            )
        }}
    )

select u.*, loc.location_key,
from unioned as u
left join {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_number = loc.powerschool_school_id
```

The existing `dbt_union_relations_automation_condition()` staleness handling
continues to apply — wrapping the union in a CTE doesn't change recompilation
triggers.

SmartRecruiters has a single consumer (`fct_job_candidate_applications`), no
upstream intermediate, and no upstream "locations" table — creating an
intermediate for one mart is over-engineering, so the mart joins the canonical
master directly.

### Mart child changes (consumes resolved `location_key`)

The six child models from #3720 stop joining the canonical master directly
(except SmartRecruiters). Each picks up `location_key` via its existing join to
the source pivot point:

- `fct_support_tickets` ← `int_zendesk__tickets__custom_fields_pivot`
- `dim_student_enrollments`, `dim_course_sections` ← `stg_powerschool__schools`
- `dim_staffing_positions` ← `int_seat_tracker__snapshot`
- `fct_staff_observations` ← `int_schoolmint_grow__observations`
- `fct_job_candidate_applications` — direct join to canonical master

## PR sequencing

Single PR, seven staged commits in dependency order:

1. **Sheet bootstrap** (Ops, off-PR). Ops creates and populates
   `src_google_sheets__people__locations` with all 38 canonical rows × all
   columns (existing attrs migrated + new addresses + new inbound IDs). Verified
   out-of-band before code review starts.
2. **Source registration + new staging model + rename**. Register the new sheet
   in `models/google/sheets/sources-external.yml`. Rename
   `stg_people__locations` → `stg_google_sheets__people__locations` and rewrite
   to source from the new master directly (drop dedup, drop campus_crosswalk
   join, drop mart-scope filter, unnest `adp_location_code`). Update all `ref()`
   callers to the new name.
3. **Move Pathways/Whittier filter** into `dim_locations`. Add
   `address_line_one/two`, `city`, `postal_code` columns to `dim_locations`.
4. **Refactor `int_people__location_crosswalk`** to source canonical attrs from
   `stg_google_sheets__people__locations`. Output shape unchanged.
5. **Alias sheet trim** (Ops, off-PR). Ops removes duplicated canonical-attr
   columns from `src_google_sheets__people__location_crosswalk`. Coordinated
   with the source YAML update for the trimmed schema.
6. **Source-system enrichment**. Extend four existing pivot models —
   `stg_powerschool__schools`, `int_zendesk__tickets__custom_fields_pivot`,
   `int_seat_tracker__snapshot`, `int_schoolmint_grow__observations` — to attach
   `location_key` from the canonical master. The PowerSchool `schoolid=999999`
   "Graduated Students" sentinel resolves to `NULL` via the LEFT JOIN (no row on
   master); Seat Tracker uses multi-valued unnest on `adp_location_code`.
7. **Mart child fixes**. Six child mart models swap their `location_key` source
   to the source-system pivot point (or join the canonical master directly for
   SmartRecruiters). `business_unit_code` on `dim_regions`; `business_unit_code`
   FK from `dim_work_assignment_organizational_units`; `location_key` FK + R9 +
   `attribute_hash` reduction on `dim_work_assignment_locations`.

## Testing

- Existing relationships tests on the six #3720 child models flip from failing
  to passing (~309K orphans resolved).
- New relationships test:
  `dim_work_assignment_organizational_units.business_unit_code → dim_regions.business_unit_code`.
- New uniqueness test: `dim_regions.business_unit_code` (single-column).
- New uniqueness test: `stg_google_sheets__people__locations.location_name`
  (single-column — replaces the alias-grain composite uniqueness check).
- New custom drift test: every distinct `clean_name` in
  `src_google_sheets__people__location_crosswalk` exists as `location_name` in
  `src_google_sheets__people__locations` (and vice versa). Fails CI if Ops adds
  a row to one without the other.
- Pre/post SCD2 row count check on `dim_work_assignment_locations` (manual,
  recorded in PR description).

## Hash-change discipline

Per `src/dbt/CLAUDE.md` enumerated surrogate-key change rules:

- `dim_locations.location_key`: **no change**. `MD5(location_name)` input
  preserved — the staging model continues exposing the canonical column as
  `location_name`.
- `dim_work_assignment_locations.location_key`: **structural add** (rule 5). New
  FK column on a model that didn't carry one. No hash on the model's PK changes.
- `dim_student_enrollments.location_key`, `dim_course_sections.location_key`:
  **null handling change** (rule 4). Previously the surrogate hash was generated
  from the joined `stg_people__locations.location_name` (returning the
  placeholder hash for sentinel rows). After the refactor, `location_key` flows
  through `stg_powerschool__schools` LEFT-joined to the canonical master,
  returning real `NULL` for the `999999` sentinel. Hash values on non-sentinel
  rows unchanged.
- `dim_regions.business_unit_code`: not a surrogate key — natural attribute.
- All other six child models updating `location_key` resolution: **values
  unify** (rule 1) where the resolution path changes from a now-missing upstream
  string to the canonical name on the master. Hash values change for
  previously-orphaned rows; non-orphan rows unchanged.

Add entries to the column-naming audit spec's "Enumerated surrogate-key changes"
table for items above flagged by rules 1, 4, or 5.

## Out of scope

- **Cube.js / Tableau migration off the 8 dropped denormalized columns** on
  `dim_work_assignment_locations` (#3689's downstream consumer impact).
  Coordinated separately by the Cube.js implementation.
- **Folding `coupa__address_name_crosswalk` into the new master** (it is the
  only other 1:1 outbound crosswalk with canonical location). Tangential to the
  three Batch C issues.
- **Per-source crosswalk sheets pivoting on extra dimensions** (Zendesk org
  lookup ×BU, Coupa Intacct lookup ×BU, Egencia traveler groups ×BU×dept×title,
  Coupa user exceptions per-user). Not 1:1 with location; not absorbable.
- **Adding canonical rows for any future locations**. Ops process; out of scope
  for this PR.

## Related

- Project board: <https://github.com/orgs/TEAMSchools/projects/4>
- Cube.js blast-radius umbrella: #3543
- Column-naming audit: #3643 /
  `docs/superpowers/specs/2026-04-15-column-naming-audit.md`
- Batch B (predecessor): #3742 (merged)
