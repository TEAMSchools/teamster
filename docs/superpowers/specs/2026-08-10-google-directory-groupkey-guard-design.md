# Guard `groupKey` in the Google Directory student user import

Refs [#4766](https://github.com/TEAMSchools/teamster/issues/4766)

## Problem

`rpt_google_directory__users_import` builds the student group address by string
concatenation with nothing to validate it against:

```sql
'group-students-' || region || '@teamstudents.org' as `groupKey`,
```

`orgUnitPath`, three lines up in the same select, **is** validated: it joins
`stg_google_directory__orgunits` on the path, so a path missing from Google
resolves to null and the student drops out of the extract.
[#4513](https://github.com/TEAMSchools/teamster/issues/4513) added that guard
for org units and left the group address unguarded. There is nothing to join
against for groups — the `groups` asset is commented out in
`src/teamster/code_locations/kipptaf/google/directory/assets.py`, so no
`stg_google_directory__groups` model exists.

Paterson entered this extract on 2026-08-03 when 079381c63 removed it from the
exclusion list. `group-students-paterson@teamstudents.org` has never existed, so
Dagster run `bc28dc20-ae50-4af7-b45a-b3a0bd05d440` logged 429 identical
`404 Resource Not Found: groupKey` errors — one per created student — on the
`zero_api_errors` check for `kipptaf/google/directory/user_create`.

## Verified state

Checked against the current working tree and prod before designing:

| Claim                                                 | Status                                                        |
| ----------------------------------------------------- | ------------------------------------------------------------- |
| `groupKey` built by concatenation, no join            | Confirmed, `rpt_google_directory__users_import.sql` line 250  |
| `orgUnitPath` guarded by a join plus a `where` filter | Confirmed, same file, lines 216-218 and 260                   |
| `groups` asset commented out, nothing to join against | Confirmed, `assets.py` lines 289-303; no staging model exists |
| Group membership attempted only under `is_create`     | Confirmed, `assets.py` lines 201-218                          |
| Paterson student accounts exist with no group         | 884 accounts, 0 disabled (issue said 883; one added since)    |

The deployed BigQuery view definition confirms the concatenated literal is
`group-students-`, matching the issue.

## Decisions

- **Scope is the guard only.** The 884 stranded Paterson memberships and
  recurring membership reconciliation (issue scope items 1 and 3) stay open on
  #4766.
- **Validate against Google, not a spreadsheet.** Re-enabling the `groups` asset
  and joining it mirrors the `orgUnitPath` guard exactly, self-heals the moment
  Ops creates the group, and needs no per-school sheet coordination for a
  per-region value. The alternative — naming the group in the
  `people__locations` sheet and resolving it through
  `int_people__location_crosswalk` — validates the sheet rather than Google.
- **A missing group must not block provisioning.** Mirroring the `orgUnitPath`
  guard literally would drop the student from the extract, so no Paterson
  student would get an account until Ops creates the group. Today those accounts
  are created correctly and only the membership fails. The guard therefore skips
  the membership and keeps the account.
- **The missing group stays visible.** Skipping silently would leave students
  created group-less indefinitely with no alert, which is worse than the noisy
  status quo. One aggregated error keeps `zero_api_errors` firing.

## Prerequisite

Ops creates `group-students-paterson@teamstudents.org` in the Google admin
console. This is not a code change. Until it exists, Paterson accounts are
created without group membership and the run reports one warning.

## Design

### Re-enable the `groups` asset

- `src/teamster/code_locations/kipptaf/google/directory/schema.py` — uncomment
  `GROUPS_SCHEMA` and add `Group` to the import from
  `teamster.libraries.google.directory.schema`. `MEMBERS_SCHEMA` stays
  commented.
- `src/teamster/code_locations/kipptaf/google/directory/assets.py` — uncomment
  the `groups` asset and add it to the `assets` list. The `members` asset stays
  commented; it belongs to the deferred reconciliation work.
- `src/teamster/code_locations/kipptaf/google/directory/schedules.py` — add
  `groups` to `google_directory_nonpartitioned_asset_schedule`, where `orgunits`
  already sits.

`GoogleDirectoryResource.list_groups()` already exists and needs no change.

The groups snapshot runs at 1:30am and `user_sync` at 1:00am, so the guard reads
a snapshot up to a day old. `orgunits` already carries the identical lag, and
regional student groups change roughly once a year, so no re-ordering is
warranted.

### Expose it to dbt

- `src/dbt/kipptaf/models/google/directory/sources-external.yml` — add
  `src_google_directory__groups`, copied from the
  `src_google_directory__orgunits` block with the `google/directory/groups/*`
  location and the matching `dagster.asset_key` meta.
- `src/dbt/kipptaf/models/google/directory/staging/stg_google_directory__groups.sql`
  — a flat select over the source, following the column-renaming style of
  `stg_google_directory__users.sql` (`directmemberscount` becomes
  `direct_members_count`, `admincreated` becomes `admin_created`,
  `noneditablealiases` becomes `non_editable_aliases`; `email`, `id`, `name`,
  `description`, and `aliases` keep their names).
- Its properties yml declares every column with `data_type`, since the
  `staging/` directory default enforces contracts, plus `unique` and `not_null`
  on `email` at `severity: error` as the staging layer requires.

### Guard the join

In `rpt_google_directory__users_import.sql`, `with_google` derives the
constructed address as a named column and the existing `final` CTE joins on it:

```sql
with_google as (
    select
        ...
        'group-students-' || s.region || '@teamstudents.org' as group_key_target,
    ...
),

final as (
    select
        w.*,
        g.email as group_key,
        ...
    from with_google as w
    left join {{ ref("stg_google_directory__groups") }} as g
        on w.group_key_target = g.email
)
```

The address is derived one CTE upstream of the join rather than inline in the
`ON` clause for two reasons: the SQL guide forbids one-sided calculations in
join predicates, and BigQuery rejects a select-list alias referenced from the
same select's `ON` clause. Joining in `final` avoids adding a CTE, since
`with_google` already computes derived columns and `final` already reads from
it.

The outer select projects the resolved address as `groupKey`, null when the
group does not exist in Google — the same shape as `o.org_unit_path`.
`group_key_target` is not projected; it is join plumbing, and an unrecognized
extra field would ride along into the Google `users.insert` payload.

The final `where` clause does **not** change: the student stays in the extract
and still gets an account. The contract does not change either, since
nullability is not part of it. The projected `groupKey` moves into the
column-enumeration group of the select to satisfy ST06 ordering.

The model description also loses its stale "Paterson is excluded" sentence,
untrue since 079381c63.

### Skip the membership and report it once

`members_for_created_users` in
`src/teamster/libraries/google/directory/resources.py` is the single place
membership payloads are built, so the guard belongs there rather than in the
asset — every caller routes through it.

It returns a 2-tuple: the payloads for users whose `groupKey` resolved, and a
list holding at most one aggregated error dict that carries the count of skipped
users and the distinct `orgUnitPath` values affected. `orgUnitPath` names the
region precisely and is already on the payload, so no extra extract column is
needed to make the alert actionable.

`google_directory_user_create` extends its `errors` list with that second
element, so `zero_api_errors` still warns — once per run, naming the affected
schools, instead of once per student.

Unit tests go in the existing
`tests/resources/test_resource_google_directory.py`: a null `groupKey` is
excluded from the payloads and reported once, and a populated `groupKey` is
unaffected.

## Ship sequence

One PR. Pre-merge, on the branch deployment:

1. Push. The `src/teamster/**` changes give this PR a Dagster branch deployment;
   a dbt-only PR would not get one.
1. Materialize `kipptaf/google/directory/groups` in that branch deployment. The
   bucket redirect writes to
   `gs://teamster-test/dagster/kipptaf/google/directory/groups/`.
1. Stage the staging-target external at that location, because dbt Cloud CI runs
   `target=staging`, which resolves `cloud_storage_uri_base` to the prod bucket
   rather than the test one:

   ```text
   dbt run-operation stage_external_sources
     --args "select: google_directory.src_google_directory__groups"
     --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kipptaf, ext_full_refresh: true}'
     --target staging
   ```

   This drops and recreates a shared `zz_stg` table, so it is classifier-blocked
   and runs from the user's terminal or under explicitly-named authorization.

1. Confirm dbt Cloud CI passes on the new source and staging model.

## Verification

- `uv run python -c "import teamster.code_locations.kipptaf.google.directory.assets"`
  plus `py_compile` on the edited files. `dagster definitions validate` on
  `kipptaf.definitions` fails in the codespace on unrelated dlt credential
  resolution, so it is not the gate.
- `uv run pytest tests/resources/test_resource_google_directory.py` for the
  `members_for_created_users` guard.
- `uv run dbt compile --select stg_google_directory__groups rpt_google_directory__users_import --target prod`
  to resolve refs and SQL without a warehouse write.
- `uv run dbt build --select stg_google_directory__groups --target staging` once
  the external is staged, which is what exercises the contract.
- `trunk check --force` on the changed SQL, YAML, Python, and this document, run
  from inside the worktree.

## Risks

The prod external table does not exist until a prod `groups` materialization
drops a file in GCS, and `build_dbt_assets` runs `stage_external_sources` itself
with `ext_full_refresh` on every dbt asset run. The post-merge code deploy fires
the dbt automation within minutes, most likely before the 1:30am `groups`
schedule, and `stage_external_sources` fails creating an AVRO external over an
empty prefix.

Mitigation: launch `kipptaf/google/directory/groups` in prod as soon as the
post-merge deploy lands. Worst case the dbt staging step fails once and
self-heals on the next run after that materialization. This is a one-time
ordering problem at first deploy, so it gets an operator action rather than
machinery in the codebase.

## Out of scope

Tracked on #4766, not addressed here:

- Backfilling group membership for the 884 existing Paterson accounts.
- Recurring membership reconciliation. Membership is attempted only under
  `is_create`, so no region has drift correction today, and a student whose
  membership was skipped is never retried. Reconciliation needs the `members`
  asset, which re-enabling `groups` makes possible as a follow-up.
