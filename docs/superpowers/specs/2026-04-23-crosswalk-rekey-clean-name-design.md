# Rekey downstream crosswalks on `location_clean_name`

**Issue**: [#3728](https://github.com/TEAMSchools/teamster/issues/3728)
**Date**: 2026-04-23

## Problem

Four Google Sheet crosswalks downstream of ADP are keyed on the raw
`home_work_location_name` value: coupa `address_name_crosswalk`, egencia
`traveler_groups`, zendesk `zendesk_org_lookup`, and (partially) people
`campus_crosswalk`. When ADP renames a physical location, every one of these
sheets must be updated in lockstep with `int_people__location_crosswalk`. The
failure mode is silent — missed sheets produce NULL joins or dropped rows with
no test signal.

`int_people__location_crosswalk` already absorbs raw-name changes via alias rows
(one row per ADP spelling, all pointing to the same `clean_name`). The
downstream crosswalks do not benefit from that indirection because they join on
the raw name directly.

## Goal

Rekey the four downstream crosswalks on `location_clean_name` so that raw ADP
name changes stop propagating past `int_people__location_crosswalk`. After this
change, a raw ADP rename is handled in exactly one place (the location crosswalk
sheet) via an alias row.

## Out of scope

- `int_people__location_crosswalk` itself (already canonical).
- Raw `home_work_location_name` display columns in Tableau/reporting extracts —
  these intentionally show the ADP value.
- The `'Room 11'` / `'%Room%'` hardcoded literals in
  `rpt_appsheet__seat_tracker_roster.sql` (separate pattern, follow-up).

## Design

### Join key choice

Use `location_clean_name` (string) as the join key. `reporting_school_id` would
be more stable but isn't universally populated; `clean_name` is human-readable
and already the canonical name exposed by `int_people__location_crosswalk`.
Accepted tradeoff: future `clean_name` edits still require a coordinated
multi-sheet update (runbook added — see Operational Guide section below).

### Source sheets

One row per logical school (already the structure; no dedup needed). All four
sheets get edited in-place at merge time:

| Sheet                               | Current key column             | New key column        |
| ----------------------------------- | ------------------------------ | --------------------- |
| `src_coupa__address_name_crosswalk` | `adp_home_work_location_name`  | `location_clean_name` |
| `src_egencia__traveler_groups`      | `adp_home_work_location_name`  | `location_clean_name` |
| zendesk `zendesk_org_lookup`        | `adp_location`                 | `location_clean_name` |
| `src_people__campus_crosswalk`      | `Name` (ADP-lookup usage only) | no sheet change       |

Sheet owners replace the raw ADP value in the renamed column with the clean name
from `int_people__location_crosswalk`.

For `campus_crosswalk`: the `Name` column is also used as a rollup key for other
consumers, so it is not renamed. Instead, the ADP-lookup consumers (clever,
illuminate, ddi_dashboard) switch their join column to `ccw.location_name`,
which already holds the clean name.

### Staging models

Three staging YAMLs and SQL files updated:

- `stg_google_sheets__coupa__address_name_crosswalk`
- `stg_google_sheets__egencia__traveler_groups`
- `stg_google_sheets__zendesk_org_lookup`
- `stg_google_sheets__people__campus_crosswalk` (no rename; test only)

Each gets:

1. Column renamed in staging SQL to reflect new semantics
   (`adp_home_work_location_name` → `location_clean_name` for coupa/egencia;
   `adp_location` → `location_clean_name` for zendesk).
2. `unique` test on the clean-name column — catches silent join fan-out, which
   no existing test covers.
3. `description` added to model and every column (project convention).

Zendesk's composite join (`adp_business_unit + adp_location`) becomes
(`adp_business_unit + location_clean_name`); the uniqueness test uses
`dbt_utils.unique_combination_of_columns` over that pair.

### Downstream extracts

Seven extract files change. All already source from `int_people__staff_roster` /
`_history` which carries `home_work_location_reporting_name`, so no new
`int_people__location_crosswalk` joins are introduced — only join-column swaps.

| File                                              | New join                                                          |
| ------------------------------------------------- | ----------------------------------------------------------------- |
| `extracts/coupa/rpt_coupa__users.sql`             | `sub.home_work_location_reporting_name = ipl.location_clean_name` |
| `extracts/egencia/rpt_egencia__users.sql`         | `sr.home_work_location_reporting_name = tg.location_clean_name`   |
| `extracts/zendesk/rpt_zendesk__users.sql`         | `sr.home_work_location_reporting_name = zol.location_clean_name`  |
| `extracts/clever/rpt_clever__staff.sql`           | `sr.home_work_location_reporting_name = ccw.location_name`        |
| `extracts/clever/rpt_clever__sections.sql`        | `sr.home_work_location_reporting_name = ccw.location_name`        |
| `extracts/illuminate/rpt_illuminate__roles.sql`   | `sr.home_work_location_reporting_name = cc.location_name`         |
| `extracts/tableau/rpt_tableau__ddi_dashboard.sql` | `r.home_work_location_reporting_name = cw.location_name`          |

#### Output column preservation

`rpt_` output columns are consumer contracts — no renames. In particular,
`rpt_zendesk__users.sql` emits `adp__home_work_location_name` as an output
column (line 94); that name is preserved even though the underlying value now
holds the clean name. The CTE that constructs it switches its source:

```sql
sr.home_work_location_reporting_name as adp__home_work_location_name,
```

## Rollout

Single PR, coordinated cutover. Ordering within the PR work:

1. Branch + dbt Cloud CI PR environment provisioned.
2. Update three staging YAMLs (rename columns, add `unique` tests, add
   descriptions).
3. Update staging SQL to select the renamed sheet columns.
4. Update the seven downstream extract SQL files.
5. Owners edit the four source sheets at merge time — values replaced with clean
   names in the renamed column.
6. Post-merge verification (see below).

Accept a brief window around merge where sheet values and SQL schema are briefly
inconsistent — affected models rebuild daily and none of the four crosswalks are
traffic-critical.

## Verification

Post-merge checks (dbt Cloud CI covers uniqueness automatically):

1. **Row-count parity**: compare row count on PR branch vs production for each
   of the seven extracts (`dbt_cloud_pr_<ci_id>_<pr_num>_*` schema vs prod). Any
   drop signals sheet entries missing a clean-name translation.
2. **NULL-join spot check**: `SELECT COUNT(*) WHERE <joined_column> IS NULL` on
   coupa/egencia/zendesk/clever output columns — expected NULLs should be at or
   below prod baseline.
3. **Uniqueness tests pass** — automatic via dbt build.
4. **Downstream system confirmation**: next-day check with sheet owners that
   coupa user sync, egencia traveler groups, zendesk user provisioning, and
   clever roster sync still produce expected deltas.

## Operational guide (new documentation)

New guide at `docs/guides/adp-location-renames.md`, added to MkDocs nav,
covering two scenarios:

### Scenario 1: ADP changes the raw `home_work_location_name` value (most common)

1. Open `src_people__location_crosswalk` (Google Sheet).
2. Add a new alias row: `name` = new ADP value, `clean_name` = unchanged
   existing clean name, other columns copied from the existing row.
3. No downstream action needed — `int_people__location_crosswalk` absorbs the
   change via alias resolution.
4. Verification: next-day query of `int_people__staff_roster` — affected staff's
   `home_work_location_reporting_name` unchanged, `home_work_location_name`
   shows the new ADP value.

### Scenario 2: Clean/reporting name itself needs to change (rare)

1. Edit `clean_name` in `src_people__location_crosswalk` (updates all aliases
   atomically).
2. Edit the four downstream crosswalks in lockstep: coupa
   `address_name_crosswalk`, egencia `traveler_groups`, zendesk
   `zendesk_org_lookup`, `campus_crosswalk` — update the value in the
   `location_clean_name` / `location_name` column in each.
3. Audit any Tableau workbooks filtering on the string value.
4. Verification: row-count parity check on the seven affected extracts.

### What NOT to do

Never edit the raw ADP name column (`name`) in `src_people__location_crosswalk`
to track renames — that breaks historical joins against
`int_people__staff_roster_history`. Always add an alias row instead.
