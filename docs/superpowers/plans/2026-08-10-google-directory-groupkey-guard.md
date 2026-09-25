# Google Directory `groupKey` Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop sending group-membership adds for a Google Workspace group that
does not exist, without blocking student account provisioning, and surface the
missing group once per run instead of once per student.

**Architecture:** Re-enable the dormant `groups` asset in the kipptaf Google
Directory code location so a `stg_google_directory__groups` model exists, then
left join it in `rpt_google_directory__users_import` so an unresolvable group
address becomes a null `groupKey` — the same shape `orgUnitPath` already uses.
The membership-payload builder skips null-`groupKey` users and returns one
aggregated error, which the `user_create` asset folds into its `zero_api_errors`
check.

**Tech Stack:** Dagster (`dagster`, `dagster-gcp`), Google Admin SDK Directory
API via `googleapiclient`, Pydantic + `py_avro_schema`, dbt on BigQuery, pytest,
uv.

Spec:
`docs/superpowers/specs/2026-08-10-google-directory-groupkey-guard-design.md`

Refs [#4766](https://github.com/TEAMSchools/teamster/issues/4766)

## Global Constraints

- **Worktree:** every command and every file edit targets
  `/workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard`.
  Use `git -C <worktree>` for git and `uv --directory <worktree> run ...`
  (prefixed with `VIRTUAL_ENV=`) for Python. Editing
  `/workspaces/teamster/<path>` instead silently dirties `main`.
- **Python:** always `uv run`, never bare `python` / `python3` / `pytest`.
- **`requires-python = ">=3.13"`.** Built-in generics (`list[dict]`,
  `tuple[list[dict], list[dict]]`), `X | None` for nullable.
- **Docstrings:** Google Python Style Guide. Multi-line is expected here.
- **Do not run `trunk fmt`.** The pre-commit hook formats. Run
  `.trunk/tools/trunk check --force --no-fix <paths> </dev/null` from inside the
  worktree only where a step says to; the binary lives only in the main repo, so
  invoke it by absolute path with cwd set to the worktree.
- **SQL conventions:** BigQuery dialect, trailing comma after the last select
  column (CV03), ST06 select-column ordering (plain refs grouped by source table
  in join order, then constants, then simple functions, then logicals), no
  one-sided calculations in join predicates, no `ORDER BY`, no `QUALIFY`, max
  one level of function nesting.
- **dbt staging layer:** `staging/` under `google/directory/` inherits
  `+materialized: table` and `+contract: enforced: true` from
  `src/dbt/kipptaf/dbt_project.yml` — do not repeat either in properties yml.
  Every staging test sets `config: severity: error` explicitly, because the
  project default is `warn`.
- **PII:** group addresses and org unit paths are not student PII. Do not put
  any student email, name, or number in a commit message, PR body, or issue
  comment.
- **The `members` asset and `MEMBERS_SCHEMA` stay commented out.** They belong
  to the deferred reconciliation work in #4766. Re-enabling them is out of
  scope.
- **Do not add a dbt test on null `groupKey`.** The extract is a view, and the
  data-change automation condition only re-materializes tables, so such a test
  would almost never re-run. The Python-side aggregated error is the alert.

---

## File Structure

| File                                                                                      | Responsibility                                    |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `src/teamster/libraries/google/directory/resources.py`                                    | Membership-payload builder; skip and report guard |
| `tests/resources/test_resource_google_directory.py`                                       | Unit tests for that builder                       |
| `src/teamster/code_locations/kipptaf/google/directory/schema.py`                          | Avro schema for the `groups` asset                |
| `src/teamster/code_locations/kipptaf/google/directory/assets.py`                          | `groups` asset; `user_create` caller wiring       |
| `src/teamster/code_locations/kipptaf/google/directory/schedules.py`                       | Daily pull of `groups`                            |
| `src/dbt/kipptaf/models/google/directory/sources-external.yml`                            | External Avro source over the new GCS prefix      |
| `src/dbt/kipptaf/models/google/directory/staging/stg_google_directory__groups.sql`        | Flat staging select                               |
| `.../staging/properties/stg_google_directory__groups.yml`                                 | Contract columns, uniqueness test, descriptions   |
| `src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql` | The guard join                                    |
| `.../extracts/google/directory/properties/rpt_google_directory__users_import.yml`         | `groupKey` description; stale Paterson sentence   |

Task order is Python first, then Dagster wiring, then dbt. Task 1 is inert until
Task 4 lands, because `groupKey` cannot be null before the join exists — so each
task is independently safe to merge.

---

### Task 1: Skip and report unresolvable group addresses

**Files:**

- Modify: `src/teamster/libraries/google/directory/resources.py:696-726`
- Modify:
  `src/teamster/code_locations/kipptaf/google/directory/assets.py:208-218`
- Test: `tests/resources/test_resource_google_directory.py:469-497`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  `members_for_created_users(users: list[dict], create_errors: list[dict]) -> tuple[list[dict], list[dict]]`.
  First element is `batch_insert_members` payloads (`groupKey` / `email` /
  `delivery_settings`). Second element holds at most one dict with keys `error`
  (str), `count` (int), `orgUnitPaths` (list[str]).

- [ ] **Step 1: Update the shared test fixtures**

The three existing tests call `_created_user`, which has no `orgUnitPath` and no
way to express a null `groupKey`. Replace both helpers at
`tests/resources/test_resource_google_directory.py:472-478`:

```python
def _created_user(
    email: str,
    group_key: str | None = "g@x.org",
    org_unit_path: str = "/Students/School A",
) -> dict:
    return {
        "primaryEmail": email,
        "groupKey": group_key,
        "orgUnitPath": org_unit_path,
    }


def _member(email: str) -> dict:
    return {"groupKey": "g@x.org", "email": email, "delivery_settings": "DISABLED"}
```

- [ ] **Step 2: Update the three existing tests for the tuple return**

Each currently asserts against a bare list. Replace the three assertions:

```python
def test_members_for_created_users_all_succeeded():
    users = [_created_user("a@x.org"), _created_user("b@x.org")]
    assert members_for_created_users(users, []) == (
        [_member("a@x.org"), _member("b@x.org")],
        [],
    )


def test_members_for_created_users_skips_failed_create():
    users = [_created_user("a@x.org"), _created_user("b@x.org")]
    create_errors = [{"primaryEmail": "b@x.org", "error": "boom"}]
    assert members_for_created_users(users, create_errors) == (
        [_member("a@x.org")],
        [],
    )


def test_members_for_created_users_all_failed_returns_empty():
    users = [_created_user("a@x.org")]
    create_errors = [{"primaryEmail": "a@x.org", "error": "boom"}]
    assert members_for_created_users(users, create_errors) == ([], [])
```

- [ ] **Step 3: Write the three new failing tests**

Append after `test_members_for_created_users_all_failed_returns_empty`:

```python
def test_members_for_created_users_skips_null_group_key():
    users = [_created_user("a@x.org"), _created_user("b@x.org", group_key=None)]

    members, _ = members_for_created_users(users, [])

    assert members == [_member("a@x.org")]


def test_members_for_created_users_reports_null_group_key_once():
    users = [
        _created_user("a@x.org", group_key=None, org_unit_path="/Students/School B"),
        _created_user("b@x.org", group_key=None, org_unit_path="/Students/School A"),
    ]

    _, unresolved = members_for_created_users(users, [])

    assert unresolved == [
        {
            "error": (
                "2 created users have no resolvable students group; membership"
                " skipped"
            ),
            "count": 2,
            "orgUnitPaths": ["/Students/School A", "/Students/School B"],
        }
    ]


def test_members_for_created_users_does_not_report_null_group_key_for_failed_create():
    users = [_created_user("a@x.org", group_key=None)]
    create_errors = [{"primaryEmail": "a@x.org", "error": "boom"}]

    assert members_for_created_users(users, create_errors) == ([], [])
```

The third test is the one that matters for alert hygiene: a user whose account
creation failed is already reported by `batch_insert_users`, so reporting it
again as an unresolved group would double-count the same student.

- [ ] **Step 4: Run the tests to verify they fail**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  run pytest tests/resources/test_resource_google_directory.py -k members_for_created_users -v
```

Expected: the three updated tests fail comparing a `list` to a `tuple`; the
three new tests fail unpacking a `list` into two names
(`ValueError: too many values to unpack`) or on the missing second element.

- [ ] **Step 5: Rewrite the helper**

Replace the whole function at
`src/teamster/libraries/google/directory/resources.py:696-726`:

```python
def members_for_created_users(
    users: list[dict], create_errors: list[dict]
) -> tuple[list[dict], list[dict]]:
    """Build group-membership payloads for users whose creation did not fail.

    A user's group membership can only be added once the account exists, so a
    user whose ``batch_insert_users`` call failed must be excluded — otherwise
    the membership insert is guaranteed to fail with "resource not found".

    A user whose ``groupKey`` is null is excluded for a different reason: the
    extract resolves ``groupKey`` against the groups Google actually has, so
    null means the students group for that region does not exist. Attempting the
    add would fail with "404 Resource Not Found: groupKey" once per user, so the
    membership is skipped and reported once for the whole run instead.

    Args:
        users: The users passed to
            :meth:`GoogleDirectoryResource.batch_insert_users`.
        create_errors: The ``{"primaryEmail", "error"}`` dicts it returned for
            users whose creation ultimately failed.

    Returns:
        A two-tuple. The first element holds
        :meth:`GoogleDirectoryResource.batch_insert_members` payloads
        (``groupKey`` / ``email`` / ``delivery_settings``) for created users
        whose ``groupKey`` resolved. The second holds at most one aggregated
        ``{"error", "count", "orgUnitPaths"}`` dict describing the created users
        whose group could not be resolved, and is empty when every group
        resolved.
    """
    failed_emails = {e["primaryEmail"] for e in create_errors}

    created = [u for u in users if u["primaryEmail"] not in failed_emails]

    members = [
        {
            "groupKey": u["groupKey"],
            "email": u["primaryEmail"],
            "delivery_settings": "DISABLED",
        }
        for u in created
        if u["groupKey"] is not None
    ]

    unresolved = [u for u in created if u["groupKey"] is None]

    if not unresolved:
        return members, []

    return members, [
        {
            "error": (
                f"{len(unresolved)} created users have no resolvable students"
                " group; membership skipped"
            ),
            "count": len(unresolved),
            "orgUnitPaths": sorted({u["orgUnitPath"] for u in unresolved}),
        }
    ]
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  run pytest tests/resources/test_resource_google_directory.py -k members_for_created_users -v
```

Expected: 6 passed.

- [ ] **Step 7: Update the caller**

In `src/teamster/code_locations/kipptaf/google/directory/assets.py`, replace the
comment and call at lines 208-218:

```python
            # Only add users whose creation succeeded — a failed create leaves
            # no account, so its member insert would fail with "resource not
            # found" and double-count the same student in the error check.
            # Users whose groupKey did not resolve are skipped and reported
            # once, rather than once per user.
            members_data, unresolved_group_errors = members_for_created_users(
                valid_users, create_errors
            )

            errors.extend(unresolved_group_errors)

            if members_data:
                members_errors = google_directory.batch_insert_members(members_data)

                for me in members_errors:
                    context.log.error(msg=me)
                    errors.append(me)
```

- [ ] **Step 8: Verify the whole resource test module still passes**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  run pytest tests/resources/test_resource_google_directory.py -v \
  --deselect tests/resources/test_resource_google_directory.py::test_list_orgunits \
  --deselect tests/resources/test_resource_google_directory.py::test_get_orgunit \
  --deselect tests/resources/test_resource_google_directory.py::test_list_roles \
  --deselect tests/resources/test_resource_google_directory.py::test_list_role_assignments \
  --deselect tests/resources/test_resource_google_directory.py::test_list_members
```

Expected: no failures. Those five deselected tests are credential-backed
developer probes that call the live Directory API and dump JSON into `env/`;
they error without Google credentials. Every other test in the module, including
the mocked `test_list_*` pagination and retry tests, must pass — do not widen
the deselect list to `-k "not list_"`, which would silently skip those.

- [ ] **Step 9: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
git add src/teamster/libraries/google/directory/resources.py \
  src/teamster/code_locations/kipptaf/google/directory/assets.py \
  tests/resources/test_resource_google_directory.py
git commit -m "fix(dagster): skip membership adds for an unresolved students group

Refs #4766"
```

---

### Task 2: Re-enable the `groups` asset

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/google/directory/schema.py:1-25`
- Modify:
  `src/teamster/code_locations/kipptaf/google/directory/assets.py:13-18,31,279-303`
- Modify:
  `src/teamster/code_locations/kipptaf/google/directory/schedules.py:4-12,23`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces: Dagster asset key `kipptaf/google/directory/groups`, writing Avro to
  `<bucket>/dagster/kipptaf/google/directory/groups/`. Task 3's dbt source reads
  that prefix.

- [ ] **Step 1: Add the Avro schema**

In `schema.py`, add `Group` to the existing import and uncomment the schema. The
import block and the new constant:

```python
from teamster.libraries.google.directory.schema import (
    Group,
    OrgUnits,
    Role,
    RoleAssignment,
    User,
)

GROUPS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Group, namespace="group"))
```

Place `GROUPS_SCHEMA` above `ORGUNITS_SCHEMA` to keep the constants
alphabetical, and delete only the commented `GROUPS_SCHEMA` line at the bottom.
Leave the commented `MEMBERS_SCHEMA` line exactly as it is.

- [ ] **Step 2: Verify the schema generates**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  run python -c "from teamster.code_locations.kipptaf.google.directory.schema import GROUPS_SCHEMA; print(sorted(f['name'] for f in GROUPS_SCHEMA['fields']))"
```

Expected:
`['adminCreated', 'aliases', 'description', 'directMembersCount', 'email', 'etag', 'id', 'kind', 'name', 'nonEditableAliases']`.

If this fails with a missing `manifest.json`, the code location's `__init__`
needs the dbt manifest — build it once in the worktree, then re-run:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

- [ ] **Step 3: Define the asset**

In `assets.py`, add `GROUPS_SCHEMA` to the schema import (alphabetically first),
then insert this asset immediately above the existing `orgunits` asset at
line 31. It must be defined above the `assets` list at the bottom of the file,
or the list raises `NameError`:

```python
@asset(
    key=[*key_prefix, "groups"],
    check_specs=[build_check_spec_avro_schema_valid([*key_prefix, "groups"])],
    io_manager_key="io_manager_gcs_avro",
    group_name="google_directory",
    kinds={"python"},
)
def groups(context: AssetExecutionContext, google_directory: GoogleDirectoryResource):
    data = google_directory.list_groups()

    yield Output(value=(data, GROUPS_SCHEMA), metadata={"record_count": len(data)})

    yield check_avro_schema_valid(
        asset_key=context.asset_key, records=data, schema=GROUPS_SCHEMA
    )
```

Then add `groups` to the `assets` list, before `orgunits`:

```python
assets = [
    google_directory_role_assignments_create,
    google_directory_user_create,
    google_directory_user_update,
    groups,
    orgunits,
    role_assignments,
    roles,
    users,
]
```

Delete the now-duplicated commented `groups` asset block at the bottom of the
file. Leave the commented `members` asset and
`google_directory_partitioned_assets` block untouched.

`GoogleDirectoryResource.list_groups()` already exists and takes no required
arguments — do not add or change resource methods.

- [ ] **Step 4: Schedule the daily pull**

In `schedules.py`, add `groups` to the asset import (alphabetically, after the
three `google_directory_*` names) and to the nonpartitioned schedule target:

```python
google_directory_nonpartitioned_asset_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__google__directory__nonpartitioned_asset_job_schedule",
    target=[groups, orgunits, role_assignments, roles, users],
    cron_schedule="30 1 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)
```

This is the same 1:30am schedule `orgunits` uses. Do not add a separate schedule
and do not change any cron.

- [ ] **Step 5: Verify the modules compile and the wiring is present**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
VIRTUAL_ENV= uv --directory . run python -m py_compile \
  src/teamster/code_locations/kipptaf/google/directory/assets.py \
  src/teamster/code_locations/kipptaf/google/directory/schedules.py \
  src/teamster/code_locations/kipptaf/google/directory/schema.py
grep -n "groups," src/teamster/code_locations/kipptaf/google/directory/assets.py \
  src/teamster/code_locations/kipptaf/google/directory/schedules.py
```

Expected: `py_compile` silent, and `grep` shows `groups,` in both the `assets`
list and the schedule `target`.

`dagster definitions validate -m teamster.code_locations.kipptaf.definitions` is
NOT the gate here — it fails in this codespace on unrelated Illuminate and
Zendesk dlt credential resolution. The real runtime gate is the branch
deployment in Task 5.

- [ ] **Step 6: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
git add src/teamster/code_locations/kipptaf/google/directory/assets.py \
  src/teamster/code_locations/kipptaf/google/directory/schedules.py \
  src/teamster/code_locations/kipptaf/google/directory/schema.py
git commit -m "feat(dagster): pull Google Workspace groups daily

Refs #4766"
```

---

### Task 3: Stage groups as a dbt source and staging model

**Files:**

- Modify: `src/dbt/kipptaf/models/google/directory/sources-external.yml:26`
- Create:
  `src/dbt/kipptaf/models/google/directory/staging/stg_google_directory__groups.sql`
- Create:
  `src/dbt/kipptaf/models/google/directory/staging/properties/stg_google_directory__groups.yml`

**Interfaces:**

- Consumes: the GCS prefix written by Task 2's asset.
- Produces: `ref("stg_google_directory__groups")` with columns `email`, `id`,
  `name`, `description`, `direct_members_count`, `admin_created`, `etag`,
  `kind`, `aliases`, `non_editable_aliases`. Task 4 joins on `email`.

- [ ] **Step 1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`, and every later dbt command fails
without it.

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard/src/dbt/kipptaf
```

- [ ] **Step 2: Declare the external source**

In `sources-external.yml`, insert this block immediately after the
`src_google_directory__users` block and before `src_google_directory__orgunits`.
Indentation must match its siblings exactly — the block starts at 6 spaces:

```yaml
- name: src_google_directory__groups
  external:
    location: "{{ var('cloud_storage_uri_base') }}/google/directory/groups/*"
    options:
      connection_name: "{{ var('bigquery_external_connection_name') }}"
      metadata_cache_mode: MANUAL
      max_staleness: INTERVAL 7 DAY
      format: AVRO
      enable_logical_types: true
  config:
    meta:
      dagster:
        asset_key:
          - kipptaf
          - google
          - directory
          - groups
```

Do not touch the source-level `schema:` block — the existing dev/staging/prod
prefix conditional already covers every table in this source.

- [ ] **Step 3: Write the staging model**

Create `stg_google_directory__groups.sql`. BigQuery column references are
case-insensitive, so the lowercased Avro field names are the repo convention
here (matching `stg_google_directory__users.sql`). The trailing comma after the
last column is required by sqlfluff CV03:

```sql
select
    id,
    email,
    name,
    description,
    directmemberscount as direct_members_count,
    admincreated as admin_created,
    etag,
    kind,

    /* repeated */
    aliases,
    noneditablealiases as non_editable_aliases,
from {{ source("google_directory", "src_google_directory__groups") }}
```

If `trunk check` in Step 6 flags `name` under sqlfluff RF04 (reserved keyword as
identifier), change that line to ``name as `name`,`` — the backticked form is
the precedent in `stg_google_directory__orgunits.sql` and is not an AL09
self-alias violation. Make no other change in response to RF04.

- [ ] **Step 4: Write the properties yml**

Create `properties/stg_google_directory__groups.yml`. `email` sorts to the top
because it carries the column-level tests. Do not add `materialized` or
`contract` — both are inherited from `dbt_project.yml`:

```yaml
models:
  - name: stg_google_directory__groups
    description: >
      Google Workspace groups as returned by the Directory API groups list
      endpoint. Consumed by rpt_google_directory__users_import to confirm that a
      region's student group exists before a membership add is attempted against
      it.
    columns:
      - name: email
        data_type: string
        description: >
          Primary address of the group. Join key for validating a constructed
          student group address against the groups Google actually has.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: id
        data_type: string
        description: Immutable Google-assigned identifier for the group.
      - name: name
        data_type: string
        description: Display name of the group, as set in the admin console.
      - name: description
        data_type: string
        description: >
          Free-text purpose of the group, as set in the admin console. Often
          empty.
      - name: direct_members_count
        data_type: string
        description: >
          Number of members that belong to the group directly rather than
          through a nested group. Carried as a string by the Directory API.
      - name: admin_created
        data_type: boolean
        description: >
          True when an administrator created the group, false when it was
          created by a user.
      - name: etag
        data_type: string
        description: Entity tag of the resource, reported by the API.
      - name: kind
        data_type: string
        description: >
          Resource type reported by the API, always admin#directory#group.
      - name: aliases
        data_type: array<string>
        description: Alternate addresses that deliver to this group.
      - name: non_editable_aliases
        data_type: array<string>
        description: >
          Domain-derived alternate addresses for the group that cannot be
          edited.
```

- [ ] **Step 5: Verify the model parses and compiles**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster run dbt compile \
  --select stg_google_directory__groups --target prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard/src/dbt/kipptaf
```

Expected: compiles, and `target/compiled/.../stg_google_directory__groups.sql`
resolves the source to `kipptaf_google_directory.src_google_directory__groups`.
`compile` performs no warehouse write. A `dbt build` cannot work yet — the
external table does not exist until Task 5 materializes the asset and stages it.

- [ ] **Step 6: Lint the new files**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/google/directory/sources-external.yml \
  src/dbt/kipptaf/models/google/directory/staging/stg_google_directory__groups.sql \
  src/dbt/kipptaf/models/google/directory/staging/properties/stg_google_directory__groups.yml \
  </dev/null
```

If `.trunk/tools/trunk` does not exist, use `~/.cache/trunk/launcher/trunk`
instead — the symlink is created lazily on first run. Formatting-only findings
(`prettier`, MD060) are fixed by the pre-commit hook; act only on sqlfluff and
yamllint findings that name a rule and a line.

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
git add src/dbt/kipptaf/models/google/directory/sources-external.yml \
  src/dbt/kipptaf/models/google/directory/staging/stg_google_directory__groups.sql \
  src/dbt/kipptaf/models/google/directory/staging/properties/stg_google_directory__groups.yml
git commit -m "feat(dbt): stage Google Workspace groups

Refs #4766"
```

---

### Task 4: Resolve `groupKey` against the staged groups

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql:186-260`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml:3-11,45-46`

**Interfaces:**

- Consumes: `ref("stg_google_directory__groups")` from Task 3, joined on
  `email`.
- Produces: the `groupKey` column of
  `kipptaf_extracts.rpt_google_directory__users_import`, now null when the
  region's students group is absent from Google. Task 1's helper reads it.

- [ ] **Step 1: Derive the target address in `with_google`**

Add one column to the `with_google` select, between `u.surrogate_key_target` and
the first `if(...)`. ST06 puts an operator expression before the logicals:

```sql
            u.surrogate_key_target,

            'group-students-' || s.region || '@teamstudents.org'
            as group_key_target,

            if(u.primary_email is not null, true, false) as is_matched,
```

The address is built here, one CTE upstream of the join, for two reasons: the
SQL guide forbids one-sided calculations in join predicates, and BigQuery
rejects a select-list alias referenced from its own select's `ON` clause.

- [ ] **Step 2: Join the groups model in `final`**

Replace the whole `final` CTE. It gains a table alias because it now reads from
two relations, so every column reference is prefixed:

```sql
    final as (
        select
            w.*,

            g.email as group_key,

            if(not w.is_matched and not w.suspended, true, false) as is_create,

            if(
                w.is_matched
                and {{
                    dbt_utils.generate_surrogate_key(
                        ["first_name", "last_name", "suspended", "org_unit_path"]
                    )
                }} != w.surrogate_key_target,
                true,
                false
            ) as is_update,
        from with_google as w
        /* A null group_key means the region's students group does not exist in
        Google. Unlike a null org_unit_path, it does NOT drop the student: the
        account is still provisioned, and the user_create asset skips the
        membership add and reports the missing group once. */
        left join
            {{ ref("stg_google_directory__groups") }} as g
            on w.group_key_target = g.email
    )
```

Leave the `generate_surrogate_key` arguments unqualified. They are column-name
strings, and `g` contributes none of those four names, so they stay unambiguous.

- [ ] **Step 3: Project the resolved address in the outer select**

Replace the outer select's column list. `groupKey` is now a plain column
reference, so ST06 moves it up into the enumeration group and out of the
constants group where the concatenation used to sit:

```sql
select
    student_email_google as `primaryEmail`,
    org_unit_path as `orgUnitPath`,
    group_key as `groupKey`,
    suspended,
    is_create,
    is_update,
    student_number,

    'SHA-1' as `hashFunction`,

    struct(first_name as `givenName`, last_name as `familyName`) as `name`,
    to_hex(sha1(student_web_password)) as `password`,

    if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,
from final
```

Do NOT change the trailing `where` clause or its comment. The student must stay
in the extract when the group is missing. `group_key_target` reaches `final` via
`w.*` but is deliberately not projected here — the extract's columns become the
Google `users.insert` payload, so an unused extra field would ride along.

- [ ] **Step 4: Update the properties yml**

Two edits. First, the model description's last sentence claims Paterson is
excluded, untrue since 079381c63 — replace the description:

```yaml
description: >
  Google Workspace student accounts to create or update, consumed by the
  google_directory user_create and user_update assets. Rows are the union of two
  enrollment sources — PowerSchool for the NJ regions, and Focus for Miami,
  whose PowerSchool instance is a frozen archive. A row appears only when the
  account is missing (is_create) or when its name, suspension state, or org unit
  has drifted from the source of record (is_update).
```

Second, give `groupKey` a description recording the null semantics:

```yaml
- name: groupKey
  data_type: string
  description: >
    Address of the region's student group, resolved against
    stg_google_directory__groups. Null when that group does not exist in Google
    Workspace, in which case the account is still created and the membership add
    is skipped.
```

Add no data test on this column — see Global Constraints.

- [ ] **Step 5: Verify the extract compiles**

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster run dbt compile \
  --select rpt_google_directory__users_import --target prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard/src/dbt/kipptaf
```

Expected: compiles. Read
`target/compiled/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql`
and confirm three things: the `left join` resolves to
`kipptaf_google_directory.stg_google_directory__groups`, the outer select
projects `group_key as groupKey`, and `group_key_target` appears nowhere in the
outer select.

- [ ] **Step 6: Lint the changed SQL**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql \
  src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml \
  </dev/null
```

Expected: no sqlfluff findings. ST06 (column ordering) and ST09 (join-predicate
order) are the two rules this change is most likely to trip; both fire only at
pre-push and CI, so this step is not optional.

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard
git add src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql \
  src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml
git commit -m "fix(dbt): resolve groupKey against the staged Google groups

Refs #4766"
```

---

### Task 5: Validate on the branch deployment and open the PR

**Files:** none. This task is operational.

**Interfaces:**

- Consumes: everything from Tasks 1-4.
- Produces: a staged
  `zz_stg_kipptaf_google_directory.src_google_directory__groups` external table,
  a green dbt Cloud CI run, and an open PR.

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard \
  push -u origin cbini/fix/claude-google-directory-groupkey-guard
```

The pre-push hook runs `trunk check` git-diff-scoped. It can miss findings on
already-committed lines, which is why Tasks 3 and 4 ran `--force` explicitly.

- [ ] **Step 2: Open the PR**

Use `.github/pull_request_template.md` as the body and include `Refs #4766` so
the PR lands on the project board. Do not `gh project item-add` the PR.

Because the diff touches `src/teamster/**`, this PR gets a Dagster branch
deployment. Recover its name from the `dagster-cloud-deploy / deploy` job log
line `Deploying to branch deployment <hash>`; there are ~5 same-named check
runs, one per code location, and all must reach a terminal conclusion before the
deploy counts as green.

- [ ] **Step 3: Materialize `groups` in the branch deployment**

Preview first, then confirm:

```text
mcp__dagster__launch_run(
    asset_keys=["kipptaf/google/directory/groups"],
    deployment="<branch-deployment-hash>",
    confirm=False,
)
```

A dormant branch deployment throws `DagsterUserCodeUnreachableError` on the
first call — retry after about 90 seconds to let the code location warm.

Confirm the Avro landed via `mcp__dagster__get_asset_materializations` and check
`record_count` is greater than zero. Branch deployments redirect the bucket, so
the file is at `gs://teamster-test/dagster/kipptaf/google/directory/groups/`.

Also confirm the asset's `avro_schema_valid` check passed. A warning there means
the Directory API returns a field the `Group` Pydantic model does not declare;
the fix is to add the field to
`src/teamster/libraries/google/directory/schema.py`, not to suppress the check.

- [ ] **Step 4: Stage the staging-target external (user runs this)**

dbt Cloud CI runs `target=staging`, which resolves `cloud_storage_uri_base` to
the prod bucket — not the test bucket the branch deployment just wrote to. So
the location must be overridden for this one staging run:

```text
uv run dbt run-operation stage_external_sources
  --args "select: google_directory.src_google_directory__groups"
  --vars '{cloud_storage_uri_base: gs://teamster-test/dagster/kipptaf, ext_full_refresh: true}'
  --target staging
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard/src/dbt/kipptaf
```

This drops and recreates a shared `zz_stg` table, so the auto-classifier blocks
it. Hand it to the user's terminal rather than retrying it.

- [ ] **Step 5: Build the staging model to exercise the contract**

Contract enforcement (`assert_columns_equivalent`) runs only inside a real
`dbt build`, never in `compile` and never in a SELECT against the external. This
is the first point at which it can run, because the external table now exists:

```bash
VIRTUAL_ENV= uv --directory /workspaces/teamster run dbt build \
  --select stg_google_directory__groups --target staging \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-google-directory-groupkey-guard/src/dbt/kipptaf
```

Expected: the model builds and both `email` tests pass. A contract failure here
names the offending column and type — reconcile the properties yml `data_type`
against `INFORMATION_SCHEMA.COLUMNS` on the staged table rather than guessing;
`numeric` and `float64` are distinct types, and BigQuery's legacy spellings
(`bool` / `boolean`, `int64` / `integer`) may differ between the yml and
`INFORMATION_SCHEMA` without being real drift.

- [ ] **Step 6: Verify the three working regions resolve — added by the final
      review**

The join compares the constructed address to
`stg_google_directory__groups.email` only. The code it replaces passed that
address to `members.insert`, which also resolves aliases and unique ids. So if
`newark`, `camden`, or `miami`'s address is an **alias** of a group whose
primary address differs, this change turns a working region's `groupKey` null
and silently stops its membership adds — the regression class this branch exists
to prevent, inverted.

This is the first point where it can be checked, because the staged table now
holds real group data:

```sql
select email
from `teamster-332318.zz_stg_kipptaf_google_directory.stg_google_directory__groups`
where email like 'group-students-%'
```

Expect `camden`, `miami`, and `newark` — and NOT `paterson`, whose absence is
the bug this branch guards. If any of the three is missing, its address is an
alias: add `or w.group_key_target in unnest(g.aliases)` to the join in
`rpt_google_directory__users_import.sql`. The staging model already carries
`aliases`, so no schema change is needed. Do not add that arm speculatively —
verify first, because an unnecessary alias arm widens the match and can resolve
a group address that Google would have rejected.

- [ ] **Step 7: Confirm CI is green on both surfaces**

dbt Cloud is a commit status; Trunk, CodeQL, and `claude` are check runs. Check
both:

```bash
gh pr checks <pr-number> --json name,bucket,state
```

Trunk's check runs are re-created on every push, so a poll that samples the gap
between them can report done prematurely — re-check after a delay. After dbt
Cloud passes, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` before calling
the PR done.

Process `claude-review` findings through `superpowers:receiving-code-review` —
verify each claim against the code before replying. It runs only on `opened` /
`ready_for_review`, never on a push, so do not wait for a re-review after
pushing a fix.

- [ ] **Step 8: Record the two post-merge actions in the PR body**

Neither is a code change, and both need an owner:

1. Ops creates `group-students-paterson@teamstudents.org` in the admin console.
   Until then the guard fires one warning per run and Paterson accounts are
   created without membership.
1. Launch `kipptaf/google/directory/groups` in prod as soon as the post-merge
   deploy lands. The prod external table does not exist until a prod
   materialization drops a file, and `build_dbt_assets` runs
   `stage_external_sources` on every dbt asset run — which fails creating an
   AVRO external over an empty prefix. The dbt automation fires within minutes
   of the deploy, well before the 1:30am schedule. Worst case it fails once and
   self-heals after the manual materialization.

---

## Out of scope

Tracked on #4766, deliberately not in this plan:

- Backfilling group membership for the 884 existing Paterson accounts.
- Recurring membership reconciliation. Membership is attempted only under
  `is_create`, so no region has drift correction, and a student whose membership
  was skipped is never retried. That work needs the `members` asset, which
  re-enabling `groups` makes possible as a follow-up.
