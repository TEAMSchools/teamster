# Handling ADP Location Renames

`int_people__location_crosswalk` is the canonical resolver for all location-name
lookups. It maps raw ADP `home_work_location_name` values to clean reporting
names, absorbing historical aliases so downstream models stay stable even when
ADP changes its source values.

## Scenario 1: ADP changes the raw `home_work_location_name` value (most common)

ADP occasionally renames a location in its system without any real-world change
to the school or office. When that happens:

1. Open the `src_people__location_crosswalk` Google Sheet.
2. Add a **new alias row**: set `name` to the new ADP value, set `clean_name` to
   the unchanged existing clean name, and copy all other columns (region, school
   level, etc.) from the existing row for that location.
3. No downstream action is needed — `int_people__location_crosswalk` absorbs the
   rename via alias resolution. All models that join on `clean_name` are
   unaffected.

**Verification** — run the following query the next day to confirm
`home_work_location_reporting_name` is unchanged for affected staff:

```sql
select
    home_work_location_name,
    home_work_location_reporting_name,
    count(*),
from `teamster-332318.kipptaf_people.int_people__staff_roster`
where home_work_location_name = '<new ADP value>'
group by 1, 2
```

## Scenario 2: The clean/reporting name itself needs to change (rare)

When the school or office is actually renamed and the reporting name must change
everywhere:

1. Edit `clean_name` in `src_people__location_crosswalk`. Because all alias rows
   share the same `clean_name`, the update propagates atomically to every
   historical alias.
2. Edit the five downstream crosswalk sheets **in lockstep** — each one joins on
   the clean name:
   - `src_coupa__address_name_crosswalk` — update `location_clean_name`
   - `src_coupa__intacct_program_lookup` — update `location_clean_name`
   - `src_coupa__user_exceptions` — update `location_clean_name`
   - `src_egencia__traveler_groups_v2` — update `location_clean_name`
   - zendesk `org_lookup` — update `location_clean_name`
   - `src_people__campus_crosswalk` — update `Location_Name`
3. Audit any Tableau workbooks that filter on the string literal of the old
   clean name and update them.

**Verification** — confirm row-count parity on the affected extracts after the
next dbt run:

- `rpt_coupa__users`
- `rpt_egencia__users`
- `rpt_zendesk__users`
- `rpt_clever__staff`
- `rpt_clever__sections`
- `rpt_illuminate__roles`
- `rpt_tableau__ddi_dashboard`
- `rpt_tableau__staff_roster`
- `rpt_gsheets__pm_assignment_roster`

## What NOT to do

Never edit the raw ADP `name` column in `src_people__location_crosswalk` to
track a rename. Changing an existing `name` value rewrites history and breaks
joins against `int_people__staff_roster_history`, which retains the original ADP
string. Always **add a new alias row** instead.
