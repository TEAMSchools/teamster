# Focus Student Contacts — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Focus-side student contacts models (`stg_focus__people`,
`int_focus__student_contacts`) plus inert kipptaf plumbing, per the approved
spec ([#4585](https://github.com/TEAMSchools/teamster/issues/4585),
`docs/superpowers/specs/2026-07-28-focus-student-contacts-design.md`).

**Architecture:** New staging + intermediate models in the `focus` source
package (built by `kippmiami`), consumed by kipptaf via `source()` + a thin
`union_relations` wrapper. No consumer changes — `int_students__contacts` is
untouched until Phase 2.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, trunk (sqlfluff/sqlfmt/yamllint).

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts`
  (branch `cbini/feat/claude-focus-student-contacts`). Every file
  Read/Edit/Write MUST target the worktree path; every git call MUST use
  `git -C <worktree>`.
- dbt commands run through the consuming district:
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/kippmiami` (or
  `.../kipptaf`), with
  `--defer --state /workspaces/teamster/src/dbt/<project>/target/prod` (absolute
  path — the worktree has no `target/prod`).
- Follow `src/dbt/CLAUDE.md` SQL conventions: max 1 level of function nesting,
  no `ORDER BY`/`QUALIFY`/subqueries, ST06 column ordering (plain refs grouped
  by source table, then constants, then functions, then logicals/windows),
  trailing commas, no pass-through import CTEs.
- Focus soft-delete: `where deleted is null` (never `= 0`).
- The Focus contact tables hold ~1 row today — builds succeed with tiny row
  counts; that is expected, not a failure.
- Commit messages use conventional commits and end with the
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer. Bodies
  reference `Refs #4585`.
- Do NOT run `trunk fmt` manually; the pre-commit hook formats. Verify lint with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  run with cwd INSIDE the worktree.

---

### Task 0: Worktree dbt setup

**Files:** none (environment only)

**Interfaces:**

- Consumes: existing worktree at
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts`.
- Produces: installed `dbt_packages/` for `kippmiami` and `kipptaf` in the
  worktree, required by every later build step.

- [ ] **Step 1: Install dbt packages in the worktree**

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kipptaf
```

Expected: both finish with "Installed" lines, no errors.

- [ ] **Step 2: Sanity-parse kippmiami**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami
```

Expected: parse completes without errors.

---

### Task 1: `stg_focus__people`

**Files:**

- Create: `src/dbt/focus/models/staging/stg_focus__people.sql`
- Create: `src/dbt/focus/models/staging/properties/stg_focus__people.yml`

(Both paths relative to the worktree root. The `people` table is already
declared in `src/dbt/focus/models/staging/sources-bigquery.yml` — no source
change needed.)

**Interfaces:**

- Consumes: `source("focus", "people")` (dlt-loaded;
  `dagster_kippmiami_dlt_focus.people`).
- Produces: `ref("stg_focus__people")` with columns `person_id` (int PK),
  `title`, `first_name`, `middle_name`, `last_name`, `email`, `email_opt_out`,
  `birthdate` (date), `education_level` (int), `primary_language` (int),
  `imported`, `people_import_key`, `uuid`, `created_at`/`updated_at`
  (timestamps). Task 2 joins it on `person_id`.

- [ ] **Step 1: Write the staging model SQL**

Write `src/dbt/focus/models/staging/stg_focus__people.sql` (worktree path):

```sql
select
    person_id,
    title,
    first_name,
    middle_name,
    last_name,
    email,
    email_opt_out,
    birthdate,
    education_level,
    primary_language,
    imported,
    people_import_key,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "people") }}
where deleted is null
```

- [ ] **Step 2: Write the properties yml**

Write `src/dbt/focus/models/staging/properties/stg_focus__people.yml` (worktree
path). Staging is contract-enforced at the directory level, so every column
needs `data_type`:

```yaml
models:
  - name: stg_focus__people
    description: >-
      Focus people — one row per live person record (deleted rows excluded),
      keyed on person_id. People are the guardians/contacts linked to students
      through students_join_people; their phone/email detail rows live in
      people_join_contacts. The free-text notes column and the audit
      (created_by/updated_by) columns are intentionally omitted — notes is
      unneeded sensitive free text, and the audit columns are dropped across
      this package's staging layer.
    columns:
      - name: person_id
        description: Primary key — Focus person id.
        data_type: int
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: title
        description: Salutation / name title for the person (rarely populated).
        data_type: string
      - name: first_name
        description: Person first name.
        data_type: string
        config:
          meta:
            contains_pii: true
      - name: middle_name
        description: Person middle name.
        data_type: string
        config:
          meta:
            contains_pii: true
      - name: last_name
        description: Person last name.
        data_type: string
        config:
          meta:
            contains_pii: true
      - name: email
        description: Person email address.
        data_type: string
        config:
          meta:
            contains_pii: true
      - name: email_opt_out
        description: Y-flag — the person opted out of email communication.
        data_type: string
      - name: birthdate
        description: Person date of birth.
        data_type: date
        config:
          meta:
            contains_pii: true
      - name: education_level
        description: Focus education-level code id for the person.
        data_type: int
      - name: primary_language
        description: Focus language code id for the person's primary language.
        data_type: int
      - name: imported
        description: Y-flag — the record arrived via a Focus import job.
        data_type: string
      - name: people_import_key
        description: Import-batch key assigned when the record was imported.
        data_type: string
      - name: uuid
        description: Focus-internal UUID for the record.
        data_type: string
      - name: created_at
        description: Record creation timestamp in Focus.
        data_type: timestamp
      - name: updated_at
        description: Record last-update timestamp in Focus.
        data_type: timestamp
```

- [ ] **Step 3: Build the model and its tests**

```bash
uv run dbt build --select stg_focus__people --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: model builds (1 row today — expected), contract passes, `unique` +
`not_null` tests PASS.

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/staging/stg_focus__people.sql src/dbt/focus/models/staging/properties/stg_focus__people.yml </dev/null
```

Expected: no issues (formatting autofixes at commit are fine).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts add src/dbt/focus/models/staging/stg_focus__people.sql src/dbt/focus/models/staging/properties/stg_focus__people.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts commit -m "feat(dbt): add stg_focus__people staging model

Refs #4585

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `int_focus__student_contacts` + unmapped-title guard test

**Files:**

- Create: `src/dbt/focus/models/intermediate/int_focus__student_contacts.sql`
- Create:
  `src/dbt/focus/models/intermediate/properties/int_focus__student_contacts.yml`
- Create: `src/dbt/focus/tests/focus_unmapped_phone_contact_titles.sql`
- Create: `src/dbt/focus/tests/properties.yml`

**Interfaces:**

- Consumes: `ref("stg_focus__students_join_people")` (link grain: `id` PK,
  `student_id`, `person_id`, `address_id`, `student_relation`, `sort_order`
  NUMERIC, `custody`/`emergency`/`pick_up`/`reunification` as `'Y'`/null
  strings), `ref("stg_focus__people")` (Task 1),
  `ref("stg_focus__people_join_contacts")` (`person_id`, `title`, `value`,
  `detail_priority`), `ref("stg_focus__address")` (`address_id`, `address`,
  `address2`, `city`, `state`, `zipcode`),
  `ref("stg_focus__students_join_address")` (`student_id`, `address_id`),
  `ref("stg_focus__students")` (`student_id`, `local_student_id`), and the
  `finalsite` package's `clean_phone` macro (package-qualified — `kippmiami`
  installs both packages).
- Produces: `int_focus__student_contacts` at grain `student_id x person_id` with
  columns: `student_id`, `person_id`, `local_student_id`, `relationship`,
  `sort_order`, `is_custodial`, `is_emergency`, `is_pickup`, `is_reunification`,
  `is_household_member` (all boolean, null-preserving), `contact_name`,
  `contact_first_name`, `contact_last_name`, `email`, `phone_mobile`,
  `phone_home`, `phone_work`, `phone_daytime`, `phone_primary` (E.164-cleaned),
  `home_address`. This is the exact surface the Phase 2 kipptaf swap consumes.

- [ ] **Step 1: Write the intermediate model SQL**

Write `src/dbt/focus/models/intermediate/int_focus__student_contacts.sql`
(worktree path):

```sql
with
    -- normalize the Y/null flags once; null is preserved as "unmaintained in
    -- Focus" (the Finalsite import seeds these as null; registrars set them)
    links as (
        select
            student_id,
            person_id,
            address_id,
            sort_order,

            student_relation as relationship,

            custody = 'Y' as is_custodial,
            emergency = 'Y' as is_emergency,
            pick_up = 'Y' as is_pickup,
            reunification = 'Y' as is_reunification,
        from {{ ref("stg_focus__students_join_people") }}
    ),

    people as (
        select
            person_id,
            first_name as contact_first_name,
            last_name as contact_last_name,
            email,

            array_to_string([first_name, last_name], ' ') as contact_name,
        from {{ ref("stg_focus__people") }}
    ),

    -- contact detail rows are free-typed by title; map to the phone-type
    -- vocabulary shared with the Finalsite contacts intermediate. Unmapped
    -- titles are surfaced by the focus_unmapped_phone_contact_titles test.
    phones as (
        select
            person_id,
            value,
            detail_priority,

            case
                when regexp_contains(lower(title), r'cell|mobile')
                then 'mobile'
                when regexp_contains(lower(title), r'home')
                then 'home'
                when regexp_contains(lower(title), r'work|business|office')
                then 'work'
                when regexp_contains(lower(title), r'day')
                then 'daytime'
            end as phone_type,
        from {{ ref("stg_focus__people_join_contacts") }}
    ),

    phones_ranked as (
        select
            person_id,
            value,
            phone_type,

            row_number() over (
                partition by person_id, phone_type
                order by detail_priority asc nulls last
            ) as type_rank,

            row_number() over (
                partition by person_id
                order by detail_priority asc nulls last
            ) as overall_rank,
        from phones
        where phone_type is not null
    ),

    phones_typed as (
        select
            person_id,

            max(if(phone_type = 'mobile', value, null)) as phone_mobile,
            max(if(phone_type = 'home', value, null)) as phone_home,
            max(if(phone_type = 'work', value, null)) as phone_work,
            max(if(phone_type = 'daytime', value, null)) as phone_daytime,
            max(if(overall_rank = 1, value, null)) as phone_primary,
        from phones_ranked
        where type_rank = 1
        group by person_id
    ),

    addresses as (
        select
            address_id,

            nullif(
                array_to_string([address, address2, city, state, zipcode], ', '),
                ''
            ) as home_address,
        from {{ ref("stg_focus__address") }}
    ),

    -- grain projection: one row per (student, address) the student resides at
    student_addresses as (
        select student_id, address_id,
        from {{ ref("stg_focus__students_join_address") }}
        group by student_id, address_id
    )

select
    l.student_id,
    l.person_id,
    l.relationship,
    l.sort_order,
    l.is_custodial,
    l.is_emergency,
    l.is_pickup,
    l.is_reunification,

    s.local_student_id,

    p.contact_name,
    p.contact_first_name,
    p.contact_last_name,
    p.email,

    a.home_address,

    {{ finalsite.clean_phone("pt.phone_mobile") }} as phone_mobile,
    {{ finalsite.clean_phone("pt.phone_home") }} as phone_home,
    {{ finalsite.clean_phone("pt.phone_work") }} as phone_work,
    {{ finalsite.clean_phone("pt.phone_daytime") }} as phone_daytime,
    {{ finalsite.clean_phone("pt.phone_primary") }} as phone_primary,

    if(
        l.address_id is null, null, sa.address_id is not null
    ) as is_household_member,
from links as l
inner join {{ ref("stg_focus__students") }} as s on l.student_id = s.student_id
left join people as p on l.person_id = p.person_id
left join phones_typed as pt on l.person_id = pt.person_id
left join addresses as a on l.address_id = a.address_id
left join
    student_addresses as sa
    on l.student_id = sa.student_id
    and l.address_id = sa.address_id
```

- [ ] **Step 2: Write the properties yml**

Write
`src/dbt/focus/models/intermediate/properties/int_focus__student_contacts.yml`
(worktree path). Intermediates are not contract-enforced — no `data_type`
needed:

```yaml
models:
  - name: int_focus__student_contacts
    description: >-
      Focus student contacts — one row per live student-to-person link
      (students_join_people), enriched with the person's name and email, typed
      phone numbers pivoted from people_join_contacts, the link's address, and
      household membership (the link address matches one of the student's own
      addresses). Unslotted and uncapped by design — contact_slot assignment
      (contact_1 / emergency_N) happens at the kipptaf reporting layer. Flag
      booleans are null-preserving — null means the flag is unmaintained in
      Focus, not false. Internal-only; a rpt_ view must sit between this model
      and any external consumer.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_id
              - person_id
          config:
            severity: error
    columns:
      - name: student_id
        description: Focus student id (links to stg_focus__students).
        config:
          meta:
            contains_pii: true
      - name: person_id
        description: Focus person id of the contact.
        config:
          meta:
            contains_pii: true
      - name: relationship
        description:
          Contact relationship to the student (student_relation, e.g. Guardian).
      - name: sort_order
        description: >-
          Contact ordering within the student, lowest first. Import-seeded rows
          rank the primary caregiver 1.
      - name: is_custodial
        description: >-
          Whether the contact has custody. Null-preserving — null means
          unmaintained in Focus.
      - name: is_emergency
        description: >-
          Whether the contact is an emergency contact. Null-preserving — null
          means unmaintained in Focus.
      - name: is_pickup
        description: >-
          Whether the contact may pick the student up. Null-preserving — null
          means unmaintained in Focus.
      - name: is_reunification
        description: >-
          Whether the contact is a reunification contact. Null-preserving — null
          means unmaintained in Focus.
      - name: local_student_id
        description:
          KIPP local student id from the Focus student record (custom_53).
        config:
          meta:
            contains_pii: true
      - name: contact_name
        description: Contact full name (first + last).
        config:
          meta:
            contains_pii: true
      - name: contact_first_name
        description: Contact first name.
        config:
          meta:
            contains_pii: true
      - name: contact_last_name
        description: Contact last name.
        config:
          meta:
            contains_pii: true
      - name: email
        description: Contact email address.
        config:
          meta:
            contains_pii: true
      - name: home_address
        description: >-
          Contact home address assembled from the link's address record (street,
          unit, city, state, zip).
        config:
          meta:
            contains_pii: true
      - name: phone_mobile
        description: Contact mobile/cell phone, normalized to E.164.
        config:
          meta:
            contains_pii: true
      - name: phone_home
        description: Contact home phone, normalized to E.164.
        config:
          meta:
            contains_pii: true
      - name: phone_work
        description: Contact work phone, normalized to E.164.
        config:
          meta:
            contains_pii: true
      - name: phone_daytime
        description: Contact daytime phone, normalized to E.164.
        config:
          meta:
            contains_pii: true
      - name: phone_primary
        description: >-
          Contact primary phone — the highest-priority (lowest detail_priority)
          phone-typed contact detail, normalized to E.164.
        config:
          meta:
            contains_pii: true
      - name: is_household_member
        description: >-
          Whether the contact's linked address matches one of the student's own
          addresses. Null when the link carries no address.
```

- [ ] **Step 3: Write the unmapped-title guard test**

Write `src/dbt/focus/tests/focus_unmapped_phone_contact_titles.sql` (worktree
path). It fails (warn) when a `people_join_contacts` title doesn't match the
phone-type mapping in the intermediate — new contact types get flagged instead
of silently dropped:

```sql
-- Focus contact-detail titles are free-typed; the phone pivot in
-- int_focus__student_contacts maps them by regex. Warn on any title that maps
-- to no phone type so a new contact type is surfaced, not silently dropped.
-- Email-shaped titles are expected to be unmapped and are excluded.
select title, count(*) as n,
from {{ ref("stg_focus__people_join_contacts") }}
where
    not regexp_contains(
        lower(title), r'cell|mobile|home|work|business|office|day'
    )
    and not regexp_contains(lower(title), r'e-?mail')
group by title
```

- [ ] **Step 4: Write the singular-test properties yml**

Write `src/dbt/focus/tests/properties.yml` (worktree path). The
`meta.dagster.ref` needs `package: focus` (source-system package test):

```yaml
data_tests:
  - name: focus_unmapped_phone_contact_titles
    description: >-
      Warns when a people_join_contacts title matches none of the phone-type
      regexes used by int_focus__student_contacts, so a newly-introduced Focus
      contact type is surfaced instead of silently dropped from the phone pivot.
    config:
      meta:
        dagster:
          ref:
            name: stg_focus__people_join_contacts
            package: focus
```

If `src/dbt/focus/tests/` already has a `properties.yml` (it should not — the
directory does not exist today), append the test entry instead of overwriting.

- [ ] **Step 5: Build the model and all its tests**

```bash
uv run dbt build --select int_focus__student_contacts focus_unmapped_phone_contact_titles --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: model builds (~1 row today — expected), grain test PASS, singular test
PASS or WARN (a warn is acceptable; note any surfaced titles).

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/focus/models/intermediate/int_focus__student_contacts.sql src/dbt/focus/models/intermediate/properties/int_focus__student_contacts.yml src/dbt/focus/tests/focus_unmapped_phone_contact_titles.sql src/dbt/focus/tests/properties.yml </dev/null
```

Expected: no issues.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts add src/dbt/focus/models/intermediate/int_focus__student_contacts.sql src/dbt/focus/models/intermediate/properties/int_focus__student_contacts.yml src/dbt/focus/tests/focus_unmapped_phone_contact_titles.sql src/dbt/focus/tests/properties.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts commit -m "feat(dbt): add int_focus__student_contacts intermediate

One row per live student-person link, unslotted; contact_slot shaping
happens at the kipptaf layer in Phase 2. Refs #4585

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: kipptaf source entry + union wrapper (inert)

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` (append one table
  entry)
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_contacts.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_contacts.yml`

**Interfaces:**

- Consumes: the kippmiami-built `int_focus__student_contacts` (Task 2) via
  `source("kippmiami_focus", "int_focus__student_contacts")`.
- Produces: kipptaf model `int_focus__student_contacts` — Task 2's columns plus
  `_dbt_source_relation` and `_dbt_source_project`. This is the model the Phase
  2 swap will `ref()` from `int_students__contacts`. Nothing consumes it in this
  PR.

- [ ] **Step 1: Append the source table entry**

In `src/dbt/kipptaf/models/focus/sources-kippmiami.yml` (worktree path), append
to the `tables:` list, matching the existing entries exactly:

```yaml
- name: int_focus__student_contacts
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__student_contacts
```

- [ ] **Step 2: Write the wrapper SQL**

Write
`src/dbt/kipptaf/models/focus/intermediate/int_focus__student_contacts.sql`
(worktree path), following `int_focus__school_year_first_day.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__student_contacts"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 3: Write the wrapper properties yml**

Write
`src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_contacts.yml`
(worktree path):

```yaml
models:
  - name: int_focus__student_contacts
    description: >-
      Kipptaf-level union_relations passthrough of kippmiami's
      int_focus__student_contacts, following the same pattern as
      int_focus__school_year_first_day. Focus is Miami-only today; this shape
      lets a future region's Focus ingestion union in without a rewrite. Column
      docs/tests live on the kippmiami source model. Unconsumed until the Phase
      2 int_students__contacts swap (see issue 4585).
    columns:
      - name: _dbt_source_project
        description: District code location derived from _dbt_source_relation.
```

- [ ] **Step 4: Build the wrapper against the dev copy**

The wrapper's source resolves to the dev-prefixed schema
(`zz_<user>_kippmiami_focus`), which Task 2's build populated:

```bash
uv run dbt build --select int_focus__student_contacts --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kipptaf --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod --target dev
```

Expected: view builds; `union_relations` resolves the column set from the dev
relation.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/focus/sources-kippmiami.yml src/dbt/kipptaf/models/focus/intermediate/int_focus__student_contacts.sql src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_contacts.yml </dev/null
```

Expected: no issues.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts add src/dbt/kipptaf/models/focus/sources-kippmiami.yml src/dbt/kipptaf/models/focus/intermediate/int_focus__student_contacts.sql src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts commit -m "feat(dbt): add kipptaf int_focus__student_contacts wrapper

Inert until the Phase 2 int_students__contacts swap. Refs #4585

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Full verification + CI staging prep

**Files:** none created; verification only.

**Interfaces:**

- Consumes: everything from Tasks 1-3.
- Produces: a verified, lint-clean branch ready for PR, plus the staging-seed
  handoff the PR needs before dbt Cloud CI can pass.

- [ ] **Step 1: Full selective build of the new chain**

```bash
uv run dbt build --select stg_focus__people+ --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod --target dev
```

Expected: `stg_focus__people`, `int_focus__student_contacts`, and all their
tests PASS (kippmiami side; the kipptaf wrapper was built in Task 3).

- [ ] **Step 2: Lint every changed file at once**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts && git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts diff --name-only origin/main...HEAD | xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Expected: no issues.

- [ ] **Step 3: CI staging seed — STOP, hand to the user**

Editing `sources-kippmiami.yml` marks the whole `kippmiami_focus` source
`state:modified`, so dbt Cloud CI (`state:modified+`) rebuilds every kipptaf
model reading it (the `stg_focus__*` wrappers and both `int_focus__*` wrappers).
Those reads resolve to `zz_stg_kippmiami_focus`, which does not yet contain the
NEW models. Before (or right after) opening the PR, the staged copies must be
seeded. **These commands recreate shared `zz_stg_*` tables — the auto-classifier
requires the user to run or explicitly authorize them.** Present this block to
the user; do not run it without their direct authorization:

```bash
# seed unchanged kippmiami focus models from prod
uv run dbt clone --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami --target staging --state /workspaces/teamster/src/dbt/kippmiami/target/prod --full-refresh
# build the NEW models into the staged schema (clone can't — they're not in prod)
uv run dbt build --select stg_focus__people int_focus__student_contacts --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-student-contacts/src/dbt/kippmiami --target staging
```

- [ ] **Step 4: Report status**

Summarize for the user: models built, tests passing, lint clean, staging seed
status, and that the branch is ready for a PR (use
superpowers:finishing-a-development-branch — squash merge, PR body from
`.github/pull_request_template.md`, `Refs #4585`).

---

## Out of scope for this plan (Phase 2, separate plan)

- Swapping the PowerSchool branch of `int_students__contacts` and slotting.
- Retiring kipptaf `int_powerschool__contacts` and the frozen contacts source
  entries.
- Downstream verification of `dim_student_contact_persons` /
  `bridge_student_contacts` / extracts.

Phase 2 is gated on the Finalsite contacts import landing in Focus (link count
in `students_join_people` on the order of enrolled students, ~4k).
