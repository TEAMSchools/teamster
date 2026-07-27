# Miami student emails into the Focus DEMOGRAPHICS import — design

Tracking issue: [#4512](https://github.com/TEAMSchools/teamster/issues/4512)
(Deliverable 1 of parent
[#4511](https://github.com/TEAMSchools/teamster/issues/4511)).

## Problem

Every enrolled KIPP Miami (Focus) student needs a stable KIPP student email
landed in the Focus `DEMOGRAPHICS` import (`stdt_email`) so the newly launched
Miami Clever instance can provision accounts.

Today `rpt_focus__demographics.stdt_email` maps `stg_finalsite__contacts.email`,
which is empty for effectively all students. NJ students get a generated
`username@teamstudents.org` from `stg_people__student_logins` (PowerSchool
driven); Miami's PowerSchool is retired, so Focus-only Miami students never get
an email minted.

## Decisions (resolved during brainstorming)

1. **Domain — all `@teamstudents.org`.** Returning students reuse their existing
   `@teamstudents.org` account; new students are minted on the same network
   domain. `@kippmiami.org` is a staff domain and is not used for students.
2. **Delivery — no change to the automated import-once behavior.** The only
   pipeline change is minting the email and wiring it into `stdt_email`. New
   enrollees inherit it through the existing kippmiami import-once wrapper. The
   ~1,473 already-enrolled students are backfilled manually via the kipptaf
   feed.
3. **Keying — prefixed Focus id only.** All Miami rows in
   `stg_people__student_logins` are keyed on the `8400`-prefixed Focus id
   (`focus_student_id_prefixed`, which equals Focus `students.student_id` and is
   the `stdt_id` join key into the feed). Existing Miami rows are **migrated**
   from their bare key to the prefixed key.

## Current architecture

```text
Finalsite (API)  ->  kipptaf_extracts.rpt_focus__demographics   (desired state, all rows)
                          |  source("kipptaf_extracts", ...)
                          v
                     kippmiami_extracts.rpt_focus__demographics  (import-once wrapper)
                          |  Dagster build_bigquery_query_sftp_asset
                          v
                     Focus SFTP  incoming/*.csv
```

- `stg_people__student_logins` (kipptaf) is an **incremental merge** model
  (`unique_key: student_number` int64, `full_refresh: false`,
  `merge_update_columns: [default_password]`). `username` and `google_email` are
  **insert-only** — never rewritten once set. All 30,266 existing rows are
  `@teamstudents.org`; none are `8400`-prefixed.
- Only two models read it: `base_powerschool__student_enrollments` and
  `rpt_littlesis__enrollments`, both scoped to the PowerSchool enrollment /
  roster spine. The Google Workspace and Clever feeds obtain student email
  downstream of `base_powerschool__student_enrollments` via
  `int_extracts__student_enrollments`, which also spines on PowerSchool.
- The kipptaf-level `stg_powerschool__students` union **still includes the
  frozen `kippmiami_powerschool` archive** and exposes
  `_dbt_source_project = regexp_extract(_dbt_source_relation, r'(kipp\w+)_')`.

## Design

Division of labor follows the existing finalsite -> focus pattern: `kipptaf`
owns desired state; `kippmiami` owns reconciliation (unchanged here).

### 1. Migrate existing Miami rows to the prefixed key (one-time DML)

Re-key every historical Miami row in `stg_people__student_logins` from its bare
`student_number` to the `8400`-prefixed form, preserving `username`,
`default_password`, and `google_email`. Miami rows are identified as those whose
`student_number` appears in the frozen Miami PowerSchool archive — safe because
`student_number` is globally unique across districts (verified: zero true
cross-district collisions).

```sql
update `teamster-332318.kipptaf_people.stg_people__student_logins` as s
set student_number = cast(concat('8400', cast(s.student_number as string)) as int64)
where
    s.student_number in (
        select distinct student_number
        from `teamster-332318.kippmiami_powerschool.stg_powerschool__students`
        where student_number >= 1
    )
```

- Claude is DML-blocked; **the user runs this** in their terminal with named
  consent, once, before the manual backfill.
- The predicate is self-guarding against a double run: bare Miami numbers are
  6-digit (`< 1000000`) while the archive holds only bare numbers, so a second
  execution matches nothing new (already-prefixed rows are not in the archive
  set).
- Scope is all ~3,939 historical Miami rows (enrolled + withdrawn), not just the
  currently enrolled — this future-proofs re-enrollments and leaves the table
  uniformly prefixed for Miami.

### 2. Add a Miami/Focus mint branch to `stg_people__student_logins`

In the incremental block, add a second source branch that mints emails for
enrolled Focus students, keyed on `focus_student_id_prefixed` cast to `int64`.
Source the enrolled Finalsite cohort (`stg_finalsite__contacts`
`status = 'enrolled'` joined to `int_finalsite__contact_id_attributes` where
`focus_student_id_prefixed is not null`).

- **Mint only genuinely-new students.** Guard on BOTH id forms so a returning
  student is never re-minted even if this branch runs before the migration:
  `focus_student_id_prefixed not in {{ this }}` AND bare
  `focus_student_id not in {{ this }}`.
- Reuse the existing 5-tier username algorithm and the `@teamstudents.org`
  suffix; dedupe generated usernames against `{{ this }}` exactly as the NJ
  branch does (0 collisions with the current cohort).
- Reuse the existing default-password derivation.

### 3. Make the PowerSchool branch NJ-only

Add `and _dbt_source_project != 'kippmiami'` to the PowerSchool-branch `where`.
Without it, once the migration removes bare Miami numbers from `{{ this }}`, the
PowerSchool branch (which still unions the frozen Miami archive) would treat
those `enroll_status = 0` Miami students as new and re-mint them under bare
numbers, resurrecting the retired rows. All PowerSchool-union rows carry a
region, so no null handling is needed. Sourcing becomes unambiguous: NJ via
PowerSchool, Miami via Focus.

### 4. Wire `stdt_email` in kipptaf `rpt_focus__demographics`

Replace `c.email as stdt_email` with the generated email joined from
`stg_people__student_logins` on the prefixed key:

- `left join stg_people__student_logins on <prefixed id> = <student_number>`,
  selecting `google_email as stdt_email`.
- Per repo SQL conventions, the id/type normalization for the join (string vs
  `int64`) is a **named column in an upstream CTE**, not an inline cast in the
  `ON` clause, and the swapped column must preserve the model's fixed
  `DEMOGRAPHICS` column order (the file carries a `sqlfluff/ST06` trunk-ignore).

### 5. kippmiami feed unchanged; manual backfill

- `kippmiami/.../rpt_focus__demographics.sql` (import-once anti-join) is
  **unchanged**. New enrollees not yet in Focus (~24 today) inherit the email
  automatically.
- **Manual backfill (Laszlo / Charlie):** export the kipptaf desired-state
  `rpt_focus__demographics` (all rows, now carrying email) and import once into
  Focus for the ~1,473 already-enrolled students. Map **only `stdt_id` and
  `stdt_email`** in the Focus import — the feed emits full demographics rows,
  and import-once exists precisely to prevent other Focus-managed fields from
  being overwritten.

## Data findings (verified 2026-07-23, counts only)

- **Feed cohort:** 1,497 enrolled Finalsite students with a non-null
  `focus_student_id_prefixed`.
- **Email today:** 1 has any email; 0 have `@teamstudents.org`.
- **Generation attributes:** 1,492 of 1,497 have first + last + dob.
- **Returning vs new:** 1,091 have a `powerschool_student_number` (returning);
  406 do not (new). For 1,090 returning students the bare `focus_student_id`
  equals the `powerschool_student_number`.
- **All returning students already have an account:** every one of the 1,091
  matches an existing `stg_people__student_logins` row (keyed on their bare
  number), all `@teamstudents.org`.
- **Import-once gap:** 1,473 of 1,497 are already in Focus (manual backfill); 24
  are new to Focus (automated feed).
- **Global uniqueness of `student_number`:** Miami archive 3,945 students vs
  NJ-only 26,551 students — 0 true cross-district collisions. 3,939 of the 3,945
  Miami archive students have a `stg_people__student_logins` row (the migration
  set).

## Edge cases

- **1 new student missing first/last/dob** — falls out of generation, gets no
  email, excluded from Clever. Manual handling.
- **4 returning students missing first/last/dob** — no impact; they keep their
  migrated existing email.
- **1 returning student where `powerschool_student_number` !=
  `focus_student_id`** — the mint guards check the bare and prefixed Focus id,
  not the retired PowerSchool number, so this student passes both guards and is
  minted a fresh `@teamstudents.org` email keyed to their new Focus identity.
  The migration re-keys their old PowerSchool-numbered login to `8400` + PS#,
  which is then orphaned (expected, since PowerSchool is retired).
  - **Pre-merge gate:** Ops must reconcile the PS# ↔ `focus_student_id`
    discrepancy in the source (Finalsite/Focus) before this PR merges; after the
    manual backfill, dedup-check for any student holding two `8400`-prefixed
    login rows.
- **Duplicate-username hygiene** — none, because returning students are migrated
  (re-keyed) rather than duplicated. No new username-uniqueness test is added.

## Sequencing / rollout

1. Merge the model change (branch 2 + 3) and the feed wiring (4). Dagster
   rematerializes `stg_people__student_logins` (mints the 406 new students) and
   `rpt_focus__demographics`.
1. User runs the migration DML (1). Returning-student emails now resolve on the
   prefixed key.
1. User exports the kipptaf feed and performs the manual Focus backfill (5),
   mapping only `stdt_id` + `stdt_email`.

## Files

**Modify (`kipptaf`):**

- `models/people/staging/stg_people__student_logins.sql` — Miami/Focus mint
  branch (prefixed key, double-guarded, `@teamstudents.org`), PowerSchool branch
  NJ-only filter.
- `models/people/staging/properties/stg_people__student_logins.yml` — describe
  the new sourcing; no schema change (same four columns).
- `models/extracts/focus/rpt_focus__demographics.sql` — `stdt_email` from the
  generated email; add the join and the id-normalization CTE.

**Unit tests:**

- `stg_people__student_logins` — mint a new Focus student, skip a returning
  student under both id guards, PowerSchool branch excludes `kippmiami`.
- `rpt_focus__demographics` — `stdt_email` resolves from the logins join for a
  prefixed-keyed student.

**Operational (user-run, outside dbt):**

- One-time migration DML on `stg_people__student_logins`.
- One-time manual Focus DEMOGRAPHICS backfill (email-only column mapping).

## Testing

- dbt **unit tests** per modified model (above). `stg_people__student_logins`
  generation runs only in the incremental (prod) branch — dev/staging read the
  prod source — so generation logic is validated via unit tests plus a prod
  smoke check, matching the NJ generator and the June finalsite -> focus spec.
- Post-deploy prod validation (counts only): every enrolled Miami student
  resolves a non-null `stdt_email`, and each email is unique.

## Out of scope

- Deliverable 2 (live Google Workspace account provisioning) —
  [#4511](https://github.com/TEAMSchools/teamster/issues/4511).
- Any change to the SFTP transport, filenames, or schedule.
- Any change to the kippmiami import-once reconciliation logic.
- Race/ethnicity, language, and other demographics fields.
