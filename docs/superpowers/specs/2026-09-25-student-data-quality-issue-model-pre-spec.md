# Student data quality: a per-check issue model

**Pre-spec for [#5549](https://github.com/TEAMSchools/teamster/issues/5549).**
This is a proposal to argue with, not a plan to execute. It carries a design,
the evidence behind it, the sources each decision came from, and 6 open
questions the team has to settle. No implementation plan exists yet, and none
should until the open questions close.

**Read this first if you read nothing else:** 3 of the 9 checks we run today are
wrong, and one of them is 58% of everything on the dashboard. Section 1 has the
measurements. Rebuilding delivery on top of the current checks would ship a
faster path to wrong work.

---

## 1. What is actually broken

The network surfaces student data problems through one Tableau dashboard over
`rpt_tableau__student_info_audit` — a 343-line model with 9 `UNION ALL`
branches. The dashboard does not drive corrections.

Three problems are organizational:

- Nobody goes looking. It is a pull surface in a tool school staff do not open.
- Adding a check is expensive. It means editing the union model and republishing
  a workbook.
- Nobody owns a flag. There is no aging, no resolution, and no way for a
  regional team to see who is behind.

A fourth problem is in the data itself. Every figure below comes from a query
against `teamster-332318.kipptaf_tableau.rpt_tableau__student_info_audit` on
2026-09-23, and every one is an aggregate.

### 1.1 Two checks are 69% of the volume

The network carries 3,009 flagged rows. The distribution is not close to even.

| Region    | Check                      | Rows | Students |
| --------- | -------------------------- | ---: | -------: |
| Miami     | Missing or Incorrect FTEID | 1744 |     1744 |
| Paterson  | Missing SID                |  338 |      338 |
| Newark    | Enrollment Dupes           |  364 |       60 |
| All other | All other checks           | ~563 |          |

### 1.2 The FTEID check does not apply to Miami

Every one of Miami's 1,744 FTEID flags carries `detail = 'MISSING'`, meaning
`fteid` is null for every Miami student in the model. The check left-joins
`stg_powerschool__fte`. Miami runs Focus, not PowerSchool, so the join can never
match.

Newark and Camden produce 11 genuine mismatches between them, with specific and
plausible details such as `1761 != 1762`. The check works correctly where it
applies. It simply has no way to say where that is.

### 1.3 The name check flags accented names

`Name Spelling` uses the pattern `[^\w\s',-]`. BigQuery's RE2 engine matches
`\w` against ASCII characters only, so every diacritic matches the "illegal
character" class. Verified directly with literals, not student records:

| Input           | Flagged |
| --------------- | ------- |
| `Jose`          | no      |
| `José`          | **yes** |
| `O'Brien-Smith` | no      |
| `Smith  Jones`  | yes     |

46 of the 88 `Name Spelling` flags carry a character outside `\x00-\x7F`. The
check tells school staff that correctly spelled Spanish surnames are misspelled,
in a network whose 4 regions serve large Hispanic populations. The double-space
detection is genuinely useful and should survive; the character class should
not.

NJ SLEDS publishes a rule for this element. It rejects periods, permits
apostrophes and hyphens, and says nothing about accents.

### 1.4 One check has never fired

`Missing DOB` returns 0 rows against 11,490 enrollments.

### 1.5 What this means

Anyone who opened the dashboard, saw a wall of Miami, and left was behaving
correctly. "Nobody goes looking" is partly a consequence of the checks, not an
independent problem. Fix the checks first.

---

## 2. The design

One sentence: **checks know nothing about delivery, delivery knows nothing about
checks, and they meet at one table.**

### 2.1 Components

| #   | Component      | What it is                                                                                                                                                                 |
| --- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Student spine  | `int_students__data_quality_spine`, materialized. One row per student per academic year, carrying every field any check needs. Serves PowerSchool and Focus regions alike. |
| 2   | Check register | A Google Sheet, staged in. One row per check per region: label, fix instructions, owning role, owner scope, severity, active flag.                                         |
| 3   | Check models   | One small model per check, fixed 6-column contract, emitting only failing rows.                                                                                            |
| 4   | Issue fact     | Unions the check models, joins the register for metadata and scope, joins the spine for routing.                                                                           |
| 5   | Issue state    | Append-only event table keyed on an issue signature. Gives first-detected dates, aging, time-to-fix, and reopen counts.                                                    |
| 6   | Waiver input   | A sheet, staged in, joined as a **status** rather than a filter.                                                                                                           |
| 7   | Delivery       | Per-owner worklist and weekly digest. Reads the fact. Knows no check names.                                                                                                |
| 8   | Waiver hygiene | An anti-join listing waivers whose issue stopped firing.                                                                                                                   |

### 2.2 The check contract

Every check model returns exactly these columns, and a shared generic test
enforces it:

```text
student_number · _dbt_source_project · academic_year
check_name · detail · detail_hash
```

`detail_hash` is a surrogate key over student, check, detail, and year. It is
the issue signature, and waivers key on it. A changed underlying value produces
a different hash, which re-arms the check automatically.

This contract is the load-bearing decision in the whole design. dbt Labs
deliberately did not union their 24 rule models in `dbt-project-evaluator`
because each has a different column set. The first check that wants a seventh
column collapses this design back into an unjoined pile, so the contract needs a
test rather than a convention.

### 2.3 Scope lives in the register

The register holds `(check_name, region)` rows. The fact applies them with an
inner join. Miami never receives an FTEID row because no such row exists in the
register — not because somebody remembered to write `where region != 'Miami'`
inside a branch.

One branch of the current model already carries region-specific logic
([lines 88-99](https://github.com/TEAMSchools/teamster/blob/anthonygwalters/docs/claude-student-data-quality-pre-spec/src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__student_info_audit.sql#L88-L99)),
buried where no reader would find it. Section 5 has the open question about
whether scope belongs in the fact or in each check.

### 2.4 Waivers mark, they do not remove

A waived issue still appears in the fact, flagged as waived. Three consequences:

- "How much has this school waived" becomes a queryable number.
- A changed value re-arms the check without anyone touching the waiver.
- Waivers are auditable, because the rows they cover are still visible.

This reverses the first draft of this design, which anti-joined waivers out.
Section 6 explains why.

### 2.5 Aggregation is by owner, not by school

The accountability unit is the owning team. School and region are attributes of
the owner rather than the grouping key. One row of the rollup is one message:

- "Newark compliance team: 22 open items."
- "Campus ops at [school]: 6 open items."

The register resolves `(check_name, region)` to an owning role and an owner
scope, because the same check plausibly belongs to campus ops in one region and
a regional team in another. Staffing is a people fact, so it lives in the sheet
where it changes without a deploy.

An issue is owned by exactly one team at a time. When it ages past a threshold,
ownership escalates one scope level, so the regional list becomes "what your
campuses have not cleared" rather than a copy of the campus list.

### 2.6 What the rollup should measure

Not raw open counts. An open count is a school-size proxy, it weights a missing
state identifier the same as an enrollment duplicate, and it cannot tell a
school that cleared 40 items and received 40 new ones from a school that did
nothing.

Four primitives instead: aging buckets by severity, median time-to-fix, opened
against resolved in period, and waiver rate. Waiver rate only exists because
waivers are a status; the first draft of this design made it structurally
invisible.

---

## 3. A worked check

`Missing or Incorrect FTEID`, chosen because it is the check that broke, and
because it needs its own join — the case a YAML rule registry could not express.

`models/students/data_quality/dq_student__missing_or_incorrect_fteid.sql`:

```sql
with
    fte_expected as (
        select
            schoolid,
            yearid,
            _dbt_source_project,

            id as expected_fteid,
        from {{ ref("stg_powerschool__fte") }}
        where name like 'Full Time Student%'
    ),

    fte_compared as (
        select
            s.student_number,
            s._dbt_source_project,
            s.academic_year,

            'missing_or_incorrect_fteid' as check_name,

            cast(s.fteid as string) as fteid_string,
            cast(f.expected_fteid as string) as expected_fteid_string,
        from {{ ref("int_students__data_quality_spine") }} as s
        left join
            fte_expected as f
            on s.schoolid = f.schoolid
            and s.yearid = f.yearid
            and s._dbt_source_project = f._dbt_source_project
    ),

    fte_detail as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            check_name,

            case
                when fteid_string is null
                then 'MISSING'
                when fteid_string = '0'
                then 'FTE == 0'
                when fteid_string != expected_fteid_string
                then concat(fteid_string, ' != ', expected_fteid_string)
            end as detail,
        from fte_compared
    )

select
    student_number,
    _dbt_source_project,
    academic_year,
    check_name,
    detail,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "check_name", "detail", "academic_year"]
        )
    }} as detail_hash,
from fte_detail
where detail is not null
```

Today the same logic sits in 2 places 180 lines apart: the `detail` expression
at lines 68-86 of the union model, and the `flag` in its `UNION ALL` branch at
lines 252-267.

The fact that unions the checks:

```sql
{%- set checks = [
    "dq_student__enrollment_dupes",
    "dq_student__missing_or_incorrect_fteid",
    "dq_student__missing_state_id",
] -%}

with
    all_issues as (
        {%- for check in checks %}
        select
            student_number,
            _dbt_source_project,
            academic_year,
            check_name,
            detail,
            detail_hash,
        from {{ ref(check) }}
        {%- if not loop.last %}
        union all
        {%- endif %}
        {%- endfor %}
    )

select
    i.student_number,
    i.academic_year,
    i.check_name,
    i.detail,
    i.detail_hash,

    s.schoolid,
    s.region,

    c.label,
    c.severity,
    c.owning_role,
    c.owner_scope,
from all_issues as i
inner join
    {{ ref("int_students__data_quality_spine") }} as s
    on i.student_number = s.student_number
    and i.academic_year = s.academic_year
    and i._dbt_source_project = s._dbt_source_project
inner join
    {{ ref("stg_google_sheets__data_quality_checks") }} as c
    on i.check_name = c.check_name
    and s.region = c.region
where c.is_active
```

Neither block compiles today. The spine does not exist, and the column names
assume it carries `yearid` and `fteid`. Treat both as illustrations of shape.

Adding a check costs one file and one line in the list. Nothing downstream
changes.

---

## 4. Phasing

| Phase                             | What lands                                                                                |             dbt nodes |
| --------------------------------- | ----------------------------------------------------------------------------------------- | --------------------: |
| 0 — Check audit                   | All 9 checks re-derived against published state rules. Fix, scope, or retire each.        |                     0 |
| 1 — Spine, register, checks, fact | Replaces the current model. The existing dashboard repoints. Nothing user-facing changes. |                   ~11 |
| 2 — State and waivers             | Aging, time-to-fix, waivers, hygiene report.                                              |                    ~3 |
| 3 — Delivery                      | Per-owner push, regional rollup, deep links.                                              | ~2 plus orchestration |

Phase 0 is mostly analyst and sysadmin time rather than engineering, and it is
independently valuable. NJ SMART publishes a 9-part element template and Florida
publishes Edit Specifications; both are copy-ready.

Four things drive the estimate:

1. The spine spanning PowerSchool and Focus. This is the largest unknown, and
   every check's correctness depends on it.
2. Phase 2's state table. No prior art exists anywhere the research reached, so
   pad it.
3. `detail` string stability. A check that changes how it renders `detail`
   re-arms every waiver keyed to that hash. This is an ongoing maintenance tax,
   not a one-time cost.
4. The SIS deep-link URL shape. PowerSchool's developer documentation is behind
   a login, so nobody has verified it. It is a 2-minute empirical test against a
   live instance and the highest-leverage detail in Phase 3.

### 4.1 Alerting

Dagster already carries the sending half. `EmailResource` in
`src/teamster/libraries/email/resources.py` opens one authenticated SMTP
connection and holds it open, and `send_message()` supports a recipient, a text
body, and an HTML alternative.

The gap is narrow. `send_email_op` takes a single subject and body from config
and BCC-blasts identical content to batches, and its `template_path` is a static
file read, with no variable substitution. A per-owner digest needs a sibling op
that groups by owner and renders one message each.

Three rules decide whether a weekly email survives past month 2. Never send an
empty one. Cap the detail list with an explicit "showing 25 of 60" marker. Send
one email per owner per week, never one per check.

Phase 2 is what makes the email worth opening. "3 new this week, 5 cleared, 2
open longer than 30 days" is a different message from "you have 10 items", and
it costs nothing extra once the event table exists.

Use distribution lists rather than named staff addresses. Staffing churn stops
being a data change, and individual staff contact details stay out of a shared
sheet.

---

## 5. Open questions

These are the decisions this pre-spec does not make. Argue with them in the PR.

1. **Does scope belong in the fact or in each check?** The fact gives one
   enforcement point and a sheet edit to change scope. Each check gives a reader
   the answer without opening another file, and avoids computing rows that get
   discarded. ISO 8000-8 clause 5.1 requires that unchecked rules be listed,
   which argues for the central version.
2. **What is the first delivery surface?** A per-school Google Sheet gives a
   writable column and a natural resolution loop. An email digest pushes
   hardest. The research argues a Tableau table cannot be the answer, because it
   has no per-row state.
3. **Who may waive, and at what scope?** A campus clearing its own list is a
   different risk from a regional team doing it.
4. **What is the escalation threshold?** 30 days is a guess.
5. **Does the check audit block Phase 1, or run beside it?** Shipping the
   architecture with known-wrong checks is the fastest route to a worse problem
   than the one we have.
6. **How many checks launch?** The register's active flag makes staged rollout a
   sheet edit. Starting with 3 or 4 high-confidence checks and widening is safer
   than launching all 9.

---

## 6. Provenance

Nothing here is invented. The shape has been load-bearing elsewhere.

- **Kimball's error event schema**, ETL subsystem 5 of 34, published 2004: an
  error event fact, an error event detail fact, and a `Screen` table holding the
  checks and their metadata. This design is a rediscovery of it.
- **`dbt-labs/dbt-project-evaluator`**: 24 rules, one `fct_` model each, each
  ending in a `filter_exceptions()` macro. Released v1.3.5 on 2026-09-02. Nobody
  tried the per-check shape and abandoned it.
- **dbt-core issue #4613**, open since 2022-01-24, requests exactly the
  persisted unified failure table proposed here, from someone wanting to "push
  out responsibility for correction outside of the data engineering team."
- **Ed-Fi's validation result signature**, `(rule_code, resource_id)` unique
  across runs, is the model for the issue signature. Ed-Fi also puts suppression
  in the consuming system, explicitly outside the rules engine, and mandates a
  per-result cap with a truncation flag.
- **ISO 8000-8 clause 5.1** requires that unchecked rules be listed. This is why
  waivers mark rather than remove.
- **detect-secrets** keys suppressions on a content hash, with a source comment
  saying line numbers are excluded "because line numbers are subject to change."
  **Osmose** binds a dismissal to the element version, so any edit re-arms the
  check. Both argue for `detail_hash`.
- **ESLint, PHPStan, mypy, Psalm, and golangci-lint** all detect unused
  suppressions, and 2 of them default it on. Only 2 of 15 surveyed systems have
  waiver expiry. Unused-waiver detection is the feature the ecosystem converged
  on.
- **Osmose, KeepRight, MapRoulette, and Wikidata constraint reports** are the
  most mature at-scale examples of routing errors to non-engineers who fix them
  in the source system. All 4 are per-item worklists with per-item state.
  Wikidata shows the violation on the entity page the editor already has open.

### 6.1 From our own codebase

`stg_google_sheets__gradebook_exceptions` supplies both a warning and a gift. It
keys partly on `view_name` and `cte` — the implementation location in the SQL —
so any refactor of the detection models silently misapplies its waivers, and 21
sites reference it. Do not copy that key shape.

It does carry `academic_year`, which gives automatic annual expiry. Keep that.

---

## 7. What this is not

- **Not a PowerSchool plugin.** Plugins cost too much to build, break across SIS
  upgrades, and Miami runs Focus, so a plugin reaches at most 3 of 4 regions.
- **Not a generic entity model.** Student-grained only. Widening later stays
  additive.
- **Not a purchased tool.** Soda, Great Expectations, Elementary, Monte Carlo,
  and Bigeye are all engineer-facing alert triage on a check against a table,
  plus a ticketing hook. None models a work item routed to the person who
  retypes the value in the SIS. Elementary's own documentation describes it as
  built for data and analytics engineers, its grain is one row per test
  execution, and it writes 5 sample failing rows into the warehouse by default.
- **Not built on dbt tests.** `+store_failures: true` and
  `+store_failures_as: view` already apply project-wide, but a model cannot
  `ref()` a test relation — `REFABLE_NODE_TYPES` covers models, seeds, and
  snapshots only. Stored failure relations also drop and recreate each run, and
  test `meta` is unrecoverable at query time. A check expected to produce
  failing rows every day would also make "tests passing" meaningless.
- **Not a per-school score.** A composite score obscures which check drives the
  number, invites denominator arguments instead of fixes, and would have ranked
  Miami's schools last for years because of a bug in our own SQL.
- **Not the sibling audits.** `rpt_tableau__assessment_entry_audit`,
  `_assessment_tag_audit`, `_ddi_audit`, and `_staff_job_salary_audit` share no
  contract with the student audit and stay out of scope.

---

## 8. Confidence

Verified by query or by reading the files in this repo:

- The Miami FTEID measurements, including that every row carries
  `detail = 'MISSING'`.
- The name-check regex behavior and the 46-of-88 count.
- The `stg_google_sheets__gradebook_exceptions` key columns and its 21 reference
  sites.
- The project-wide `store_failures` configuration and the
  `data_quality_dashboard` exposure.
- The `EmailResource` and `send_email_op` capabilities and their gap.

Taken from research against primary sources, cited above but not independently
re-verified here: the Kimball, ISO 8000-8, Ed-Fi, dbt-project-evaluator, and
static-analysis citations, and a reported 657 lifetime views on the
`Ops - Student Info Audit` Tableau view since 2021-12-21.

Not verifiable: PowerSchool's own documentation on how customizations survive
version upgrades sits behind a login. The decision to skip a plugin does not
rest on that claim, because Miami runs Focus regardless.
