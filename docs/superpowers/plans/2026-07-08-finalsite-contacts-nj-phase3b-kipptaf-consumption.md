# Finalsite NJ Contacts — Phase 3b (kipptaf Consumption Layer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans. Subagents doing dbt work MUST first invoke
> `Skill` with skill `dbt:using-dbt-for-analytics-engineering`, and for
> mart-layer tasks also read `src/dbt/kipptaf/models/marts/CLAUDE.md`.

**Goal:** Swap the network contact surface from PowerSchool to the 1+4 Finalsite
shape: a new kipptaf long-format union (NJ Finalsite + PS-mapped for Miami /
not-yet-cutover regions), a redefined pivot, redefined
`dim_student_contact_persons` / `bridge_student_contacts`, the removal of the
contact columns from the powerschool package, and updates to every downstream
consumer.

**Depends on:** Plan 3a merged AND materialized in prod (kipptaf reads
`int_finalsite__student_contacts` via `source()`; per `src/dbt/CLAUDE.md` the
district/package change must land in prod before the kipptaf consumer, or ship
via the single-PR cross-project workflow with staged `zz_stg_*`).

**Architecture:** long model → pivot → enrollment chain + roster + extracts. The
long model also feeds the redefined dim + bridge (person / link grains).
`rpt_clever__students` reads the long model directly (person_type-keyed). Cube
does not consume the marts.

## Global Constraints

- **Worktree:**
  `/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contacts-dbt`.
  `git -C <worktree>`; `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf`
  (kipptaf models) or `.../src/dbt/kippnewark` (package/district builds); dev
  target with `--defer --state /workspaces/teamster/src/dbt/<proj>/target/prod`.
- **Surface shape (resolved):** strict **1+4** — `contact_1` + `emergency_1..4`.
  **No `contact_2`, no `pickup_*`** anywhere. Typed phone columns
  `phone_mobile`/`_home`/`_work`/`_daytime`/`_primary` (per Plan 3a mapping:
  Cell→mobile, Home→home, Work→work, daytime→null, primary→first phone).
- **Column families per contact:** `<slot>_name`, `<slot>_relationship`,
  `<slot>_email_current`, `<slot>_phone_mobile/_home/_daytime/_work/_primary`,
  and (contact_1 + emergency only where present) `<slot>_address_home`.
  Emergency slots carry the flags
  `is_pickup`/`is_custodial`/`is_household_member` (from
  `emrg_N_pickup_yn`/`_custody_yn`/`_lives_with_yn`); `contact_1` flags are
  null.
- **Cross-project sequencing:** powerschool-package change (Task 5) + finalsite
  source reads require the two-PR pattern OR the single-PR cross-project
  workflow (`src/dbt/kipptaf/CLAUDE.md`). Default: ship 3a first (already its
  own PR), let prod materialize, then this PR.
- **Cube:** not a consumer (grep `src/cube` empty) — no Cube change.
- **Miami stays PS-sourced** (Focus migration owns its cutover). The PS-mapped
  CTE covers Miami + any NJ region not yet cut over; its region list shrinks per
  cutover. Mark it `-- TODO(focus)`.
- **SQL guide + marts rubric:** no `contact_2`/`pickup` in any mart SELECT;
  source-agnostic column names (strip `powerschool_`/`finalsite_`); PK/FK
  surrogate keys; `union_dataset_join_clause` / `_dbt_source_project` for union
  joins; no `QUALIFY`/`ORDER BY`/`SELECT *` in marts; contract + uniqueness on
  every dim/fct/rpt.
- Conventional commits; branch `cbini/feat/claude-finalsite-contacts-dbt`.

## Consumer map (authoritative — from the current tree)

| Consumer                                                  | Reads today                                                                                                                                           | 3b action                                                                                                                                                              |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base_powerschool__student_enrollments` (powerschool pkg) | 73 `scw.*` contact cols from `int_powerschool__student_contacts_pivot`                                                                                | **Remove all** — package can't ref finalsite. Contact join moves to kipptaf (Task 6).                                                                                  |
| `int_extracts__student_enrollments`                       | `e.contact_1/2_email_current` (guardian_email coalesce)                                                                                               | Join new kipptaf pivot; `guardian_email = contact_1_email_current` (drop contact_2).                                                                                   |
| `int_extracts__student_enrollments_subjects_weeks`        | full `co.contact_1/2_*`, `emergency_1/2/3_*`, `pickup_1/2/3_*` (73 cols)                                                                              | Repoint to new pivot; keep `contact_1_*` + `emergency_1..4_*`; **drop `contact_2_*`, `pickup_*`**.                                                                     |
| `int_kippadb__roster`                                     | `se.contact_1/2_*`, `se.emergency_1/2/3_*` → `powerschool_*` aliases                                                                                  | Keep `contact_1` + `emergency_1..3` (add `emergency_4`); **drop `contact_2_*`**. Downstream `powerschool_contact_2_*` consumers below also drop.                       |
| `rpt_deanslist__student_misc`                             | `contact_1_name/phone_mobile/email`, `contact_2_name/phone_mobile`                                                                                    | Keep parent1 (contact_1); **drop parent2** (`contact_2_name`→`parent2_name`, `contact_2_phone_mobile`→`parent2_cell`).                                                 |
| `rpt_gsheets__kfwd_taf_contact_feed`                      | `r.powerschool_contact_1/2_*`, `r.powerschool_emergency_contact_1/2_*`                                                                                | Keep contact_1 + emergency_1/2; **drop contact_2** block.                                                                                                              |
| `rpt_gsheets__kippfwd_collab_roster`                      | `ktc.powerschool_contact_1_*` only                                                                                                                    | No change (contact_1 only). Verify after roster edit.                                                                                                                  |
| `rpt_gsheets__kippfwd_miami_roster`                       | `co.contact_1/2_*`                                                                                                                                    | **Drop contact_2_*** (Miami PS-mapped → contact_1 only).                                                                                                               |
| `rpt_gsheets__njsmart_transfer_unverified`                | `co.contact_1/2_*` (name/relationship/phone)                                                                                                          | **Drop contact_2_*** (both `contact_2` block + the `contact_2_phone` coalesce).                                                                                        |
| `rpt_gsheets__student_contact_info`                       | `contact_1` (mother), `contact_2` (father), `pickup_1/2/3` (release_1/2/3), coalesce(contact_1,contact_2) email                                       | Keep mother (contact_1); **drop father** (contact_2) + **release_1/2/3** (pickup); email = `contact_1_email_current`.                                                  |
| `rpt_tableau__next_year_status`                           | `co.contact_1/2_phone_mobile`, `contact_1_email` (tel_mother_cell / tel_father_cell)                                                                  | Keep tel_mother_cell (contact_1); **drop tel_father_cell** (contact_2).                                                                                                |
| `rpt_clever__students`                                    | LONG model: `sc.person_type in ('mother','father','contact1','contact2')`, `sc.contact_name`, `sc.contact`, `sc.relationship_type`, `sc.contact_type` | Remap to the new long model's `contact_slot` values (`contact_1`, `emergency_1..4`); rebuild the phone-type `contact_type` logic from typed-phone columns. See Task 8. |

---

## Task 1: `int_students__contacts` — long-format union (NJ Finalsite + PS-mapped)

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__contacts.sql`
- Create: `.../properties/int_students__contacts.yml`

**Interfaces:**

- Produces: grain `(student_number, _dbt_source_project, contact_slot)`.
  Columns: `student_number`, `_dbt_source_project`, `contact_slot`
  (`contact_1`/`emergency_1..4`), `contact_name`, `relationship`,
  `email_current`, `phone_mobile`, `phone_home`, `phone_daytime`, `phone_work`,
  `phone_primary`, `address_home`, `is_emergency`, `is_pickup`, `is_custodial`,
  `is_household_member`, and the raw `personid`/`finalsite_contact_id` for the
  dim key (Task 3). Consumed by Tasks 2, 3, 4.

- [ ] **Step 1: Finalsite branch (NJ cutover regions)**

CTE `finalsite`: union the per-cutover-region
`source("<region>_finalsite", "int_finalsite__student_contacts")` (start with
`kippnewark_finalsite`; add Camden/Paterson as they cut over). Join
`finalsite_enrollment_id` → `powerschool_student_number` via
`source("<region>_finalsite", "int_finalsite__contact_id_attributes")`. Set
`_dbt_source_project` via `extract_code_location`. Column names already match
the target (Plan 3a emits typed phones + flags); `address_home` from the model's
`home_address`.

- [ ] **Step 2: PS-mapped branch (Miami + not-yet-cutover regions)**

CTE `powerschool`
(`-- TODO(focus): remove when Focus/Finalsite cover all regions`): union
`source("<region>_powerschool", "int_powerschool__contacts")`

- `int_powerschool__person_contacts` for regions NOT in the Finalsite branch
  (today: Miami, Camden, Paterson — as each NJ region cuts over, remove it
  here). Map to 1+4:

* `contact_1` = the `contactpriorityorder = 1`, `person_type != 'self'` contact.
* `emergency_1..4` = `isemergency = 1` contacts ranked by `contactpriorityorder`
  (row_number in a CTE, filter `<= 4`; no QUALIFY).
* Typed phones from `int_powerschool__person_contacts`
  (`contact_category = 'Phone'`, `contact_type` in Mobile/Home/Daytime/Work);
  email from `contact_category = 'Email'` current; `address_home` from
  `contact_category = 'Address'` home. Flags: `is_pickup = schoolpickupflg`,
  `is_custodial = iscustodial`, `is_household_member = liveswithflg`,
  `is_emergency = isemergency`.

* [ ] **Step 3: UNION + key columns + grain test**

`UNION ALL` both branches (enumerate columns; CV03). Carry `personid` (PS) /
`finalsite_contact_id` (the resolved parent `rel_id` for contact_1; null for
emergency) for the dim key. Model-level
`dbt_utils.unique_combination_of_columns` on
`[student_number, _dbt_source_project, contact_slot]`. `description:` on model +
every column. Materialize table (intermediate default here).

- [ ] **Step 4: Build + verify** (dev, `--defer`), then verify slot counts and
      that Newark rows come from the Finalsite branch while
      Miami/Camden/Paterson come from PS (group by
      `_dbt_source_project, contact_slot`). Commit.

---

## Task 2: New pivot `int_students__contacts_pivot`

Replaces `int_powerschool__student_contacts_pivot` as the reporting source. One
row per `(student_number, _dbt_source_project)`; columns `contact_1_<attr>` +
`emergency_{1..4}_<attr>` for attr in {`name`, `relationship`, `email_current`,
`phone_mobile`, `phone_home`, `phone_daytime`, `phone_work`, `phone_primary`,
`address_home`}. BigQuery `PIVOT` (or conditional aggregation) over
`contact_slot`. Grain test on `[student_number, _dbt_source_project]`. Build +
verify the column set matches what the enrollment chain needs (Task 6). Commit.

---

## Task 3: Redefine `dim_student_contact_persons`

From `int_students__contacts` (person grain, not slot). PK
`student_contact_person_key = generate_surrogate_key([...])`: for `contact_1`
rows use the real contact identity (`_dbt_source_project` +
`finalsite_contact_id` for NJ, `personid` for PS); emergency rows have no person
record → key =
`generate_surrogate_key([_dbt_source_project, student_number, contact_slot])`.
Columns: `full_name`, `email`, typed phones, `home_address` (slim per marts
rubric R1 — no source prefixes). Contract + `unique` on PK. Redeclare FK
constraints. Build + verify FK population. Commit.

## Task 4: Redefine `bridge_student_contacts`

From `int_students__contacts`. Grain
`(student_key, student_contact_person_key, contact_slot)`. Columns:
`student_key` FK, `student_contact_person_key` FK, `relationship`,
`contact_slot`, `is_emergency`, `is_pickup`, `is_custodial`,
`is_household_member` (INT64 0/1 per R3 if used as measures, else BOOLEAN).
Contract + composite uniqueness. Build + verify. Commit.

---

## Task 5: Remove contact columns from the powerschool package (SHIP FIRST / staged)

**Files:**
`src/dbt/powerschool/models/sis/base/base_powerschool__student_enrollments.sql`
(drop the 73 `scw.*` refs + the `int_powerschool__student_contacts_pivot` join)
and its `properties.yml` contract (remove the 73 contract columns). Also mark
`int_powerschool__student_contacts` / `_pivot` deprecated-as-reporting-source
once no consumer reads them (do NOT delete — raw PS still loads; deletion waits
for Miami/Focus).

Because this is a package model consumed by every district + kipptaf, follow the
cross-project sequencing (Global Constraints). Build the affected district
projects locally to confirm no other consumer of
`base_powerschool__student_enrollments` reads the dropped columns. Commit.

---

## Task 6: Rewire the enrollment chain to the new pivot

**Files:** `int_extracts__student_enrollments.sql` (+ properties),
`int_extracts__student_enrollments_subjects_weeks.sql` (+ properties).

- Join `int_students__contacts_pivot` (on `student_number` +
  `_dbt_source_project`) in place of the removed `base_powerschool` contact
  columns.
- `int_extracts__student_enrollments`:
  `guardian_email = contact_1_email_current` (drop the `contact_2` coalesce).
- `int_extracts__student_enrollments_subjects_weeks`: keep `contact_1_*` +
  `emergency_1..4_*`; DROP every `contact_2_*` and `pickup_*` column. Update the
  contract YAMLs (these are contract-enforced) in the same change. Build +
  verify. Commit.

---

## Task 7: Update `int_kippadb__roster` + the extract feeds

Per the consumer-map table. For each file: drop `contact_2_*` (and
`powerschool_contact_2_*`) and `pickup_*` refs; keep `contact_1` + emergency;
add `emergency_4` where the feed lists emergencies. Update contract YAMLs where
present. One commit per file (subagent-driven task each), building + verifying
each against dev. Feeds: `int_kippadb__roster`, `rpt_deanslist__student_misc`,
`rpt_gsheets__kfwd_taf_contact_feed`, `rpt_gsheets__kippfwd_miami_roster`,
`rpt_gsheets__njsmart_transfer_unverified`, `rpt_gsheets__student_contact_info`,
`rpt_tableau__next_year_status`. (`rpt_gsheets__kippfwd_collab_roster` reads
only `contact_1` — verify, likely no edit.)

---

## Task 8: `rpt_clever__students` (long-model consumer)

Reads the long model's `person_type` values (`mother`/`father`/`contact1`/
`contact2`) and a phone-type `contact_type`. Remap to the new `contact_slot`
vocabulary (`contact_1`, `emergency_1..4`) and rebuild `contact_type` from the
typed-phone columns. Confirm the Clever export's per-contact-type rows still
emit (Clever expects specific contact-type codes). Build + verify. Commit.

---

## Task 9: Tests, cutover validation, exposures

- [ ] Grain/uniqueness + `relationships` FK tests on the new dim/bridge/pivot
      (warn or error per layer).
- [ ] **Cutover coverage gate (Newark):** compare Finalsite-sourced vs the prior
      PS-sourced surface for Newark enrolled students — % with `contact_1`, %
      with ≥1 emergency, phone/email fill. A material drop blocks the Newark PR
      from flipping the reporting source. Query documented inline.
- [ ] Update dbt exposures for any changed extract (the feeds have exposures
      under `models/exposures/`); no Cube exposure change (not a consumer).
- [ ] Trunk-check all changed SQL/YAML from inside the worktree.

---

## Self-review notes

- **Spec coverage:** covers spec §2 kipptaf items (union, pivot, dim, bridge,
  powerschool-package removal, consumer updates) + the resolved decisions (1+4,
  typed phones, drop parent2/pickup, PS-mapped Miami CTE). Cube task dropped
  (not a consumer — verified). Finalsite-package foundation is Plan 3a.
- **Sequencing risk:** Task 5 (package) + Task 1 (finalsite source reads) cross
  the project boundary — follow two-PR or single-PR cross-project workflow, or
  CI fails on stale `zz_stg_*`. Do not merge this before 3a is in prod.
- **Blast radius:** removing `contact_2`/`pickup` changes live external feeds
  (DeansList, KIPP Forward sheets, NJSMART, Tableau, Clever). The cutover
  coverage gate (Task 9) must pass before the Newark reporting source flips.
- **Camden/Paterson:** creds now in 1Password — their ingestion (a Phase-1
  repeat) + per-region `emrg`/phone-type discovery re-check must land before
  moving them from the PS-mapped branch to the Finalsite branch in Task 1.
