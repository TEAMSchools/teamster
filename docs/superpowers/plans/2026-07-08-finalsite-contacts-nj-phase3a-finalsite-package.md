# Finalsite NJ Contacts — Phase 3a (Finalsite Package Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Subagents doing dbt work MUST first
> invoke `Skill` with skill `dbt:using-dbt-for-analytics-engineering`.

**Goal:** Build the SIS-agnostic 1+4 contact foundation in the `finalsite` dbt
package: extend the `custom_attributes` PIVOT with Newark's emergency fields,
and add `int_finalsite__student_contacts` (one row per student × contact slot:
`contact_1` + `emergency_1..4`).

**Architecture:** All models live in the `finalsite` package `api/` layer
(SIS-agnostic — no PowerSchool refs, no `student_number` join; that happens in
Phase 3b at kipptaf). The `api/` layer is enabled only where Finalsite contacts
ingestion is wired — today Newark (this plan) once its `api`/source gates flip.
Miami's `api/` custom_attributes columns are consumed by its Focus extracts, so
the PIVOT extension is strictly **additive**.

**Tech Stack:** dbt (BigQuery), the `finalsite` package built via a consuming
district project-dir (`kippnewark`).

## Global Constraints

- **Worktree:**
  `/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt`.
  `git -C <worktree>` on every git call;
  `uv run dbt ... --project-dir <worktree>/src/dbt/kippnewark` on every dbt call
  (build finalsite package models via the kippnewark consuming project, not
  standalone — the package has no resolvable vars alone).
- **This is an additive package change.** Do NOT remove or rename any existing
  column in `int_finalsite__contact_custom_attributes` — Miami's Focus extracts
  (`rpt_focus__*`) read `emrg_1_*`/`emrg_2_*`, `pickup_*`, `nonpickup_*`, etc.
  Only ADD the Newark fields below.
- **Newark emergency schema (verbatim, from discovery):** 4 sets `emrg_1..4`,
  each with (string unless noted): `name_first_name`, `name_last_name`, `email`,
  `phone_1_number`, `phone_1_type`, `phone_1_opt_in` (bool), `phone_2_number`,
  `phone_2_type`, `phone_2_opt_in` (bool), `phone_3_number`, `phone_3_type`,
  `phone_3_opt_in` (bool), `relationship_ss`, `relationship_txt`, `priority_ss`,
  `custody_yn` (bool), `lives_with_yn` (bool), `pickup_yn` (bool). Plus presence
  toggles `emrg_3_yn` (bool), `emrg_4_yn` (bool). Sets 1-2 are always present;
  3-4 gated by their toggle.
- **contact_1 rule (resolved):** the `relationships` element with
  `primary = true`; fallback to `relationships[0]` when no primary. Details
  (name/email/phone/address) come from joining that relationship's `rel_id` to
  the parent contact record's `id`.
- **emergency order (resolved):** sort the up-to-4 emergency sets by
  `priority_ss` (cast to int) asc, tiebreak natural set order (1..4), nulls
  last. The output slots `emergency_1..4` are the sorted positions.
- **contact_1 flags (resolved):**
  `is_pickup`/`is_custodial`/`is_household_member` are null/false for
  `contact_1` (only emergency sets carry these).
- **SQL guide:** BigQuery dialect, trailing commas, single quotes, 88 cols, no
  `QUALIFY`/`ORDER BY`/`GROUP BY ALL`/`SELECT *` in final marts, max 1 function
  nesting, cast early. Follow `src/dbt/CLAUDE.md` row-picking rules
  (`dbt_utils.deduplicate` for canonical picks, no `qualify row_number()=1`).
- **Contract + uniqueness** on every staging/intermediate model.
- Conventional commits; branch `cbini/feat/claude-finalsite-contacts-dbt`
  (exists, linked to #4346).

## Prerequisite (one-time, per this plan's testing)

Newark's contacts source + api models are `+enabled: false` in
`src/dbt/kippnewark/dbt_project.yml`. This plan's models can't build for Newark
until those flip. **Task 0** flips them (this is a real cutover change that
ships with the plan, not a temporary edit). The Newark contacts external must
also be staged. All dbt builds below target `dev` with `--defer` to the prod
manifest.

---

## Task 0: Enable Newark Finalsite contacts (source + api) and stage the external

**Files:**

- Modify: `src/dbt/kippnewark/dbt_project.yml`

- [ ] **Step 1: Flip the two gates**

In `src/dbt/kippnewark/dbt_project.yml`: under `models: finalsite: api:` set
`+enabled: true` (was false), and under
`sources: finalsite: finalsite: contacts:` set `+enabled: true` (was false).

- [ ] **Step 2: Stage the contacts external into dev**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt && \
  uv run dbt run-operation stage_external_sources \
  --args 'select: finalsite.contacts' \
  --project-dir src/dbt/kippnewark --target dev
```

Expected:
`create or replace external table ... zz_<user>_kippnewark_finalsite.contacts`.

- [ ] **Step 3: Build the two existing api staging models into dev**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt && \
  uv run dbt build --project-dir src/dbt/kippnewark --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --select stg_finalsite__contacts stg_finalsite__contact_relationships
```

Expected: PASS. Confirms the enabled source resolves and staging builds for
Newark.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  add src/dbt/kippnewark/dbt_project.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  commit -m "feat(kippnewark): enable Finalsite contacts source and api models. Refs #4346"
```

---

## Task 1: Extend the custom_attributes PIVOT with Newark emergency fields

Add the Newark `emrg_*` fields absent from the current PIVOT. The model
(`src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_custom_attributes.sql`)
pivots each field with three aggregates (`max(value_string) as s`,
`max(value_boolean) as b`, `any_value(value_array) as a`) and projects the typed
subfield. Booleans use the `b_` alias → output name; strings use `s_`.

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_custom_attributes.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_custom_attributes.yml`

**Interfaces:**

- Produces: the Newark emergency columns consumed by Task 2. Boolean columns
  (`emrg_N_phone_M_opt_in`, `emrg_N_custody_yn`, `emrg_N_lives_with_yn`,
  `emrg_N_pickup_yn`, `emrg_3_yn`, `emrg_4_yn`); the rest string.

- [ ] **Step 1: Add the new field names to the PIVOT `for field_name in (...)`
      list**

Add these to the `in (...)` list (alphabetical placement not required; the
existing list is roughly alphabetical). Fields already present (`emrg_1_email`,
`emrg_1_name_first_name`, `emrg_1_name_last_name`, `emrg_1_phone_1_number`,
`emrg_1_phone_1_opt_in`, `emrg_1_phone_1_type`, `emrg_1_phone_2_number`,
`emrg_1_phone_2_type`, `emrg_1_relationship_ss`, `emrg_1_relationship_txt`, and
the `emrg_2_*` equivalents) stay. ADD:

```text
'emrg_1_phone_2_opt_in', 'emrg_1_phone_3_number', 'emrg_1_phone_3_type',
'emrg_1_phone_3_opt_in', 'emrg_1_priority_ss', 'emrg_1_custody_yn',
'emrg_1_lives_with_yn', 'emrg_1_pickup_yn',
'emrg_2_phone_2_opt_in', 'emrg_2_phone_3_number', 'emrg_2_phone_3_type',
'emrg_2_phone_3_opt_in', 'emrg_2_priority_ss', 'emrg_2_custody_yn',
'emrg_2_lives_with_yn', 'emrg_2_pickup_yn',
'emrg_3_yn', 'emrg_3_email', 'emrg_3_name_first_name', 'emrg_3_name_last_name',
'emrg_3_phone_1_number', 'emrg_3_phone_1_type', 'emrg_3_phone_1_opt_in',
'emrg_3_phone_2_number', 'emrg_3_phone_2_type', 'emrg_3_phone_2_opt_in',
'emrg_3_phone_3_number', 'emrg_3_phone_3_type', 'emrg_3_phone_3_opt_in',
'emrg_3_relationship_ss', 'emrg_3_relationship_txt', 'emrg_3_priority_ss',
'emrg_3_custody_yn', 'emrg_3_lives_with_yn', 'emrg_3_pickup_yn',
'emrg_4_yn', 'emrg_4_email', 'emrg_4_name_first_name', 'emrg_4_name_last_name',
'emrg_4_phone_1_number', 'emrg_4_phone_1_type', 'emrg_4_phone_1_opt_in',
'emrg_4_phone_2_number', 'emrg_4_phone_2_type', 'emrg_4_phone_2_opt_in',
'emrg_4_phone_3_number', 'emrg_4_phone_3_type', 'emrg_4_phone_3_opt_in',
'emrg_4_relationship_ss', 'emrg_4_relationship_txt', 'emrg_4_priority_ss',
'emrg_4_custody_yn', 'emrg_4_lives_with_yn', 'emrg_4_pickup_yn'
```

- [ ] **Step 2: Add the matching projected columns in the final SELECT**

For each added field, add a projected column using the correct type prefix
(`b_<field>` for booleans, `s_<field>` for strings), aliased to the bare field
name. Booleans: every `*_opt_in`, `*_yn`. Strings: everything else. Example
lines (follow the existing `s_...`/`b_...` pattern, ST06 ordering — strings and
booleans grouped as the existing model does):

```sql
    b_emrg_1_phone_2_opt_in as emrg_1_phone_2_opt_in,
    s_emrg_1_phone_3_number as emrg_1_phone_3_number,
    s_emrg_1_phone_3_type as emrg_1_phone_3_type,
    b_emrg_1_phone_3_opt_in as emrg_1_phone_3_opt_in,
    s_emrg_1_priority_ss as emrg_1_priority_ss,
    b_emrg_1_custody_yn as emrg_1_custody_yn,
    b_emrg_1_lives_with_yn as emrg_1_lives_with_yn,
    b_emrg_1_pickup_yn as emrg_1_pickup_yn,
    -- ...repeat for emrg_2; then all emrg_3_* and emrg_4_* including
    -- b_emrg_3_yn, b_emrg_4_yn (presence toggles)...
```

- [ ] **Step 3: Document the new typed (boolean) columns in properties yml**

The model docs only the Focus-consumed + typed fields. Add `description:` +
`data_type:` entries for the new BOOLEAN columns (the yml's convention documents
booleans/arrays): `emrg_{1..4}_phone_{1..3}_opt_in`, `emrg_{1..4}_custody_yn`,
`emrg_{1..4}_lives_with_yn`, `emrg_{1..4}_pickup_yn`, `emrg_3_yn`, `emrg_4_yn`.
Describe by logic (e.g. "Whether emergency contact N is authorized for pickup").
String columns follow the model's "only typed + Focus-consumed documented"
convention and need no per-column entry.

- [ ] **Step 4: Build + verify against dev**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt && \
  uv run dbt build --project-dir src/dbt/kippnewark --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --select int_finalsite__contact_custom_attributes
```

Expected: PASS (unique/not_null on `finalsite_enrollment_id`). Then verify the
new columns populate (BigQuery MCP against
`zz_<user>_kippnewark_finalsite.int_finalsite__contact_custom_attributes`):

```sql
select
  countif(emrg_1_pickup_yn is not null) as n_e1_pickup,
  countif(emrg_4_name_first_name is not null and emrg_4_name_first_name != '') as n_e4_name,
  countif(emrg_1_priority_ss is not null) as n_e1_priority
from `teamster-332318`.zz_<user>_kippnewark_finalsite.int_finalsite__contact_custom_attributes
```

Expected: `n_e1_pickup` ~6,700, `n_e4_name` ~440, `n_e1_priority` ~6,700.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  add src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_custom_attributes.sql \
      src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_custom_attributes.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  commit -m "feat(finalsite): add Newark emergency-contact fields to custom_attributes pivot. Refs #4346"
```

---

## Task 2: Add `int_finalsite__student_contacts` (1+4 long format)

**Files:**

- Create:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
- Create:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`

**Interfaces:**

- Consumes: `stg_finalsite__contacts` (student + parent records; `id`, `email`,
  `phone_1/2/3`, `households`, `custom_attributes`),
  `stg_finalsite__contact_relationships` (`finalsite_enrollment_id`, `rel_id`,
  `rel_name`, `rel_type`, `is_primary`),
  `int_finalsite__contact_custom_attributes` (emergency fields from Task 1),
  `int_finalsite__contact_id_attributes` (`powerschool_student_number` — used
  only to identify student records, NOT to join to PS).
- Produces: grain `(finalsite_enrollment_id, contact_slot)` where
  `contact_slot ∈ {'contact_1','emergency_1','emergency_2','emergency_3','emergency_4'}`.
  Columns (all nullable except keys): `finalsite_enrollment_id` (student contact
  id), `contact_slot`, `contact_name`, `relationship`, `email`, **typed phones**
  `phone_mobile`, `phone_home`, `phone_work`, `phone_daytime`, `phone_primary`,
  `home_address`, `is_pickup`, `is_custodial`, `is_household_member`,
  `is_emergency`. Sparse — a slot row is emitted only when that slot has data.
- **Phone typing (both slots):** map the up-to-3 phones by their `_type` value —
  `phone_mobile` = the phone with type `Cell`; `phone_home` = type `Home`;
  `phone_work` = type `Work`; `phone_daytime` = null (no Finalsite equivalent);
  `phone_primary` = `phone_1.number` / `emrg_N_phone_1_number` (the first phone,
  regardless of type — ~32% of parent phones are blank-type so only `_primary`
  catches them). For `contact_1` the phones come from the parent record's
  `phone_1/2/3` (each `{number, phone_type}`); for `emergency_N` from
  `emrg_N_phone_{1,2,3}_number` + `_type`. Derive each typed column with
  `coalesce(if(type='Cell', number, null) ...)` over the 3 phones in an upstream
  CTE (max 1 function nesting; no subqueries) — do NOT emit a single `phone`.

- [ ] **Step 1: Identify student records**

CTE `students`: from `int_finalsite__contact_id_attributes`, select
`finalsite_enrollment_id` where `powerschool_student_number is not null`. (This
is the Finalsite enrollment spine; the PS join is downstream in 3b.)

- [ ] **Step 2: contact_1 — pick the ranked relationship, join for details**

CTE `ranked_rel`: from `stg_finalsite__contact_relationships` joined to
`students`, compute a pick rank per student: `primary` first, then array order.
`stg_finalsite__contact_relationships` does not currently carry array offset —
add it: in that staging model, expose `_offset` via
`... cross join unnest(c.relationships) as r with offset as rel_offset` (add
`rel_offset` to the staging SELECT + its properties yml + contract). Then in
`ranked_rel`, order by `is_primary desc, rel_offset asc` and pick the top with
`dbt_utils.deduplicate(partition_by='finalsite_enrollment_id', order_by='is_primary desc, rel_offset asc')`.
Join the picked `rel_id` to `stg_finalsite__contacts` (`c.id = picked.rel_id`)
for `email`, `phone_1.number`/`phone_1.phone_type`, `households[safe_offset(0)]`
address. `contact_name` = `rel_name`; `relationship` = `rel_type`. Emit one
`contact_slot = 'contact_1'` row per student with a relationship;
`is_pickup`/`is_custodial`/`is_household_member` = null; `is_emergency` = false.

- [ ] **Step 3: emergency_1..4 — unpivot the emrg sets, sort by priority**

CTE `emergency_long`: from `int_finalsite__contact_custom_attributes` (joined to
`students`), build one row per (student, set N in 1..4) via `UNION ALL` of 4
branches (branch N selects `emrg_N_*` columns as generic `contact_name` =
`concat(first, ' ', last)`, `relationship` =
`coalesce(relationship_ss, relationship_txt)`, `email`, `phone` =
`emrg_N_phone_1_number`, `phone_type` = `emrg_N_phone_1_type`, `is_pickup` =
`emrg_N_pickup_yn`, `is_custodial` = `emrg_N_custody_yn`, `is_household_member`
= `emrg_N_lives_with_yn`, `priority` = `safe_cast(emrg_N_priority_ss as int64)`,
`set_order` = N). Filter each branch to rows where the set has a name
(`emrg_N_name_first_name` non-null/ non-empty). Then rank within student by
`priority asc nulls last, set_order asc` using `dbt_utils.deduplicate` is NOT
applicable (keeps 1) — instead compute
`row_number() over (partition by finalsite_enrollment_id order by priority, set_order)`
as a named column in a CTE and filter `= 1,2,3,4` in the next CTE (no
`QUALIFY`), mapping to `contact_slot = 'emergency_' || rank`. `is_emergency` =
true; `home_address` = null (emergency sets carry no address).

- [ ] **Step 4: UNION contact_1 + emergency slots**

Final SELECT: `UNION ALL` the contact_1 rows and the emergency rows, enumerating
columns explicitly (no `SELECT *` across UNION branches — CV03). Cast the `is_*`
booleans consistently.

- [ ] **Step 5: properties yml — contract, grain test, descriptions**

`config: materialized: table` (default for staging; intermediate defaults to
table here too — match the sibling `int_finalsite__*` models). Model-level
`dbt_utils.unique_combination_of_columns` on
`[finalsite_enrollment_id, contact_slot]`. `description:` on model + every
column. `contract: enforced: true` if the sibling intermediates enforce it
(check `int_finalsite__enrollment_lifecycle.yml`); match them.

- [ ] **Step 6: Build + verify**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt && \
  uv run dbt build --project-dir src/dbt/kippnewark --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippnewark/target/prod \
  --select int_finalsite__student_contacts stg_finalsite__contact_relationships
```

Expected: PASS. Verify grain + slot distribution (BigQuery MCP):

```sql
select contact_slot, count(*) n,
  countif(phone is not null and phone != '') n_phone
from `teamster-332318`.zz_<user>_kippnewark_finalsite.int_finalsite__student_contacts
group by contact_slot order by contact_slot
```

Expected: `contact_1` ~6,700; `emergency_1` ~6,700 tapering to `emergency_4`
~440; phone highly populated. Confirm no student exceeds 5 rows.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  add src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql \
      src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml \
      src/dbt/finalsite/models/api/staging/stg_finalsite__contact_relationships.sql \
      src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_relationships.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt \
  commit -m "feat(finalsite): add int_finalsite__student_contacts 1+4 long model. Refs #4346"
```

---

## Task 3: Trunk-check and push

- [ ] **Step 1:** `trunk check --force` all changed SQL/YAML from inside the
      worktree (absolute binary `/workspaces/teamster/.trunk/tools/trunk`, cwd =
      worktree). Fix sqlfluff/yamllint findings.
- [ ] **Step 2:** Confirm dbt Cloud CI is terminal (nothing running), then push.
      This is a district + package change; CI is kipptaf-scoped and a no-op —
      verify the district build locally (done in Tasks 0-2). Open the PR only
      after Plan 3b is also ready, OR open a package-only PR now (the new model
      builds empty in Miami/Camden/Paterson; harmless).

---

## Self-review notes

- **Spec coverage:** Covers the spec §2 finalsite-package items
  (`stg_finalsite__contact_relationships` rank/offset,
  `int_finalsite__contact_custom_attributes` emergency fields,
  `int_finalsite__student_contacts`). The kipptaf union/pivot/dim/bridge,
  consumer updates, Miami PS-mapped CTE, and Cube updates are **Plan 3b**.
- **Additive PIVOT:** Miami Focus extracts keep their columns; only new Newark
  fields added. Miami lacks `emrg_3/4`, `priority_ss`, `_yn` flags → those pivot
  to NULL for Miami (harmless; Miami contacts use the PS-mapped path in 3b).
- **SIS-agnostic:** the finalsite model filters to student records via
  `powerschool_student_number` presence but does NOT join PS; the
  `finalsite_enrollment_id → student_number` join is Plan 3b at kipptaf.
- **Open item for 3b:** the Camden/Paterson `emrg` schema is assumed identical
  to Newark's — confirm when their ingestion lands (re-run the discovery field
  query per region before enabling).
