# Google Directory student `externalIds` — design

Tracking issue: [#3950](https://github.com/TEAMSchools/teamster/issues/3950).
Follow-up: [#4057](https://github.com/TEAMSchools/teamster/issues/4057)
(uniqueness contracts on `rpt_google_directory__users_import`).

## Goal

Populate Google Workspace Directory `externalIds` with each student's
PowerSchool `student_number` (type `organization`).

- **Recurring**: every new student account created via
  `google_directory_user_create` carries `externalIds` from the moment of
  creation.
- **One-shot**: every existing matched student account (including those under
  `/Students/Disabled`) gets its `externalIds` backfilled to match.

The user-update path is explicitly left untouched — `externalIds` on existing
accounts is set exactly once, by either the create path or the backfill.

## Scope

In scope:

1. dbt: surface `student_number` on `rpt_google_directory__users_import`.
2. Dagster: attach `externalIds` on create; pop `student_number` on update.
3. One-shot Python script under `scripts/` to backfill existing matched
   accounts.

Out of scope:

- Uniqueness / not_null tests on `rpt_google_directory__users_import` — moved to
  #4057 (depends on backfill having run).
- Staff `externalIds`.
- Any `externalIds` type other than `organization`.
- Modification of existing accounts' `externalIds` via the recurring update
  path.

## Recurring create-path (the #3950 ask)

### dbt — `rpt_google_directory__users_import.sql`

Add `student_number` to the `students` CTE pulled from
`int_extracts__student_enrollments`; project it through `with_google` and
`final` unchanged; emit it in the final `SELECT` as plain `student_number`.

The model's existing `where is_create or is_update` filter is unchanged. Create
rows carry the real `student_number`; update rows also carry it (the asset pops
it before PATCH).

### Properties — `properties/rpt_google_directory__users_import.yml`

Add the column to the contract, with a `not_null` test scoped to create rows:

```yaml
- name: student_number
  data_type: int64
  description: >
    PowerSchool student_number. Consumed by google_directory_user_create to set
    externalIds[type='organization'] on new accounts; popped by
    google_directory_user_update before PATCH so the recurring update path never
    touches externalIds.
  data_tests:
    - not_null:
        config:
          severity: error
          where: "is_create"
```

**Why the `not_null` test:** `int_extracts__student_enrollments` does not
contractually guarantee `student_number` is populated for every row with a
`student_email`. If a create row reaches the asset with null `student_number`,
we would create a Google account without `externalIds`, and the recurring update
path pops `student_number` so there is no second opportunity to fix it short of
manual intervention. Failing dbt build instead forces upstream reconciliation
before any account is created.

No uniqueness test on this PR — see #4057.

### Dagster — `kipptaf/google/directory/assets.py`

In `google_directory_user_create`, after `arrow.to_pylist()`: partition into
valid create rows and rows missing `student_number`, record one synthetic error
per missing row, then call `batch_insert_users` on the valid rows only. The
existing `zero_api_errors` asset check surfaces the missing-student_number rows.

```python
errors = []
valid_users = []
for u in create_users:
    if u.get("student_number") is None:
        errors.append({
            "primaryEmail": u["primaryEmail"],
            "error": "missing student_number; cannot set externalIds",
        })
    else:
        student_number = u.pop("student_number")
        u["externalIds"] = [
            {"value": str(student_number), "type": "organization"}
        ]
        valid_users.append(u)

if valid_users:
    create_errors = google_directory.batch_insert_users(valid_users)
    for ce in create_errors:
        context.log.error(msg=ce)
        errors.append(ce)

    members_data = [
        {
            "groupKey": u["groupKey"],
            "email": u["primaryEmail"],
            "delivery_settings": "DISABLED",
        }
        for u in valid_users
    ]
    members_errors = google_directory.batch_insert_members(members_data)
    for me in members_errors:
        context.log.error(msg=me)
        errors.append(me)
```

`externalIds[].value` is a string in the Google Directory schema — cast at the
boundary.

The dbt `not_null` test should prevent any row from reaching this branch; the
asset-level guard is defense in depth in case the test is downgraded or
bypassed.

In `google_directory_user_update`, after `arrow.to_pylist()`:

```python
for u in update_users:
    u.pop("student_number", None)
```

No other changes to either asset.

## One-shot backfill — `scripts/backfill_google_directory_student_external_ids.py`

A standalone PEP 723 Python script. Not added to Dagster.

### Behavior

1. Query the warehouse for matched student accounts under any `/Students/*` org
   unit (including `/Students/Disabled`) whose Workspace `externalIds` does not
   contain the expected `organization` entry:

   ```sql
   select
       u.primary_email,
       se.student_number,
       u.org_unit_path
   from `teamster-332318.kipptaf_google.stg_google_directory__users` as u
   inner join `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments` as se
       on u.primary_email = se.student_email
       and se.rn_all = 1
   where u.org_unit_path like '/Students/%'
       and se.region != 'Paterson'
       and se.student_number is not null
       and not exists (
           select 1 from unnest(u.external_ids) as e
           where e.type = 'organization'
               and e.value = cast(se.student_number as string)
       )
   ```

2. For each row, call
   `users().patch(userKey=primary_email, body={"externalIds": [{"value": str(student_number), "type": "organization"}]})`.
   Use the same service-account + domain-wide-delegation path as
   `GoogleDirectoryResource` so behavior matches prod.

3. Dry-run by default. `--apply` to execute. Output one line per user:
   `primary_email | student_number | action` (no other PII).

4. Chunk via Google's HTTP `batch()` in groups of 50, with a small sleep between
   batches to stay under quota.

### PII handling

The script's output contains student emails and student_numbers. Capture stdout
only to `.claude/scratch/` or local terminal; never paste to PRs, issues, or
external surfaces. Aggregate counts (`would_patch / patched / skipped / errors`)
are safe to share.

### Idempotency

The query's `not exists` predicate filters out users whose `externalIds` already
match, so the script is naturally idempotent. If `stg_google_directory__users`
is stale (typical lag: <24h), a re-run after a fresh `users` materialization
will be a no-op for already-patched accounts.

## Verification

### Local (before opening PR)

- `uv run dbt build --select rpt_google_directory__users_import+ --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/`
  — confirms model parses, contract holds, tests pass.
- `uv run python -c "import teamster.code_locations.kipptaf.google.directory.assets"`
  — syntactic check on the assets edit.
- BQ spot-check on the PR-schema rpt model:
  `select count(*), count(student_number) from <pr_schema>.rpt_google_directory__users_import where is_create`
  — every create row carries student_number.

### dbt Cloud CI

CI runs `dbt build --select state:modified+ --full-refresh` on kipptaf staging.
The contract addition is `state:modified`, so the model and its downstream
rebuild. No external table staging required.

## Rollout sequence

1. Merge #3950 PR (this work).
2. Wait for the next prod materialization of the `users` asset (so
   `stg_google_directory__users` reflects post-deploy state for the create path
   going forward).
3. Run the backfill script with `--apply` from the Codespace under the same
   credentials Dagster uses; capture output to `.claude/scratch/`.
4. Re-materialize the `users` asset; spot-check 5-10 students across
   `/Students/*` (including `/Students/Disabled`) for the
   `externalIds.organization` entry.
5. Pick up #4057 to add uniqueness tests on the rpt model.
6. Close #3950.
