# Miami Student Emails into the Focus DEMOGRAPHICS Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mint a stable `@teamstudents.org` email for every enrolled KIPP Miami
(Focus) student and land it in the Focus `DEMOGRAPHICS` import (`stdt_email`).

**Architecture:** Absorb Miami into the existing network student-login generator
(`stg_people__student_logins`), keyed on the `8400`-prefixed Focus id. A new
Focus/Miami branch mints emails for genuinely-new students; a one-time migration
re-keys existing Miami rows from their bare key to the prefixed key; the
PowerSchool branch is scoped NJ-only so it never re-mints Miami. The kipptaf
desired-state `rpt_focus__demographics` reads the generated email; the kippmiami
import-once wrapper is unchanged.

**Tech Stack:** dbt (BigQuery), dbt unit tests, dbt Cloud CI, Dagster (prod
materialization), BigQuery MCP for validation.

**Spec:**
`docs/superpowers/specs/2026-07-23-miami-student-emails-focus-import-design.md`

## Global Constraints

- **Email domain suffix:** `@teamstudents.org` (verbatim; same as NJ). No
  Miami-specific domain.
- **Prefixed key:** `cast(concat('8400', cast(<bare> as string)) as int64)` —
  equals Focus `students.student_id` and the feed's `stdt_id`.
- **Warehouse project:** `teamster-332318`. Logins table:
  `kipptaf_people.stg_people__student_logins`. Miami PS archive:
  `kippmiami_powerschool.stg_powerschool__students`.
- **SQL conventions** (`.trunk/config/.sqlfluff`, BigQuery): trailing commas in
  `SELECT`, single quotes, 88-char lines, no `QUALIFY`, no `ORDER BY`, cast once
  as a named column (never inline in `WHERE`/`ON`). Mirror the existing model's
  `student_number not in (select t.student_number, from {{ this }} as t)` idiom
  — it predates the no-subquery guideline and is the established pattern in this
  specific model.
- **Migration is user-run DML.** Claude is DML/DDL-blocked (BigQuery MCP + `bq`
  are SELECT-only); the migration `UPDATE` and the manual Focus backfill are
  executed by the user, not committed.
- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails`. Use
  `uv run dbt ... --project-dir <worktree>/src/dbt/kipptaf` and
  `git -C <worktree>`.
- **Lint gate:** run
  `/workspaces/teamster/.trunk/tools/trunk check --force <changed files>` from
  inside the worktree before pushing (sqlfluff/yamllint fire at pre-push/CI, not
  the pre-commit `fmt` hook).

---

## Task 0: Worktree setup

**Files:** none (environment prep).

- [ ] **Step 1: Install dbt packages in the fresh worktree**

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails/src/dbt/kipptaf
```

Expected: `Installed N packages` (no "0 package(s) installed" error).

- [ ] **Step 2: Confirm the prod manifest exists for `--defer`**

Run:

```bash
ls /workspaces/teamster/src/dbt/kipptaf/target/prod/manifest.json
```

Expected: the path prints (main repo's manifest, refreshed by `post-merge`). If
missing, regenerate:
`uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipptaf --target-path target/prod`.

---

## Task 1: Wire `stdt_email` in `rpt_focus__demographics` (TDD)

Point the Focus DEMOGRAPHICS `stdt_email` at the generated login email instead
of the always-empty Finalsite contact email. `rpt_focus__demographics` is a flat
view (no `env_var`/`is_incremental` branching), so it is fully unit-testable.

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml`
- Test: same `properties/rpt_focus__demographics.yml` (`unit_tests:` block)

**Interfaces:**

- Consumes: `stg_people__student_logins` columns `student_number` (int64) and
  `google_email` (string), joined on the string form of `student_number` =
  `int_finalsite__contact_id_attributes.focus_student_id_prefixed`.
- Produces: `rpt_focus__demographics.stdt_email` (string) = the generated
  `@teamstudents.org` email, or null when the student has no login row.

- [ ] **Step 1: Update the failing unit test**

In `properties/rpt_focus__demographics.yml`, add a `stg_people__student_logins`
input to `test_demographics_shape.given` (place it after the existing
`int_finalsite__contact_id_attributes` input):

```yaml
- input: ref('stg_people__student_logins')
  format: sql
  rows: |
    select
      84001001001 as student_number,
      'jsmith@teamstudents.org' as google_email
```

Then change the three `expect` rows' `stdt_email` values:

```yaml
# enr-001 (stdt_id 84001001001) — has a login row → generated email, NOT c.email
stdt_email: jsmith@teamstudents.org
# enr-002 (stdt_id 84001001002) — no login row → null
stdt_email: null
# enr-003 (stdt_id 84001001003) — no login row → null
stdt_email: null
```

Also update the `test_demographics_shape` description's leading sentence to note
the new source, replacing the existing first sentence:

```yaml
description:
  Verifies the 42-column DEMOGRAPHICS layout — STDT_ID and STDT_EMAIL are
  sourced from int_finalsite__contact_id_attributes and
  stg_people__student_logins (joined on the 8400-prefixed id); the first student
  has a login row so STDT_EMAIL is the generated google_email (not the Finalsite
  contact email), while the second and third have no login row so STDT_EMAIL is
  null. DT_BIRTH is formatted as YYYYMMDD, GENDER is mapped to a single-letter
  code, ETHNIC_HL derives from
  int_finalsite__contact_custom_attributes.latino_hispanic_yn. The second
  student has no custom-attributes row, confirming ETHNIC_HL is null (not 'N')
  for an unknown while PHOTO_VID_PERM defaults to 'N'. The third student has a
  custom-attributes row whose lang_parent_ss has no crosswalk entry, confirming
  the language columns fall through to null (not the raw label). The fourth
  student has no int_finalsite__contact_id_attributes row (no minted Focus id)
  and is excluded from the extract. The fifth student has status 'applied' (not
  'enrolled') and a minted Focus id, confirming the enrolled-only filter — not
  the missing-id filter — excludes them.
```

- [ ] **Step 2: Run the unit test to verify it fails**

Run:

```bash
uv run dbt test --select test_demographics_shape \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: FAIL — either `stdt_email` mismatch (still resolving `c.email`) or a
missing-input error for `stg_people__student_logins` (the model does not yet
join it).

- [ ] **Step 3: Add the login join and repoint `stdt_email`**

Edit `rpt_focus__demographics.sql`. Add a leading CTE that derives the string
join key (real work — a cast — so not a banned pass-through CTE), then join it
and swap the `stdt_email` source. The full file becomes:

```sql
with
    student_logins as (
        select
            google_email,

            cast(student_number as string) as focus_student_id_prefixed,
        from {{ ref("stg_people__student_logins") }}
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus DEMOGRAPHICS contract
select
    ida.focus_student_id_prefixed as stdt_id,

    c.last_name,
    c.first_name,

    cast(null as string) as name_suffix,

    c.middle_name,
    c.preferred_name as nickname,

    format_date('%Y%m%d', c.birth_date) as dt_birth,

    case
        when c.gender in ('M', 'Male')
        then 'M'
        when c.gender in ('F', 'Female')
        then 'F'
    end as gender,

    -- LANG, PRIMARY_HOME_LANG, and NATIVE_PARENT_LANG all draw the same Focus
    -- value code from the language crosswalk. NOTE: the Focus LANG field
    -- (custom_200000005) historically carried a legacy 3-option set
    -- (EN/English/Spanish); pending registrar confirmation it is assumed to
    -- accept the same FLDOE code as the home/native-language fields.
    lcc.focus_language_code as lang,

    sl.google_email as stdt_email,

    -- null (not 'N') when no custom_attributes row exists, so an unknown is not
    -- silently reported as not-Hispanic for FLDOE.
    case
        when cca.latino_hispanic_yn then 'Y' when not cca.latino_hispanic_yn then 'N'
    end as ethnic_hl,

    cast(null as string) as single_ethnic,

    if('American Indian' in unnest(cca.race_ms), 'Y', null) as race_am_ind_ak_nat,
    if('Asian' in unnest(cca.race_ms), 'Y', null) as race_asian,
    if('Black' in unnest(cca.race_ms), 'Y', null) as race_black,
    if(
        'Native Pacific Islander' in unnest(cca.race_ms), 'Y', null
    ) as race_nat_haw_pac_isl,
    if('White' in unnest(cca.race_ms), 'Y', null) as race_white,

    cast(null as string) as residence_county,
    cast(null as string) as contry_birth,
    cast(null as string) as homeroom_tchr,
    cast(null as string) as resident_st,
    cast(null as string) as birth_loc,
    cast(null as string) as bdate_verif,
    cast(null as string) as immun_st,

    lcc.focus_language_code as primary_home_lang,
    lcc.focus_language_code as native_parent_lang,

    cast(null as string) as grde_enter_dist,
    cast(null as string) as msix_id,
    cast(null as string) as homeroom,
    cast(null as string) as pmrn,
    cast(null as string) as internt_perm,
    cast(null as string) as act_perm,
    cast(null as string) as direct_perm,
    cast(null as string) as screen_perm,

    if(cca.media_release_yn, 'Y', 'N') as photo_vid_perm,

    cast(null as string) as survey_perm,
    cast(null as string) as mckay_sch_attend,
    cast(null as string) as fhsaa_el3_ind,
    cast(null as string) as fhsaa_el3ch_ind,
    cast(null as string) as dt_home_lang_survey,
    cast(null as string) as casas_track,
    cast(null as string) as lcp_cont_stdt,
from {{ ref("stg_finalsite__contacts") }} as c
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
left join
    {{ ref("int_finalsite__contact_custom_attributes") }} as cca
    on c.finalsite_enrollment_id = cca.finalsite_enrollment_id
left join
    {{ ref("stg_google_sheets__focus__language_code_crosswalk") }} as lcc
    on cca.lang_parent_ss = lcc.finalsite_language
left join
    student_logins as sl
    on ida.focus_student_id_prefixed = sl.focus_student_id_prefixed
where c.status = 'enrolled'
```

- [ ] **Step 4: Update the `stdt_email` column description**

In `properties/rpt_focus__demographics.yml`, replace the `stdt_email`
description:

```yaml
- name: stdt_email
  data_type: string
  description:
    Student KIPP email (Focus STDT_EMAIL) from
    stg_people__student_logins.google_email, joined on the 8400-prefixed Focus
    id. Null when the student has no minted login yet.
```

- [ ] **Step 5: Run the unit test to verify it passes**

Run:

```bash
uv run dbt test --select test_demographics_shape \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS (1 of 1).

- [ ] **Step 6: Run the whole focus-extracts unit-test directory**

Sibling focus models mock overlapping refs; confirm none broke.

```bash
uv run dbt test --select "test_type:unit,extracts.focus" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all PASS.

- [ ] **Step 7: Lint the changed files**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml </dev/null
```

Expected: `No issues` (a `prettier`/`fmt` reflow is auto-applied at commit — not
a failure).

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__demographics.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__demographics.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails commit \
  -m "feat(focus): source demographics stdt_email from generated student login"
```

---

## Task 2: Absorb Miami into `stg_people__student_logins`

Add a Focus/Miami mint branch (prefixed key, double-guarded) and scope the
PowerSchool branch NJ-only. This model has an `env_var`/`is_incremental` branch
structure — the generation logic runs ONLY in the prod incremental branch, so it
is not exercised by dbt Cloud CI (staging reads the prod table via `source()`)
and cannot be unit-tested here (no repo unit test overrides `is_incremental`).
It is validated by `dbt parse` (Jinja/refs) plus a prod-simulation SELECT.

**Files:**

- Modify: `src/dbt/kipptaf/models/people/staging/stg_people__student_logins.sql`

**Interfaces:**

- Consumes: `stg_powerschool__students` (`student_number`, `dob`, `first_name`,
  `last_name`, `enroll_status`, `_dbt_source_project`);
  `stg_finalsite__contacts` (`finalsite_enrollment_id`, `first_name`,
  `last_name`, `birth_date`, `status`); `int_finalsite__contact_id_attributes`
  (`finalsite_enrollment_id`, `focus_student_id`, `focus_student_id_prefixed`).
- Produces: rows in `stg_people__student_logins` (`student_number` int64,
  `username`, `default_password`, `google_email`) for new Miami students keyed
  on the `8400`-prefixed id. Consumed by Task 1's join.

- [ ] **Step 1: Edit the incremental branch**

In `stg_people__student_logins.sql`, replace the `components as (...)` CTE
(inside the `{% elif is_incremental() %}` block) with a Focus-union version and
add the NJ-only filter. The new CTE block:

```sql
    with
        miami_candidates as (
            select
                c.first_name,
                c.last_name,
                c.birth_date,

                cast(ida.focus_student_id_prefixed as int64) as student_number,
                cast(ida.focus_student_id as int64) as student_number_bare,
            from {{ ref("stg_finalsite__contacts") }} as c
            inner join
                {{ ref("int_finalsite__contact_id_attributes") }} as ida
                on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
                and ida.focus_student_id_prefixed is not null
            where c.status = 'enrolled'
        ),

        components as (
            select
                student_number,

                format_date('%m', dob) as dob_month,
                format_date('%d', dob) as dob_day,
                format_date('%y', dob) as dob_year,

                regexp_replace(
                    normalize(lower(first_name), nfd), r'[\pM\W]', ''
                ) as first_name_clean,

                regexp_replace(
                    normalize(
                        lower(regexp_replace(last_name, r'\s[IiVvXxJjRr\.]*$', '')), nfd
                    ),
                    r'[\pM\W]',
                    ''
                ) as last_name_clean,
            from {{ ref("stg_powerschool__students") }}
            where
                student_number not in (select t.student_number, from {{ this }} as t)
                and _dbt_source_project != 'kippmiami'
                and dob is not null
                and first_name is not null
                and last_name is not null
                and enroll_status = 0

            union all

            select
                student_number,

                format_date('%m', birth_date) as dob_month,
                format_date('%d', birth_date) as dob_day,
                format_date('%y', birth_date) as dob_year,

                regexp_replace(
                    normalize(lower(first_name), nfd), r'[\pM\W]', ''
                ) as first_name_clean,

                regexp_replace(
                    normalize(
                        lower(regexp_replace(last_name, r'\s[IiVvXxJjRr\.]*$', '')), nfd
                    ),
                    r'[\pM\W]',
                    ''
                ) as last_name_clean,
            from miami_candidates
            where
                student_number not in (select t.student_number, from {{ this }} as t)
                and student_number_bare
                not in (select t.student_number, from {{ this }} as t)
                and birth_date is not null
                and first_name is not null
                and last_name is not null
        ),
```

Leave `username_options`, `username_filter`, `username_password`, and the final
`select *, username || '@teamstudents.org' as google_email` UNCHANGED — the
shared username-generation and dedupe-against-`{{ this }}` logic now applies to
the unioned Miami rows automatically. Leave the `dev`/`staging` and `else`
branches and the trailing `-- depends_on:` comments unchanged.

- [ ] **Step 2: Parse to verify Jinja and refs resolve**

```bash
uv run dbt parse \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails/src/dbt/kipptaf \
  --target dev
```

Expected: `Wrote manifest` / no parse error. (Parse renders the non-incremental
branch, so it will not surface SQL errors inside the incremental branch — those
are caught in Step 3.)

- [ ] **Step 3: Validate the mint branch against prod (SELECT-only simulation)**

The incremental branch never runs in CI/dev, so validate its logic directly. Run
via the BigQuery MCP (`mcp__bigquery__execute_sql`). This mirrors the
`miami_candidates` + guard logic against live prod and confirms the guards
select the ~406 genuinely-new students (not the 1,091 returning):

```sql
with
  miami_candidates as (
    select
      cast(ida.focus_student_id_prefixed as int64) as student_number,
      cast(ida.focus_student_id as int64) as student_number_bare,
      c.birth_date,
      c.first_name,
      c.last_name,
    from `teamster-332318.kipptaf_finalsite.stg_finalsite__contacts` as c
    inner join
      `teamster-332318.kipptaf_finalsite.int_finalsite__contact_id_attributes` as ida
      on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
      and ida.focus_student_id_prefixed is not null
    where c.status = 'enrolled'
  ),
  existing as (
    select student_number
    from `teamster-332318.kipptaf_people.stg_people__student_logins`
  )
select
  count(*) as candidates,
  countif(
    m.student_number not in (select student_number from existing)
    and m.student_number_bare not in (select student_number from existing)
    and m.birth_date is not null
    and m.first_name is not null
    and m.last_name is not null
  ) as would_mint,
  countif(m.student_number_bare in (select student_number from existing)) as returning_skipped
from miami_candidates as m
```

Expected: `candidates` ≈ 1497, `would_mint` ≈ 405–406 (the new-to-KIPP cohort
minus any missing first/last/dob), `returning_skipped` ≈ 1090. If `would_mint`
is ~1497, the guards are wrong (they are not excluding returning students) —
stop and fix before committing.

- [ ] **Step 4: Lint the changed file**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/people/staging/stg_people__student_logins.sql </dev/null
```

Expected: `No issues`.

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails add \
  src/dbt/kipptaf/models/people/staging/stg_people__student_logins.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-miami-student-emails commit \
  -m "feat(people): mint Miami Focus student logins; scope PowerSchool branch NJ-only"
```

---

## Task 3: Open the PR

**Files:** none (GitHub).

- [ ] **Step 1: Push and open the PR**

Push the branch (hand to the user if `git push` is classifier-blocked), then
open a PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md` as the body and `Closes #4512` in it.

- [ ] **Step 2: Verify CI**

dbt Cloud CI (`Build - CI (Modified)`) will select `rpt_focus__demographics`
(and its unit test) under `state:modified+`; `stg_people__student_logins` is
`state:modified` but its generation branch is not exercised in staging. Confirm
both the dbt Cloud commit status and the Trunk/`claude` check-runs are green
(the two disjoint CI surfaces). After green, fetch warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`.

- [ ] **Step 3: Merge after CODEOWNERS approval**

`src/dbt/` requires an analytics-engineer review (CODEOWNERS); a green PR may
read `mergeable_state: blocked` awaiting that approval. Squash-merge once
approved.

---

## Task 4: Post-merge operations (user-run — NOT committed)

These run against prod after the code deploys. Claude is DML-blocked; the user
executes them. Order matters.

**Pre-merge gate:** Do NOT merge until Ops reconciles the PS# ↔
`focus_student_id` discrepancy in the source.

- [ ] **Step 1: Confirm the code deploy landed**

After merge, Dagster redeploys kipptaf and the
`kipptaf__automation_condition_sensor` rematerializes the changed models.
Confirm via `get_location_load_history` (new commit LOADED) and a
materialization of `kipptaf/people/stg_people__student_logins`. The incremental
run mints the ~406 new students (prefixed key) but does NOT touch returning
students yet.

- [ ] **Step 2: Run the migration DML (user, in their terminal)**

Re-key existing Miami rows from the bare key to the `8400`-prefixed key. This is
a warehouse mutation of a shared identity table — the user must run it with
named consent:

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

Expected: ~3,939 rows updated. Safe re-run: already-prefixed rows (`8400…`) are
not in the archive set, so a second execution matches nothing.

- [ ] **Step 3: Verify the migration (SELECT, Claude or user)**

```sql
select
  countif(regexp_contains(cast(student_number as string), r'^8400[0-9]{6}$')) as prefixed_rows,
  countif(
    student_number in (
      select distinct student_number
      from `teamster-332318.kippmiami_powerschool.stg_powerschool__students`
      where student_number >= 1
    )
  ) as remaining_bare_miami
from `teamster-332318.kipptaf_people.stg_people__student_logins`
```

Expected: `prefixed_rows` ≈ 3,939 (plus 406 newly minted ≈ 4,345 total
prefixed); `remaining_bare_miami` = 0.

- [ ] **Step 4: Verify `stdt_email` populates in the feed (SELECT)**

After the next `rpt_focus__demographics` materialization:

```sql
select
  count(*) as cohort,
  countif(stdt_email is not null) as with_email,
  count(distinct stdt_email) as distinct_emails
from `teamster-332318.kipptaf_extracts.rpt_focus__demographics`
```

Expected: `with_email` ≈ 1,496 (cohort − 1). The PS# ≠ `focus_student_id`
student now receives a fresh mint and is no longer excluded; only the 1
genuinely-new student missing first/last/dob stays null. `distinct_emails` ≈
`with_email` (no duplicate emails).

- [ ] **Step 5: Manual Focus backfill (user)**

Export `kipptaf_extracts.rpt_focus__demographics` (all rows, now carrying email)
and import once into Focus for the ~1,473 already-enrolled students. **Map only
`stdt_id` and `stdt_email`** in the Focus import so no other Focus-managed
demographics fields are overwritten. Going forward, new enrollees receive the
email automatically through the unchanged kippmiami import-once wrapper.

---

## Self-Review

**Spec coverage:**

- Spec §1 (migration) → Task 4 Step 2–3.
- Spec §2 (Miami mint branch) → Task 2 Step 1 (union branch) + Step 3
  validation.
- Spec §3 (PS branch NJ-only) → Task 2 Step 1
  (`_dbt_source_project != 'kippmiami'`).
- Spec §4 (wire `stdt_email`) → Task 1.
- Spec §5 (kippmiami unchanged; manual backfill) → no code change (confirmed
  unchanged); backfill → Task 4 Step 5.
- Spec sequencing → Task 3 (deploy) → Task 4 (migration → backfill).
- Spec edge cases (5 missing-attr, 1 PS≠focus) → Task 4 Step 4 expected count
  reflects the 1 genuinely-new null (PS≠focus now mints fresh, no longer null).

**Placeholder scan:** none — every code/SQL step is complete.

**Type consistency:** `student_number` is int64 throughout; the join key is
`cast(student_number as string)` = `focus_student_id_prefixed` (string) in both
Task 1 (feed CTE) and Task 2 (mint keys). `google_email` is string in the mock,
the model, and the feed. Consistent.

---

## Execution Handoff

Two execution options:

1. **Subagent-Driven (recommended)** — a fresh subagent per task with review
   between tasks. Note: Task 2 must be dispatched with the absolute worktree
   path and the instruction to use `git -C <worktree>` + `uv run --project-dir`,
   and that IDE Pyright/SQL diagnostics on worktree files are false positives.
2. **Inline Execution** — execute in this session with checkpoints.

Tasks 1–3 are code; Task 4 is operational and user-run (migration DML + Focus
backfill) after merge and deploy.
