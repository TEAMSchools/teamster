# Google Directory student `externalIds` — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate Google Workspace `externalIds[type='organization']` with
PowerSchool `student_number` on new student accounts created via
`google_directory_user_create`, plus a one-shot backfill for existing matched
accounts.

**Architecture:** dbt rpt model surfaces `student_number` to the create-path
asset; the create asset attaches `externalIds` before `batch_insert_users`, the
update asset pops the column so the recurring update path never touches
`externalIds`. A standalone PEP 723 Python script handles the existing-account
backfill. Tracking issue:
[#3950](https://github.com/TEAMSchools/teamster/issues/3950). Follow-up:
[#4057](https://github.com/TEAMSchools/teamster/issues/4057).

**Tech Stack:** dbt (BigQuery), Dagster, `googleapiclient`, `google-auth`,
`google-cloud-bigquery`, `uv` PEP 723 inline deps.

**Spec:**
[`docs/superpowers/specs/2026-05-28-google-directory-student-external-ids-design.md`](../specs/2026-05-28-google-directory-student-external-ids-design.md).

**Working directory:** All commands assume the worktree at
`/workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids`.

---

## File map

- **Modify:**
  `src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql`
  — surface `student_number` from `int_extracts__student_enrollments`.
- **Modify:**
  `src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml`
  — declare `student_number int64` on the contract; add `not_null` test scoped
  to `is_create`.
- **Modify:** `src/teamster/code_locations/kipptaf/google/directory/assets.py` —
  in `google_directory_user_create`, partition by `student_number` presence and
  attach `externalIds`; in `google_directory_user_update`, pop the column.
- **Create:** `scripts/backfill_google_directory_student_external_ids.py` — PEP
  723 one-shot backfill for existing matched student accounts.

---

## Task 1: Surface `student_number` in `rpt_google_directory__users_import`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml`

- [ ] **Step 1: Add `student_number` to the `students` CTE**

  In `rpt_google_directory__users_import.sql`, modify the `students` CTE to pull
  `student_number` (BIGINT in PowerSchool, lands as INT64). Final state of that
  CTE:

  ```sql
  students as (
      select
          student_number,
          student_first_name as first_name,
          student_last_name as last_name,
          school_name,
          grade_level,
          student_email as student_email_google,
          student_web_password,
          is_out_of_district,

          lower(region) as region,

          if(enroll_status = 0, false, true) as suspended,
      from {{ ref("int_extracts__student_enrollments") }}
      where rn_all = 1 and student_email is not null and region != 'Paterson'
  ),
  ```

  `student_number` is the first column to satisfy sqlfluff ST06 (plain refs
  ordered before function/conditional columns).

- [ ] **Step 2: Project `student_number` through `final` SELECT**

  At the bottom of the file, add `student_number,` to the final `SELECT`
  immediately after `changePasswordAtNextLogin`. Final tail of the file:

  ```sql
  select
      student_email_google as `primaryEmail`,
      org_unit_path as `orgUnitPath`,
      suspended,
      is_create,
      is_update,

      'SHA-1' as `hashFunction`,

      'group-students-' || region || '@teamstudents.org' as `groupKey`,

      struct(first_name as `givenName`, last_name as `familyName`) as `name`,
      to_hex(sha1(student_web_password)) as `password`,

      if(grade_level >= 3, true, false) as `changePasswordAtNextLogin`,

      student_number,
  from final
  where is_create or is_update
  ```

  `student_number` is grouped last (plain ref from `final`) to keep the
  conditional/function columns together as in the existing file. sqlfluff ST06
  allows a trailing plain-ref column block.

- [ ] **Step 3: Add `student_number` column to the contract YAML**

  In `properties/rpt_google_directory__users_import.yml`, append the column
  block after the existing entries. The column-level `data_tests` go on this
  column (single-column test), keeping the per-column-test column near the top
  per dbt conventions — for this one-test file, put it after
  `changePasswordAtNextLogin`:

  ```yaml
  models:
    - name: rpt_google_directory__users_import
      columns:
        - name: primaryEmail
          data_type: string
        - name: orgUnitPath
          data_type: string
        - name: suspended
          data_type: boolean
        - name: is_create
          data_type: boolean
        - name: is_update
          data_type: boolean
        - name: hashFunction
          data_type: string
        - name: groupKey
          data_type: string
        - name: name
          data_type: record
        - name: name.givenName
          data_type: string
        - name: name.familyName
          data_type: string
        - name: password
          data_type: string
        - name: changePasswordAtNextLogin
          data_type: boolean
        - name: student_number
          data_type: int64
          description: >
            PowerSchool student_number. Consumed by google_directory_user_create
            to set externalIds[type='organization'] on new accounts; popped by
            google_directory_user_update before PATCH so the recurring update
            path never touches externalIds.
          data_tests:
            - not_null:
                config:
                  severity: error
                  where: "is_create"
  ```

- [ ] **Step 4: Parse + build locally to verify contract**

  ```bash
  uv run dbt build \
      --select rpt_google_directory__users_import \
      --project-dir src/dbt/kipptaf \
      --target dev \
      --defer \
      --state src/dbt/kipptaf/target/prod/
  ```

  Expected: model materializes, contract holds (no "column type mismatch"
  error), `not_null_rpt_google_directory__users_import_student_number` test
  passes (no PASS — should be a green test row in the summary). If `not_null`
  fails locally, that means upstream `int_extracts__student_enrollments` has
  students with email but no student_number — stop and surface the failing
  students to the user before continuing.

- [ ] **Step 5: BigQuery spot-check that `student_number` populates create
      rows**

  ```bash
  uv run dbt show \
      --project-dir src/dbt/kipptaf \
      --target dev \
      --inline "select count(*) as create_rows, count(student_number) as nonnull_student_numbers from {{ ref('rpt_google_directory__users_import') }} where is_create"
  ```

  Expected: `create_rows == nonnull_student_numbers`. If they diverge, the dbt
  test in step 4 should also have failed — stop and reconcile upstream.

- [ ] **Step 6: Commit**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  git -C . add -u src/dbt/kipptaf/models/extracts/google/directory/
  git -C . commit -m "feat(dbt): surface student_number on rpt_google_directory__users_import

  Refs #3950"
  ```

---

## Task 2: Attach `externalIds` on create / pop on update

**Files:**

- Modify: `src/teamster/code_locations/kipptaf/google/directory/assets.py`

- [ ] **Step 1: Replace the body of `google_directory_user_create`'s post-query
      block**

  Find the existing block in `assets.py` starting at the line
  `if arrow.num_rows > 0:` inside `google_directory_user_create`. Replace it
  with the partition-and-attach version. The full final state of
  `google_directory_user_create` (lines ~147–206 of the existing file) becomes:

  ```python
  @asset(
      key=[*key_prefix, "user_create"],
      deps=[AssetKey(["kipptaf", "extracts", "rpt_google_directory__users_import"])],
      check_specs=[
          AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "user_create"])
      ],
      group_name="google_directory",
      kinds={"python", "task"},
  )
  def google_directory_user_create(
      context: AssetExecutionContext,
      db_bigquery: BigQueryResource,
      google_directory: GoogleDirectoryResource,
  ):
      query = """
          select * from kipptaf_extracts.rpt_google_directory__users_import
          where is_create
      """
      errors = []

      context.log.info(msg=query)
      with db_bigquery.get_client() as bq:
          query_job = bq.query(query=query, project=db_bigquery.project)

      arrow = query_job.to_arrow()

      context.log.info(msg=f"Retrieved {arrow.num_rows} rows")

      if arrow.num_rows > 0:
          create_users = arrow.to_pylist()

          valid_users = []
          for u in create_users:
              if u.get("student_number") is None:
                  errors.append(
                      {
                          "primaryEmail": u["primaryEmail"],
                          "error": "missing student_number; cannot set externalIds",
                      }
                  )
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

      yield Output(value=None)
      yield AssetCheckResult(
          passed=(len(errors) == 0),
          asset_key=context.asset_key,
          check_name="zero_api_errors",
          metadata={"errors": errors},
          severity=AssetCheckSeverity.WARN,
      )
  ```

  Key differences vs current code:
  - `create_users` is partitioned into `valid_users` (have `student_number`) and
    error entries (missing `student_number`).
  - `batch_insert_users` and `batch_insert_members` only run if `valid_users` is
    non-empty.
  - `members_data` is built from `valid_users`, not `create_users` — never
    create group memberships for users we refused to insert.

- [ ] **Step 2: Pop `student_number` in `google_directory_user_update`**

  In the same file, find the body of `google_directory_user_update`'s
  `if arrow.num_rows > 0:` block. Insert a single pop loop immediately after
  `update_users = arrow.to_pylist()`. Final state of that block:

  ```python
      if arrow.num_rows > 0:
          update_users = arrow.to_pylist()

          for u in update_users:
              u.pop("student_number", None)

          errors = google_directory.batch_update_users(update_users)

          for e in errors:
              context.log.error(msg=e)
  ```

  This guarantees the recurring update PATCH never carries `student_number` /
  `externalIds`. Use `pop(..., None)` (default `None`) so we don't crash if a
  future dbt change drops the column.

- [ ] **Step 3: Syntactic verification**

  ```bash
  uv run python -c "import teamster.code_locations.kipptaf.google.directory.assets"
  ```

  Expected: no output, exit 0. If `ImportError` or `SyntaxError`, fix the
  reported line before continuing.

- [ ] **Step 4: Commit**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  git -C . add -u src/teamster/code_locations/kipptaf/google/directory/assets.py
  git -C . commit -m "feat(google-directory): attach student_number externalIds on user create

  Refs #3950"
  ```

---

## Task 3: One-shot backfill script

**Files:**

- Create: `scripts/backfill_google_directory_student_external_ids.py`

- [ ] **Step 1: Write the PEP 723 backfill script**

  Create the file with the following content:

  ```python
  # /// script
  # requires-python = ">=3.13"
  # dependencies = [
  #     "google-api-python-client",
  #     "google-auth",
  #     "google-cloud-bigquery",
  # ]
  # ///
  """One-shot backfill: set externalIds[type='organization'] on existing student Google accounts.

  Identifies matched student accounts under any /Students/* org unit (including
  /Students/Disabled) whose Workspace externalIds does not already contain an
  'organization' entry equal to the PowerSchool student_number, then PATCHes
  each one. Dry-run by default; pass --apply to execute.

  Usage:
      uv run scripts/backfill_google_directory_student_external_ids.py [--apply]

  Auth: Uses the same service-account key path as the Dagster
  GoogleDirectoryResource. Pass --service-account-file to override.

  Output (stdout): one line per user, plus aggregate counts. Output contains
  student emails and student_numbers; capture only to .claude/scratch/ or
  local terminal. Never paste to PRs, issues, or external surfaces.
  """

  import argparse
  import sys
  import time
  from collections.abc import Iterable, Iterator

  from google.cloud import bigquery
  from google.oauth2 import service_account
  from googleapiclient import discovery

  BQ_PROJECT = "teamster-332318"

  QUERY = """
  select
      u.primary_email,
      se.student_number,
      u.org_unit_path
  from `teamster-332318.kipptaf_google.stg_google_directory__users` as u
  inner join `teamster-332318.kipptaf_students.int_extracts__student_enrollments` as se
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
  """

  SCOPES = ["https://www.googleapis.com/auth/admin.directory.user"]


  def chunks[T](items: list[T], size: int) -> Iterator[list[T]]:
      for i in range(0, len(items), size):
          yield items[i : i + size]


  def build_directory_client(
      service_account_file: str, delegated_account: str
  ) -> discovery.Resource:
      credentials = service_account.Credentials.from_service_account_file(
          service_account_file, scopes=SCOPES
      ).with_subject(delegated_account)
      return discovery.build("admin", "directory_v1", credentials=credentials)


  def fetch_rows() -> list[dict]:
      bq = bigquery.Client(project=BQ_PROJECT)
      return [dict(row) for row in bq.query(QUERY).result()]


  def patch_batch(
      service: discovery.Resource,
      rows: Iterable[dict],
  ) -> tuple[int, list[tuple[str, str]]]:
      """PATCH a batch of users; return (patched_count, [(email, error_message), ...])."""
      patched = 0
      errors: list[tuple[str, str]] = []

      def callback(request_id: str, response, exception) -> None:
          nonlocal patched
          if exception is not None:
              errors.append((request_id, str(exception)))
          else:
              patched += 1

      # trunk-ignore(pyright/reportAttributeAccessIssue)
      batch = service.new_batch_http_request(callback=callback)
      for row in rows:
          body = {
              "externalIds": [
                  {"value": str(row["student_number"]), "type": "organization"}
              ]
          }
          batch.add(
              # trunk-ignore(pyright/reportAttributeAccessIssue)
              service.users().patch(userKey=row["primary_email"], body=body),
              request_id=row["primary_email"],
          )

      batch.execute()
      return patched, errors


  def main() -> int:
      parser = argparse.ArgumentParser(description=__doc__)
      parser.add_argument(
          "--apply",
          action="store_true",
          help="Execute PATCHes. Without this flag, runs dry (prints only).",
      )
      parser.add_argument(
          "--service-account-file",
          default="/workspaces/teamster/env/teamster-332318-48bf4ca46803.json",
          help="Path to service-account JSON key with domain-wide delegation.",
      )
      parser.add_argument(
          "--delegated-account",
          required=True,
          help="Google Workspace admin email to impersonate (same value Dagster uses).",
      )
      parser.add_argument(
          "--batch-size",
          type=int,
          default=50,
          help="PATCHes per batch HTTP request (default 50).",
      )
      parser.add_argument(
          "--sleep-seconds",
          type=float,
          default=1.0,
          help="Sleep between batches to stay under quota (default 1.0s).",
      )
      args = parser.parse_args()

      print(f"Fetching candidate rows from {BQ_PROJECT}...", file=sys.stderr)
      rows = fetch_rows()
      print(f"Found {len(rows)} candidates.", file=sys.stderr)

      if not rows:
          print("Nothing to do.", file=sys.stderr)
          return 0

      if not args.apply:
          print("DRY RUN — no PATCHes will be sent.", file=sys.stderr)
          for row in rows:
              print(
                  f"{row['primary_email']} | {row['student_number']} | would-patch"
              )
          print(f"\nTotal: {len(rows)} would-patch", file=sys.stderr)
          return 0

      service = build_directory_client(
          args.service_account_file, args.delegated_account
      )

      total_patched = 0
      total_errors: list[tuple[str, str]] = []

      batches = list(chunks(rows, args.batch_size))
      for i, batch in enumerate(batches):
          patched, errs = patch_batch(service, batch)
          total_patched += patched
          total_errors.extend(errs)
          for row in batch:
              email = row["primary_email"]
              err = next((e for (k, e) in errs if k == email), None)
              status = "error" if err else "patched"
              print(f"{email} | {row['student_number']} | {status}")
              if err:
                  print(f"  -> {err}", file=sys.stderr)
          if i < len(batches) - 1:
              time.sleep(args.sleep_seconds)

      print(
          f"\nTotal: patched={total_patched} errors={len(total_errors)} "
          f"candidates={len(rows)}",
          file=sys.stderr,
      )
      return 0 if not total_errors else 1


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 2: Smoke-test argument parsing**

  ```bash
  uv run scripts/backfill_google_directory_student_external_ids.py --help
  ```

  Expected: argparse usage block; no import errors.

- [ ] **Step 3: Verify SDK sub-resource attribute exists at runtime**

  Per CLAUDE.md: hasattr / import success does not prove `.users().patch()` is
  callable. Run a tiny in-script smoke test:

  ```bash
  uv run --with google-api-python-client --with google-auth python -c "
  from googleapiclient import discovery
  from google.auth import default
  creds, _ = default()
  svc = discovery.build('admin', 'directory_v1', credentials=creds)
  assert callable(getattr(svc.users(), 'patch', None)), 'patch missing'
  print('users().patch is callable')
  "
  ```

  Expected: `users().patch is callable`. If this errors with `RefreshError` or
  similar auth issue, that's fine — it still proves the attribute path resolves
  (the error happens later, during `.execute()`).

- [ ] **Step 4: Commit**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  git -C . add scripts/backfill_google_directory_student_external_ids.py
  git -C . commit -m "feat(scripts): one-shot backfill for student externalIds

  Refs #3950"
  ```

---

## Task 4: Update `scripts/CLAUDE.md` catalog

**Files:**

- Modify: `scripts/CLAUDE.md`

- [ ] **Step 1: Add the new script to the catalog table**

  In `scripts/CLAUDE.md`, find the script catalog table and append a row in
  alphabetical position (between `audit_marts_yaml.py` and
  `avro-schema-update.py`). The new row:

  ```markdown
  | `backfill_google_directory_student_external_ids.py` | One-shot: backfill
  Workspace `externalIds[type='organization']` for existing student accounts
  (#3950) |
  ```

- [ ] **Step 2: Confirm the user before committing the CLAUDE.md edit**

  Per project rule: present the diff to the user as a quote block and wait for
  approval before applying. (Note for the executing agent: this is the enforced
  gate — do not skip.)

- [ ] **Step 3: Commit (after user approval)**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  git -C . add scripts/CLAUDE.md
  git -C . commit -m "docs(scripts): catalog backfill script

  Refs #3950"
  ```

---

## Task 5: Final verification

- [ ] **Step 1: Full dbt build of modified slice**

  ```bash
  uv run dbt build \
      --select rpt_google_directory__users_import+ \
      --project-dir src/dbt/kipptaf \
      --target dev \
      --defer \
      --state src/dbt/kipptaf/target/prod/
  ```

  Expected: every model + test passes. The `not_null` test on `student_number`
  (where `is_create`) must be green.

- [ ] **Step 2: Confirm no other consumers of the rpt model exist**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  grep -rn "rpt_google_directory__users_import" src/ | grep -v target/
  ```

  Expected: matches only inside
  `src/dbt/kipptaf/models/extracts/google/directory/` and
  `src/teamster/code_locations/kipptaf/google/directory/assets.py`. If any other
  consumer exists, audit whether they need to handle the new `student_number`
  column.

- [ ] **Step 3: Trunk-check changed files**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  .trunk/tools/trunk check --force \
      src/dbt/kipptaf/models/extracts/google/directory/rpt_google_directory__users_import.sql \
      src/dbt/kipptaf/models/extracts/google/directory/properties/rpt_google_directory__users_import.yml \
      src/teamster/code_locations/kipptaf/google/directory/assets.py \
      scripts/backfill_google_directory_student_external_ids.py
  ```

  Expected: "No issues". If sqlfluff / yamllint / ruff flag anything, fix inline
  and re-run before opening the PR.

---

## Task 6: Open the PR

- [ ] **Step 1: Pause and ask the user for PR-creation consent**

  Per project rule: do NOT push or open PRs without explicit user consent in the
  current turn. Surface the branch state (commits, files changed) and ask the
  user whether to open the PR now or hold.

- [ ] **Step 2: Push the branch**

  ```bash
  cd /workspaces/teamster/.worktrees/cbini/feat/claude-google-directory-student-external-ids
  git -C . push -u origin cbini/feat/claude-google-directory-student-external-ids
  ```

- [ ] **Step 3: Open the PR**

  Use `gh pr create` with `.github/pull_request_template.md` as the body
  template. PR body MUST include `Refs #3950` so the project board auto-links.

  Title:
  `feat(google-directory): set student_number as externalId on user create`

  Body (template-filled):

  ```markdown
  ## Summary

  - Surfaces PowerSchool `student_number` on
    `rpt_google_directory__users_import` with a `not_null` test scoped to create
    rows.
  - Updates `google_directory_user_create` to attach
    `externalIds[type='organization']` before `batch_insert_users`, and
    `google_directory_user_update` to pop the column so the recurring update
    path never touches `externalIds`.
  - Adds `scripts/backfill_google_directory_student_external_ids.py` — a
    one-shot PEP 723 script that PATCHes existing matched student accounts
    (including `/Students/Disabled`) whose Workspace `externalIds` lacks the
    organization entry.

  Refs #3950. Follow-up #4057 will add uniqueness contracts to the rpt model
  after the backfill has run.

  ## Test plan

  - [x] Local `dbt build --select rpt_google_directory__users_import+` — model +
        `not_null` test pass.
  - [x] BQ spot-check: every `is_create` row has non-null `student_number`.
  - [x] `python -c "import teamster.code_locations.kipptaf.google.directory.assets"`
        — clean import.
  - [x] `scripts/backfill_google_directory_student_external_ids.py --help` —
        argparse OK.
  - [ ] After merge: run backfill `--apply` in Codespace, re-materialize `users`
        asset, spot-check 5–10 students for `externalIds.organization`.
  - [ ] After merge: pick up #4057 for uniqueness tests.
  ```

---

## Post-merge (manual — not part of plan execution)

These steps belong to the rollout sequence in the spec; the engineer running
this plan does not execute them. They are listed here so the spec's rollout is
referenced from the plan.

1. Wait for the next prod materialization of the `users` asset so
   `stg_google_directory__users` reflects the latest `externalIds`.
2. Run
   `uv run scripts/backfill_google_directory_student_external_ids.py --delegated-account <admin> --apply`
   from a Codespace terminal. Capture stdout to `.claude/scratch/` (PII).
3. Re-materialize the `users` asset; spot-check `/Students/*` accounts in BQ for
   `externalIds.organization`.
4. Pick up #4057 (uniqueness tests).
5. Close #3950.
