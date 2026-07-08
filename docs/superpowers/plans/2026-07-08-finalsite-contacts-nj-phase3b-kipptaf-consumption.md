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
- **Surface shape (resolved):** strict **1+4** — only `contact_1` +
  `emergency_1..4` carry DATA. Typed phone columns
  `phone_mobile`/`_home`/`_work`/`_daytime`/`_primary` (per Plan 3a mapping:
  Cell→mobile, Home→home, Work→work, daytime→null, primary→first phone).
- **PRESERVE reporting-view output schemas — do NOT remove now-dead columns.**
  The `contact_2_*` and `pickup_*` columns have no data under 1+4, but external
  consumers (Google Sheets tabs, Tableau, DeansList, NJSMART, Clever) read
  **fixed column sets** — dropping a column breaks the feed. So every model an
  external consumer reads (the `rpt_*` views, and the pivot / `int_extracts_*` /
  `int_kippadb__roster` columns those views select) **keeps its existing output
  columns**; the now-dead ones simply emit NULL. Prune a dead column ONLY from a
  purely-internal model that no external consumer and no downstream view reads.
  Net: this migration is mostly a **source swap** (PS → Finalsite 1+4) that
  leaves column surfaces intact and nulls the retired slots. `emergency_4_*` is
  a NEW additive column set (safe — consumers ignore unknown columns).
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
- **SQL guide + marts rubric:** source-agnostic column names (strip
  `powerschool_`/`finalsite_`); PK/FK surrogate keys;
  `union_dataset_join_clause` / `_dbt_source_project` for union joins; no
  `QUALIFY`/`ORDER BY`/`SELECT *` in marts; contract + uniqueness on every
  dim/fct/rpt. (The preserve-schema rule above overrides any impulse to strip
  retired `contact_2`/`pickup` columns from views.)
- Conventional commits; branch `cbini/feat/claude-finalsite-contacts-dbt`.

## Consumer map (authoritative — from the current tree)

**Governing rule:** external-facing views keep ALL current output columns; the
retired `contact_2_*`/`pickup_*` just go NULL. "Prune" happens only inside
internal models with no external/view consumer.

| Consumer                                                  | Reads today                                                                                                       | 3b action                                                                                                                                                                                                                                            |
| --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `base_powerschool__student_enrollments` (powerschool pkg) | 73 `scw.*` cols from `int_powerschool__student_contacts_pivot`                                                    | Remove the contact join/cols (package can't ref finalsite); the contact surface moves to kipptaf `int_extracts__student_enrollments*` (Task 6). This is an internal package model — safe to prune here since the columns are re-provided downstream. |
| `int_extracts__student_enrollments`                       | `e.contact_1/2_email_current` (guardian_email coalesce)                                                           | Source from new kipptaf pivot; **keep** `guardian_email = coalesce(contact_1_email_current, contact_2_email_current)` unchanged (contact_2 side is just NULL now).                                                                                   |
| `int_extracts__student_enrollments_subjects_weeks`        | full `co.contact_1/2_*`, `emergency_1/2/3_*`, `pickup_1/2/3_*` (73 cols)                                          | Source from new pivot; **keep the full existing column list** (contact_2/pickup emit NULL); ADD `emergency_4_*`. Contract YAML: keep all + add emergency_4.                                                                                          |
| `int_kippadb__roster`                                     | `se.contact_1/2_*`, `se.emergency_1/2/3_*` → `powerschool_*` aliases                                              | **Keep** all existing `powerschool_contact_1/2_*` + `emergency_1/2/3_*` aliases (contact_2 NULL); ADD `emergency_4`.                                                                                                                                 |
| `rpt_deanslist__student_misc`                             | `contact_1/2_name/phone`, email                                                                                   | **No change** — `parent2_name`/`parent2_cell` stay, now NULL.                                                                                                                                                                                        |
| `rpt_gsheets__kfwd_taf_contact_feed`                      | `powerschool_contact_1/2_*`, `powerschool_emergency_contact_1/2_*`                                                | **No change** — contact_2 columns stay NULL. (Optionally add emergency_3/4.)                                                                                                                                                                         |
| `rpt_gsheets__kippfwd_collab_roster`                      | `powerschool_contact_1_*` only                                                                                    | No change.                                                                                                                                                                                                                                           |
| `rpt_gsheets__kippfwd_miami_roster`                       | `co.contact_1/2_*`                                                                                                | **No change** — contact_2 stays NULL (Miami PS-mapped fills contact_1 only).                                                                                                                                                                         |
| `rpt_gsheets__njsmart_transfer_unverified`                | `co.contact_1/2_*`                                                                                                | **No change** — contact_2 columns/coalesce stay NULL.                                                                                                                                                                                                |
| `rpt_gsheets__student_contact_info`                       | `contact_1` (mother), `contact_2` (father), `pickup_1/2/3` (release), email                                       | **No change** — `father` + `release_1/2/3` stay NULL.                                                                                                                                                                                                |
| `rpt_tableau__next_year_status`                           | `contact_1/2_phone_mobile`, `contact_1_email`                                                                     | **No change** — `tel_father_cell` stays NULL.                                                                                                                                                                                                        |
| `rpt_clever__students`                                    | LONG model person_type-keyed (`mother`/`father`/`contact1`/`contact2`, `contact_name`, `contact`, `contact_type`) | Point at the new long model; **preserve the emitted person_type/contact_type rows/codes Clever expects** (map new `contact_slot` → the codes Clever ingests; rows for retired types simply produce no data). See Task 8.                             |

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
row per `(student_number, _dbt_source_project)`. **To preserve downstream/output
schemas, emit the SAME column surface the old pivot did** — `contact_1_<attr>`,
`contact_2_<attr>`, `emergency_{1,2,3}_<attr>`, `pickup_{1..5}_<attr>` — PLUS
the new `emergency_4_<attr>`, for attr in {`name`, `relationship`,
`email_current`, `phone_mobile`, `phone_home`, `phone_daytime`, `phone_work`,
`phone_primary`, `address_home`}. Under 1+4 the long model has no rows for
`contact_2`/`pickup_*`, so those columns pivot to NULL automatically (the
`PIVOT`/conditional-aggregation over `contact_slot` just finds no matching
rows). No consumer or contract needs a column removed; `int_extracts_*` keeps
its existing list. Grain test on `[student_number, _dbt_source_project]`.
Build + verify the old column set is present-but-null for contact_2/pickup and
populated for contact_1/emergency_1-4. Commit.

> Get the authoritative old-pivot column list from
> `int_powerschool__student_contacts_pivot` (or `INFORMATION_SCHEMA.COLUMNS` on
> the prod table) so the new pivot's `for contact_slot in (...)` + projected
> columns reproduce every existing name.

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
- `int_extracts__student_enrollments`: **keep**
  `guardian_email = coalesce(contact_1_email_current, contact_2_email_current)`
  as-is (the contact_2 side is NULL now; leaving it costs nothing and avoids a
  diff).
- `int_extracts__student_enrollments_subjects_weeks`: **keep the full existing
  column list** (contact_2_* / pickup_* emit NULL from the new pivot); ADD
  `emergency_4_*`. Contracts stay as-is plus the new emergency_4 columns. Do NOT
  remove columns — external consumers read this chain. Build + verify. Commit.

---

## Task 7: Update `int_kippadb__roster` + the extract feeds

Per the consumer-map table. **Most of these need NO edit** — because the pivot
(Task 2) preserves the old column surface, the existing `contact_2_*`/`pickup_*`
selects just resolve to NULL. `int_kippadb__roster` is the one worth touching:
**keep** its existing `powerschool_contact_1/2_*` + `emergency_1/2/3_*` aliases
(contact_2 NULL) and optionally ADD `emergency_4`. The `rpt_*` feeds
(`rpt_deanslist__student_misc`, `rpt_gsheets__kfwd_taf_contact_feed`,
`rpt_gsheets__kippfwd_miami_roster`, `rpt_gsheets__njsmart_transfer_unverified`,
`rpt_gsheets__student_contact_info`, `rpt_tableau__next_year_status`,
`rpt_gsheets__kippfwd_collab_roster`) are **verify-only** — build each and
confirm it still compiles and its external output columns are intact (now partly
NULL). The whole point of preserving the pivot surface is that these feeds don't
churn. Only touch a feed if you're intentionally wiring `emergency_4` into it.

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
- [ ] **Cutover coverage check (Newark) — informational, NOT a gate.** The
      switch is mandated by the enrollment team (no go/no-go). Still worth
      running once for confidence + to spot ingestion gaps: compare
      Finalsite-sourced vs prior PS-sourced fill for Newark enrolled students (%
      with `contact_1`, % with ≥1 emergency, phone/email fill). Report it;
      surface surprises but don't block on it.
- [ ] Update dbt exposures for any changed extract (the feeds have exposures
      under `models/exposures/`); no Cube exposure change (not a consumer).
- [ ] Trunk-check all changed SQL/YAML from inside the worktree.

---

## Self-review notes

- **Spec coverage:** covers spec §2 kipptaf items (union, pivot, dim, bridge,
  powerschool-package removal, consumer source-swap) + the resolved decisions
  (1+4 DATA shape with preserved output columns, typed phones, PS-mapped Miami
  CTE). Cube task dropped (not a consumer — verified). Finalsite-package
  foundation is Plan 3a.
- **Sequencing risk:** Task 5 (package) + Task 1 (finalsite source reads) cross
  the project boundary — follow two-PR or single-PR cross-project workflow, or
  CI fails on stale `zz_stg_*`. Do not merge this before 3a is in prod.
- **Low blast radius by design:** because the pivot preserves the old column
  surface, retired `contact_2_*`/`pickup_*` go NULL instead of disappearing —
  external feeds (DeansList, KIPP Forward sheets, NJSMART, Tableau, Clever) keep
  their schemas and mostly need no edit. This is a source swap, not a
  surface-breaking change. The switch is mandated (no go/no-go gate).
- **Camden/Paterson:** creds now in 1Password — their ingestion (a Phase-1
  repeat) + per-region `emrg`/phone-type discovery re-check must land before
  moving them from the PS-mapped branch to the Finalsite branch in Task 1.
