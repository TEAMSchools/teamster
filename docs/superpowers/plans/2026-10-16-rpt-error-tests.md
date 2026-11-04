# Non-Tableau `rpt_` error tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every test on a kipptaf `rpt_` model under `models/extracts/` (outside
`tableau/`) runs at `error`, backed by upstream `warn` tests and defenses for
the 5 that fail in prod today.

**Architecture:** One `extracts: +severity: error` folder block replaces the
`tableau:` block. The 5 prod failures are source-data defects. Each one gets a
`warn` on the earliest model that sees it, plus a defense in an allowed layer.
Then its `rpt_` test can run at `error`.

**Tech Stack:** dbt (BigQuery), kipptaf project plus the `finalsite` source
package.

**Spec:** none. Rulings settled in conversation and recorded below; #5948 is the
tracking issue (`Refs #5948`, no new issue). PR 5 precedent:
`docs/superpowers/plans/2026-10-16-tableau-rpt-error-tests.md`.

## Global Constraints

- Rule: `.claude/rules/dbt-yaml.md` _Test config defaults_. A source-data defect
  gets a `warn` on the earliest model that sees it, with a description naming
  the source system, what is wrong, and what to change there.
- A5: a dedupe or pick lives only in `stg_` or a source `int_`.
- An `error` test lands only after its query returns 0 rows in prod.
- `finalsite` is a source package: its tests default to `error`, so every new
  `warn` there sets `config: severity: warn` explicitly.
- Prod-deferred flags:
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod`.
- Always `uv run dbt`. Stage with `git add -u` (plus `git add <new file>`).

## Rulings (decided with the user)

1. One `extracts: +severity: error` block replaces `extracts: tableau:`. The
   `int_` tests under `extracts/` that resolve to `warn` today are pinned to
   `warn`.
2. The 7 ParentSquare file-to-file `relationships` tests and the 2 ParentSquare
   and 3 Clever "resolves"-style singular tests stay. They are a recorded
   exception for outbound-feed integrity, named in one line in `dbt-yaml.md`.
3. `accepted_values`: keep a test when the model's logic produces the values.
   Move it upstream when the values come from upstream.
   - The 4 `csgf_hs_enrollment` Y/N tests stay. The model's `if()` and
     `coalesce()` produce them.
   - The `kippfwd_miami_roster.iep_status` test moves to
     `int_extracts__student_enrollments.iep_status` at `error`. That model
     produces the label, and prod holds only `Has IEP` and `No IEP`. The `rpt_`
     `not_null` goes too, because a `coalesce` makes the column non-null by
     construction.
   - The Ignite `course_grade` A-F test is deleted. PowerSchool letter grades
     legitimately include other codes. The model's `case` maps anything outside
     A-D to not passing, so an upstream `warn` would fire on valid data.
4. The 5 prod failures get these defenses:
   - Coupa duplicate active addresses: flag the newest active `id` per name in
     `stg_coupa__addresses`, and join on that flag. Ops (Greg Giles) confirmed
     both addresses are active on purpose while buildings move. The fix in Coupa
     is to rename the old building's address.
   - More than 1 matriculated application: use the existing
     `base_kippadb__application.rn_app_enr` pick, as
     `rpt_tableau__kfwd_dashboard` does. Anthony Walters is confirming the rule
     (Asana task 1219594691444482).
   - DeansList `Relationship` null (Finalsite emergency contacts): fill
     `Unknown`.
   - Focus emergency contact with no last name: drop the row, matching the
     existing blank-first-name filter.
5. Delete `test_kippfwd_miami_roster_current_year_not_empty`. It tests build
   timing (data presence), not a regression.
6. Grain backfill for `rpt_` models with no grain test goes to a follow-up PR.

## Review Focus

- A Coupa address name with an active and an inactive row: the flag must land on
  the active one, even when the inactive row has the higher `id`.
- A student with 1 transfer and 1 non-transfer matriculated application: the
  CSGF join must keep only the non-transfer one.
- An emergency contact with a first name and an empty-string (not NULL) last
  name: it must be dropped like a NULL.
- An `int_` test under `extracts/` that resolves to `warn` today and has no
  explicit severity: the folder block must not flip it.
- A test whose `warn` override is removed: it must still pass in prod.

---

### Task 1: Coupa address dedupe

**Files:**

- Modify: `src/dbt/kipptaf/models/coupa/api/staging/stg_coupa__addresses.sql`
- Modify:
  `src/dbt/kipptaf/models/coupa/api/staging/properties/stg_coupa__addresses.yml`
- Modify: `src/dbt/kipptaf/models/extracts/coupa/rpt_coupa__users.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/coupa/properties/rpt_coupa__users.yml`

No kipptaf source carries a data test, so the early `warn` goes on the staging
model. Staging keeps every row and flags the pick (`is_current_for_name`), so
that `warn` still sees the duplicates.

- [ ] **Step 1:** In `stg_coupa__addresses.yml`: - Add `unique` on `id`
      (`severity: error`). - Add `unique` on `name` with
      `config: {where: active, severity: warn}`. Its description says 2 active
      Coupa addresses share a name, usually during a building move, and the fix
      is to rename the old building's address in Coupa. - Add `unique` on `name`
      with `config: {where: is_current_for_name, severity: error}`.
- [ ] **Step 2:** Run
      `uv run dbt build --select stg_coupa__addresses <prod-deferred flags>`.
      Expected: the build fails because `is_current_for_name` does not exist.
- [ ] **Step 3:** In `stg_coupa__addresses.sql`, add `is_current_for_name`
      (bool). It is true for the active row with the highest `id` per `name`,
      and false for every other row: a `row_number()` partitioned by `name` over
      active rows, ordered by `id desc`, then `active and rn = 1` in the next
      CTE. Add model and column descriptions to the yml. The column description
      states the newest-id rule.
- [ ] **Step 4:** Re-run Step 2. Expected: the active-name `warn` WARNs on 3
      names. The `is_current_for_name` `unique` passes.
- [ ] **Step 5:** In `rpt_coupa__users.sql`, change the address join
      `and a.active` to `and a.is_current_for_name`. In `rpt_coupa__users.yml`,
      remove `severity: warn` and the `TODO(#4409)` comments from both `unique`
      tests and set `severity: error`. Run
      `uv run dbt build --select rpt_coupa__users <prod-deferred flags>`.
      Expected: both `unique` tests PASS.
- [ ] **Step 6:** Commit:
      `fix(coupa): send one default address per user to Coupa`.

### Task 2: CSGF matriculated application

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__csgf_hs_postsec_pathways.sql`
- Modify: the `base_kippadb__application` properties yml

- [ ] **Step 1:** On `base_kippadb__application`, add a `warn` test: `unique` on
      `applicant` with `config: {where: is_matriculated, severity: warn}`. Its
      description says some students have more than 1 application marked
      Matriculated (Intent to Enroll) in Salesforce, that consumers pick 1 by
      `rn_app_enr`, and that KIPP Forward should leave only 1 marked.
- [ ] **Step 2:** In the CSGF join, add
      `and not app.transfer_application and app.rn_app_enr = 1`.
- [ ] **Step 3:** Run
      `uv run dbt build --select rpt_gsheets__csgf_hs_postsec_pathways <prod-deferred flags>`.
      Expected: the grain test passes. The row count equals the 12th-grade
      `rn_year = 1` count.
- [ ] **Step 4:** Commit:
      `fix(dbt): pick one matriculated application for CSGF pathways`.

### Task 3: Finalsite contact defenses (DeansList and Focus)

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_custom_attributes.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
  and its properties yml
- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql` and
  its properties yml

- [ ] **Step 1:** In the package, add `not_null` on
      `int_finalsite__student_contacts.relationship` with
      `config: {severity: warn}`. The description says a Finalsite emergency
      contact is missing its relationship (`emrg_N_relationship`), and that the
      fix is to fill it in Finalsite.
- [ ] **Step 2:** In the package, add a model-level
      `dbt_utils.expression_is_true` on
      `int_finalsite__contact_custom_attributes` with `severity: warn`. It is
      false when any of `emrg_1` to `emrg_4` has a non-blank first name and a
      blank or NULL last name. The description says the fix is to fill in the
      last name in Finalsite.
- [ ] **Step 3:** In `rpt_deanslist__family_contacts.sql`, select
      `coalesce(c.relationship, 'Unknown') as Relationship`. Delete the column's
      `not_null`: the `coalesce` makes it non-null by construction. Add a
      unit-test case with a NULL relationship that expects `Unknown`. Run the
      model's unit tests and watch the new case fail before the SQL change and
      pass after it.
- [ ] **Step 4:** In each of the 4 emergency branches of `rpt_focus__contacts`,
      add
      `and a.emrg_N_name_last_name is not null and a.emrg_N_name_last_name != ''`.
      Add a unit-test case with an empty-string last name that expects no row.
      Watch it fail, then pass. Then run
      `uv run dbt test --select "test_type:unit,extracts.focus"`.
- [ ] **Step 5:** Run
      `uv run dbt build --select rpt_deanslist__family_contacts rpt_focus__contacts <prod-deferred flags>`.
      Expected: `Relationship` has no `not_null` test, and the `last_name`
      `not_null` passes.
- [ ] **Step 6:** Commit:
      `fix(dbt): defend DeansList and Focus contact feeds against Finalsite gaps`.

### Task 4: Accepted values and singular tests

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/properties/rpt_gsheets__kippfwd_miami_roster.yml`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/ignite/properties/rpt_ignite__course_level.yml`
- Delete:
  `src/dbt/kipptaf/tests/test_kippfwd_miami_roster_current_year_not_empty.sql`
  and its `tests/properties.yml` entry
- Modify: `.claude/rules/dbt-yaml.md` (the `relationships` bullet)

- [ ] **Step 1:** Move the `iep_status` `accepted_values` (`Has IEP`, `No IEP`)
      and its `not_null` to `int_extracts__student_enrollments.iep_status` with
      `severity: error`. Delete both tests from the roster yml. Move the column
      to the top of the `columns:` list.
- [ ] **Step 2:** Delete the Ignite `course_grade` `accepted_values`.
- [ ] **Step 3:** Delete the kippfwd singular test and its properties entry.
- [ ] **Step 4:** Add to the `dbt-yaml.md` `relationships` bullet: "Exception:
      an outbound feed whose rows reference another feed's file (ParentSquare,
      Clever) keeps its file-to-file check, because the target system rejects a
      dangling id."
- [ ] **Step 5:** Run
      `uv run dbt test --select int_extracts__student_enrollments,column:iep_status <prod-deferred flags>`.
      Expected: PASS.
- [ ] **Step 6:** Commit: `test(dbt): sort extract accepted_values tests`.

### Task 5: Folder severity

**Files:**

- Modify: `src/dbt/kipptaf/dbt_project.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__student_enrollment.yml`
- Modify:
  `src/dbt/kipptaf/models/extracts/ignite/intermediate/properties/int_ignite__treatment_assignment.yml`

- [ ] **Step 1:** Parse main and the branch with `--no-partial-parse`. Save each
      test's resolved severity for everything under `models/extracts/` and the
      extract singular tests.
- [ ] **Step 2:** Replace `extracts: tableau: +severity: error` with
      `extracts: +severity: error`. Remove the `severity: warn` overrides on
      `syear` and `grade_id` in `rpt_focus__student_enrollment.yml`. Pin
      `severity: warn` on the `int_ignite__treatment_assignment` `relationships`
      test.
- [ ] **Step 3:** Re-parse and diff. Expected: every `rpt_` test is `error`.
      `int_ignite__attendance` and `int_ignite__treatment_assignment` stay
      `warn`. Removed nodes are exactly the ones Tasks 3 and 4 deleted. Added
      nodes are exactly the ones Tasks 1-4 added.
- [ ] **Step 4:** Run the prod-deferred test run over all extracts outside
      `tableau/`, plus the upstream models touched in Tasks 1-4. Expected:
      `ERROR=0`, and `WARN` only on the new upstream `warn` tests.
- [ ] **Step 5:** Lint every touched SQL, YAML, and markdown file with
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- [ ] **Step 6:** Commit: `test(dbt): run non-Tableau extract tests at error`.
