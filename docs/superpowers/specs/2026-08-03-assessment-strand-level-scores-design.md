# Strand-level assessment scores: DIBELS subtests and i-Ready domains

Issue: [#4708](https://github.com/TEAMSchools/teamster/issues/4708)

Depends on: [#4706](https://github.com/TEAMSchools/teamster/issues/4706) /
[#4709](https://github.com/TEAMSchools/teamster/pull/4709)
(`int_iready__domain_unpivot` placement/`scale_score`) — **merged**. One column
is still outstanding; see _i-Ready_ below.

**Revised 2026-08-28** after an adversarial review against current production.
The review is recorded on
[PR #4710](https://github.com/TEAMSchools/teamster/pull/4710#issuecomment-5456572015).
Two design decisions changed as a result — `response_type` is now unified across
every source, and Cube's `count_scores` no longer counts not-taken rows.
Corrections to the original draft are marked **[revised]**.

## Problem

`fct_assessment_scores_enrollment_scoped` carries only the summary score for the
two vendor benchmark diagnostics:

- **DIBELS** — the `dibels_scores` CTE filters `measure_standard = 'Composite'`,
  so subtest results never reach the mart or Cube.
- **i-Ready** — the `iready_scores_raw` CTE reads only the subject-level
  diagnostic row from `int_iready__diagnostic_results`, so the per-domain
  results are absent.

Analysts want strand and domain level cuts for both sources. Internal Illuminate
assessments already model this shape through the `response_type` column family,
so the vendor breakdowns reuse that pattern rather than introduce a parallel
one.

**[revised]** The original draft named the DIBELS subtests as "Nonsense Word
Fluency, Phoneme Segmentation Fluency, Oral Reading Fluency, Letter Naming
Fluency". Those are `measure_name` values, and two of them do not exist in any
vocabulary. The actual `measure_standard` values, verified against prod, are in
the _DIBELS_ section below.

## Rejected approach: widen `module_code`

The obvious change — drop the `Composite` filter and let `measure_standard` flow
into `module_code` — produces FK orphans. `dim_assessments` and
`dim_assessment_administrations` are **siblings**, not descendants, of this
fact: each independently re-derives its DIBELS rows from
`int_amplify__all_assessments` with the same
`assessment_type = 'Benchmark' and measure_standard = 'Composite'` filter.

**[revised]** The original draft said subtest rows would hash "an
`assessment_administration_key` and `assessment_key` that exist in neither dim".
The fact has no `assessment_key` column and never has. It hashes only
`assessment_administration_key`; `assessment_key` lives on
`dim_assessment_administrations`, and Cube reaches it by traversal
(`student_assessment_scores` → `student_assessment_administrations` →
`student_assessments`).

The correct statement of the hazard: every subtest row would hash an
`assessment_administration_key` present in neither dim. That is caught by the
existing `relationships` test on that column, at project-default `warn` severity
— a CI warning rather than silence. Downstream, Cube's `count_scores`,
`_sum_proficient`, and the `pct_proficient_*` family filter
`{student_assessments.assessment_key} IS NOT NULL`, so orphaned rows would drop
out of those measures while still inflating the ungated `avg_scale_score`.

## Design

### Discriminator columns

**[revised]** Summary rows are promoted to `response_type = 'overall'` across
every source, and Illuminate's expected-but-not-taken rows get their own token.
`response_type` becomes non-nullable throughout, which makes an
`accepted_values` test enforceable for the first time.

| branch                  | `response_type` | `_code`            | `_description` | `_root_description` |
| ----------------------- | --------------- | ------------------ | -------------- | ------------------- |
| Illuminate, no response | `not_taken`     | NULL               | NULL           | NULL                |
| Illuminate summary      | `overall`       | NULL               | NULL           | NULL                |
| Illuminate group        | `group`         | NULL               | label          | NULL                |
| Illuminate standard     | `standard`      | coded              | full text      | populated           |
| State NJ / FL           | `overall`       | NULL               | NULL           | NULL                |
| STAR                    | `overall`       | NULL               | NULL           | NULL                |
| i-Ready subject         | `overall`       | NULL               | NULL           | NULL                |
| i-Ready domain          | `group`         | `domain_name`      | rendered label | NULL                |
| DIBELS Composite        | `overall`       | NULL               | NULL           | NULL                |
| DIBELS subtest          | `group`         | `measure_standard` | `measure_name` | NULL                |

Three properties this buys:

1. **`overall` means one thing across every source.** Today there is no
   cross-source filter that yields one row per sitting: an Illuminate sitting
   contributes `1 + n_standards + n_groups` rows while an NJSLA sitting
   contributes 1. `response_type = 'overall'` becomes that filter.
1. **The not-taken population becomes addressable.** Verified against prod,
   `response_type IS NULL` currently holds 1,073,422 Illuminate
   expected-but-not-taken rows alongside 305,644 vendor and 62,378 state summary
   rows. Neither population can be isolated today.
1. **`response_type_code` becomes a genuine key.** With the code populated on
   breakdown rows, `response_type_code` functionally determines `response_type`
   and `response_type_description` — which is what `proficiency_rollup`'s
   comment already claims and has never been true.

**Why the original draft kept summary rows at NULL, and why that was wrong.**
The draft argued that keeping NULL made the change "purely additive" because
`assessment-cube-reference.md` documents `response_type notSet` as the filter
for a vendor summary row. That filter is already non-selective: 74.5% of what it
returns is Illuminate not-taken rows. The idiom being protected does not do what
the doc says it does.

**Scope boundary.** This changes `response_type` only in the fact's UNION
branches. `int_assessments__response_rollup` is read by roughly fifteen
downstream models that filter the lowercase vocabulary; changing the
intermediate would break all of them. Separately, the repo already runs three
unrelated `response_type` vocabularies — lowercase here, Title-case in the CARAT
lineage, plus one-offs. Unification means this fact, not the repo.

### DIBELS

Rewrite the `dibels_scores` CTE in
`fct_assessment_scores_enrollment_scoped.sql`. `module_code` stays the literal
`'Composite'` so every DIBELS row — summary and subtest alike — resolves the
same `assessment_administration_key`. The two dims are Composite-grain siblings
of this fact and carry no subtest rows.

```sql
dibels_scores as (
    select
        student_number,
        academic_year,
        illuminate_subject,
        `period` as administration_period,
        client_date as test_date,
        _dbt_source_project,

        measure_standard_level as proficiency_level,

        'dibels' as score_source,
        'Composite' as module_code,

        cast(measure_standard_score as numeric) as scale_score,
        cast(measure_percentile as numeric) as national_percentile,

        measure_standard_level_int >= 3 as is_mastery,

        if(measure_standard = 'Composite', 'overall', 'group') as response_type,

        case
            when measure_standard != 'Composite' then measure_standard
        end as response_type_code,

        case
            when measure_standard != 'Composite' then measure_name
        end as response_type_description,
    from {{ ref("int_amplify__all_assessments") }}
    where assessment_type = 'Benchmark' and client_date is not null
),
```

Only `and measure_standard = 'Composite'` leaves the `where` clause. The
`assessment_type = 'Benchmark'` filter stays, so progress-monitoring rows remain
out of scope.

**[revised] The vocabulary, verified against prod.** `measure_name` is coarser
than `measure_standard` — the `case` in
`int_amplify__mclass__benchmark_student_summary_unpivot.sql` maps five
`measure_name_code` values to five names, while there are eight subtests. So
`measure_name` cannot carry the surrogate-key discriminator; `measure_standard`
does, via `response_type_code`. See _Surrogate key_ below.

| `measure_standard`           | rows   |
| ---------------------------- | ------ |
| Composite                    | 58,124 |
| Reading Fluency (ORF)        | 50,824 |
| Reading Accuracy (ORF-Accu)  | 43,644 |
| Reading Comprehension (Maze) | 43,101 |
| Decoding (NWF-WRC)           | 29,117 |
| Letter Sounds (NWF-CLS)      | 29,117 |
| Word Reading (WRF)           | 29,117 |
| Letter Names (LNF)           | 15,112 |
| Phonemic Awareness (PSF)     | 15,112 |

Subtests total 255,144 — a 5.4x multiplier on the DIBELS rows reaching the fact
today.

**[revised] `is_mastery` needs a guard.** The original draft asserted
`measure_standard_level_int` is "populated on every `measure_standard` row", so
the `>= 3` threshold applies unchanged. Verified against prod, that is false:
Composite has 0 nulls, subtests have **5,565** — 1,321 each on NWF-WRC, NWF-CLS
and WRF, and 801 each on LNF and PSF. `NULL >= 3` yields NULL, so those rows
land in the denominator of `pct_proficient` and never in the numerator. The
upstream `case` that derives the column has no `else` branch. This is accepted
rather than fixed here (matching today's Composite behavior, which has the same
shape and no null rows) but it must be documented on the column, and the row
count asserted so a regression is visible.

**Which subtests reach the fact is sheet-driven.**
`int_amplify__all_assessments.sql` INNER JOINs
`int_google_sheets__dibels_expected_assessments` on
`measure_standard = expected_measure_standard`, keyed on (academic year, region,
grade, season). The set of `response_type_code` values reaching a public Cube
dimension therefore varies by those four axes and changes when someone edits a
spreadsheet. That sheet model has no uniqueness test and no declared columns.
Out of scope to fix; in scope to document.

### i-Ready

#### What #4709 landed

`int_iready__domain_unpivot` exposes `domain_name`, `placement`,
`relative_placement`, `scale_score`, `test_round`, and `_dbt_source_project`,
and applies `where relative_placement is not null` itself. Two carry-overs:

- **`illuminate_subject` was NOT included**, and is still absent as of
  2026-08-28. It is required: the vendor branch joins the resolver on
  `va.illuminate_subject = sr.subject_area`, so domain rows without it match
  nothing and the INNER JOIN drops all of them. Add the pass-through as the
  first commit of this work — an additive edit to the CTE and final `SELECT`
  plus a `properties.yml` entry, matching how `test_round` and
  `_dbt_source_project` were added. Do NOT re-derive the mapping in the fact:
  `int_iready__diagnostic_results` already derives it.
- **The fact does NOT repeat the `relative_placement is not null` predicate.**
  The model enforces it upstream as its documented inclusion rule; repeating it
  would imply the guarantee lives in the fact.

#### [revised] Exclude the comprehension parent

The original draft justified `'group'` on the grounds that i-Ready has "no
parent-domain rollup". Verified against prod, that is false:

| `domain_name`                              | years     | rows    |
| ------------------------------------------ | --------- | ------- |
| `comprehension_literature`                 | 2022-2026 | 119,756 |
| `comprehension_informational_text`         | 2022-2026 | 119,756 |
| `comprehension_overall`                    | 2022-2026 | 119,756 |
| `reading_comprehension_literature`         | 2020-2021 | 17,338  |
| `reading_comprehension_informational_text` | 2020-2021 | 17,338  |

`comprehension_overall` is the rollup of its two siblings. Cube's
`_sum_proficient` and `count_scores` are a plain `SUM` and `COUNT`, so shipping
all three flat makes every `response_type = 'group'` cut silently
comprehension-weighted and makes summing across domains double-count.

**`comprehension_overall` is excluded.** Nothing is lost: both children are
present, and the subject-level i-Ready row already carries the overall
comprehension signal as an `'overall'` row. The 2020-21
`reading_comprehension_*` pair has no parent and is unaffected —
`reading_comprehension_overall` appears in the `UNPIVOT` list but produces zero
rows, because the upstream `relative_placement is not null` rule drops it. That
leaves **13 live domains**, not 14.

#### The domain CTE

```sql
-- Domain-level rows. module_code stays the subject, for the same
-- FK-resolution reason as DIBELS above.
--
-- 'Not Assessed' is i-Ready's explicit not-administered marker and is
-- excluded. comprehension_overall is excluded as the rollup parent of
-- comprehension_literature and comprehension_informational_text -- Cube's
-- proficiency measures are additive, so retaining it would triple-count the
-- comprehension construct.
--
-- A domain with a placement but no scale score IS retained: the grade-level
-- placement is the primary domain signal.
--
-- No 'relative_placement is not null' predicate here: int_iready__domain_unpivot
-- enforces it upstream as its documented inclusion rule (#4709).
iready_domain_scores_raw as (
    select
        student_id as student_number,
        academic_year_int as academic_year,
        `subject` as module_code,
        illuminate_subject,
        test_round as administration_period,
        completion_date as test_date,
        `start_date`,
        _dbt_source_project,

        relative_placement as proficiency_level,

        'iready' as score_source,
        'group' as response_type,

        domain_name as response_type_code,

        initcap(replace(domain_name, '_', ' ')) as response_type_description,

        cast(scale_score as numeric) as scale_score,
        cast(null as numeric) as national_percentile,

        -- Same threshold stg_iready__diagnostic_results applies at subject
        -- level (overall_relative_placement_int >= 4). No per-domain ordinal
        -- column exists upstream, so the two at-or-above labels are tested
        -- directly. Guarded by an accepted_values test on relative_placement.
        relative_placement
        in ('Early On Grade Level', 'Mid or Above Grade Level') as is_mastery,
    from {{ ref("int_iready__domain_unpivot") }}
    where
        completion_date is not null
        and _dbt_source_project is not null
        and relative_placement != 'Not Assessed'
        and domain_name != 'comprehension_overall'
),
```

`national_percentile` is explicitly NULL — i-Ready publishes percentiles only at
subject level. The `placement` column from #4706 is not consumed: it is an
absolute rather than grade-relative scale and would need its own fact column.

**[revised] The label vocabulary is guarded here, not deferred.** Verified
against prod, `relative_placement` has exactly six values:

| `relative_placement`         | rows    |
| ---------------------------- | ------- |
| 1 Grade Level Below          | 455,150 |
| Mid or Above Grade Level     | 435,650 |
| 3 or More Grade Levels Below | 303,682 |
| 2 Grade Levels Below         | 210,807 |
| Early On Grade Level         | 167,569 |
| Not Assessed                 | 62,174  |

The upstream `case` in `stg_iready__diagnostic_results` has no `else`, so an
unrecognized label yields NULL there; the `IN (...)` above yields FALSE. A
reworded vendor label would therefore be scored as _not proficient_ rather than
_unknown_, silently, across ~1.5M rows feeding the headline metric. An
`accepted_values` test on `relative_placement` ships with this change rather
than as #4708 follow-up 2.

#### Dedupe partition must gain the discriminator

`iready_scores` applies `dbt_utils.deduplicate` partitioned by
`(_dbt_source_project, student_number, administration_period, module_code, test_date)`.
Because domain rows deliberately share `module_code` with the subject-level
anchor, all domains plus the anchor collapse into a single surviving row unless
the discriminator joins the partition key:

```sql
iready_scores as (
    {{
        dbt_utils.deduplicate(
            relation="iready_all_raw",
            partition_by="""
                _dbt_source_project,
                student_number,
                administration_period,
                module_code,
                response_type_code,
                test_date
            """,
            order_by="start_date desc, scale_score desc, academic_year desc",
        )
    }}
),
```

`iready_all_raw` unions `iready_scores_raw` (anchor) and
`iready_domain_scores_raw`. **[revised]** The two CTEs must be written with an
explicit, identical column list in the same order — the original draft gave them
in different orders and supplied no union SQL, which under a positional
`union all` would have swapped `score_source` with the discriminator silently.
`iready_all_raw` must also drop `rn_subject_test`, which
`int_iready__domain_unpivot` emits and the anchor lacks.

`response_type_code` is NULL for anchor rows and groups cleanly, so the
fiscal-year re-pull semantics documented in the CTE's `TODO(#4387)` comment are
preserved per domain rather than weakened.

**[revised] What the dedupe still collapses.** Verified against prod, the fixed
partition collapses 319,380 of 1,572,858 eligible domain rows (20.3%). 274,292
of the 286,397 colliding groups differ only by `academic_year_int` — the
intended re-pull collapse. But 9,286 groups carry differing `scale_score` and
4,321 differing `relative_placement` for the same student, subject, round, date
and domain, where `order by ... scale_score desc` keeps the higher value. That
is pre-existing #4387 behavior now applied per domain, and is recorded here so
it is not mistaken for a defect introduced by this change.

`star_scores` and its dedupe are unchanged, but its `vendor_all` branch gains
the three discriminator literals — see below.

### The union and the final SELECTs

**[revised]** The original draft rewrote the source CTEs and the surrogate key
but never mentioned `vendor_all` or the final `SELECT` blocks, which discard the
columns. Implemented as drafted, the change would compile, pass its contract,
pass `unique`, and emit every breakdown row with `response_type IS NULL` — the
exact quiet failure the _Rejected approach_ section argues against.

Required, in one file:

| Site                          | Change                                                       |
| ----------------------------- | ------------------------------------------------------------ |
| `dibels_scores`               | rewrite as above                                             |
| `iready_scores_raw`           | add `'overall'` plus two NULL literals, in a pinned position |
| `iready_domain_scores_raw`    | new CTE                                                      |
| `iready_all_raw`              | new CTE, explicit matching column lists                      |
| `iready_scores`               | dedupe re-target and partition change                        |
| `vendor_all` i-Ready branch   | add three columns                                            |
| `vendor_all` STAR branch      | add `'overall'` plus two `cast(null as string)`              |
| `vendor_all` DIBELS branch    | add three columns                                            |
| vendor final `SELECT`         | source `va.response_type`/`_code`/`_description`             |
| state final `SELECT`          | `cast(null as string)` → `'overall'`                         |
| internal branch               | `coalesce`-free split: `not_taken` where no response joined  |
| vendor `assessment_score_key` | append `response_type_code` as the 8th input                 |

### Surrogate key

The shared vendor-branch `assessment_score_key` hashes
`(score_source, _dbt_source_project, student_number, academic_year, administration_period, module_code, test_date)`
— exactly seven inputs. Since `module_code` is now a constant for DIBELS and
shared across domains for i-Ready, that list no longer discriminates.

**[revised] Append `response_type_code`, not `response_type_description`.** The
draft appended the description. That works for i-Ready (the slug is unique per
subject) but collides for DIBELS once the description is `measure_name`, because
NWF-WRC and NWF-CLS share the name "Nonsense Word Fluency". `response_type_code`
carries `measure_standard`, which is unique per subtest. Keying on the code also
means future label rewording never churns the PK.

Position matters — the macro hashes an ordered concatenation joined with `'-'`,
and `'Reading Accuracy (ORF-Accu)'` contains that delimiter, which is harmless
only in final position. `generate_surrogate_key` coerces NULL to
`'_dbt_utils_surrogate_key_null_'`, so summary rows hash deterministically and
no real value can collide with the sentinel.

Verified against prod: the eight-input key yields 313,268 distinct values over
313,268 DIBELS rows. For i-Ready, uniqueness holds by construction — the dedupe
partition is a superset of the key inputs minus `academic_year` and the constant
`score_source`, so one row survives per partition and one key per survivor. The
dedupe is load-bearing for PK uniqueness, not only for row counts.

**[revised] DIBELS uniqueness at the widened grain.** The current CTE comment
asserts DIBELS composites are "unique at this grain upstream (verified); no
dedupe needed" — a verification performed on Composite rows only. The count
above re-establishes it at the subtest grain. No DIBELS dedupe is added.

#### Consumer blast radius

- **No dbt model reads this fact.** **[revised]** The original draft said the
  only `ref()` is `models/exposures/cube.yml`. Since then, `d19af9567` added
  `tests/fct_assessment_scores_enrollment_scoped__term_covers_assessment_date.sql`,
  which also refs it. The corrected claim: the only model-graph consumers are
  the Cube exposure and one singular test.
- **Cube uses the column only as a `primary_key` dimension** — never a join key,
  never in a pre-aggregation dimension list. It is, however, exposed on the
  public view and the MCP knowledge doc instructs agents to select it, so a
  saved query pinned on key values would break.
- **No mart declares an FK to this fact.**

The key **value** changes for every vendor row, including STAR rows that gain no
data, and separately for every internal Illuminate `not_taken` row (~1,072,971
rows) — Task 5 changed the 4th hash input from `rr.response_type` (NULL) to
`coalesce(rr.response_type, 'not_taken')`, so that population's key changes too
even though it carries no new vendor data. This is expected, is one-way, and is
covered by the rollback runbook rather than reversed by it.

The model is `materialized: table`, so the rebuild is a full CTAS with no
incremental-merge duplicate risk.

## Cube

**[revised]** The original draft claimed "no new Cube members are required".
Literally true and materially misleading — the Cube layer needs four edits.

- **Add `student_assessments.assessment_type` to `proficiency_rollup`.** Without
  it the rollup cannot serve a single query this feature exists for:
  `assessment_type` is the documented way to select i-Ready or DIBELS, and a
  rollup only serves a query whose filtered members it all carries. As drafted,
  ~1.8M new rows would be materialized into a rollup that always falls back to
  the fact. `assessment_type` is near-functionally-determined by `module_code`,
  already in the rollup, so it costs close to zero added rows.
- **Filter `not_taken` out of the proficiency measures.** `count_scores`,
  `_sum_proficient`, and the formative and CRQ pairs gain
  `{CUBE}.response_type != 'not_taken'`. Today `count_scores` is documented as a
  "Scored-response count" but includes 1,073,422 rows with no response, and
  `_sum_proficient`'s `IF(is_mastery, 1, 0)` turns their NULL into 0 — so an
  untaken test currently counts as a non-proficient result. Expected effect on
  the global unfiltered `pct_proficient`: roughly 45.4% → 49.0%, larger on
  Illuminate-only cuts. This is a deliberate metric change and the single most
  visible consequence of this work.
- **Rewrite the `proficiency_rollup` functional-determination comment.** It
  claims `response_type` and `response_type_description` are determined by
  `response_type_code` with "zero added rows". That is false today — Illuminate
  `'group'` rows carry a NULL code with varying descriptions. With the code
  populated on breakdown rows it becomes true, and the comment should say so
  rather than be deleted.
- **Amend `avg_scale_score`'s Grain clause.** It documents the safe boundary as
  "a single assessment source/subject/grade". After this change, scoping to
  DIBELS and one subject pools a Composite score with an ORF words-per-minute
  rate. The clause gains "and response type".

**Pre-aggregation migration.** `proficiency_rollup` is ~12 yearly partitions
with no `incremental: true` and no `update_window`, each served from its last
successful build until its replacement lands. A change that flips
`response_type` on every historical row means partitions can carry the old and
new vocabulary simultaneously mid-sweep, so a multi-year query filtering
`response_type = 'overall'` returns partial history with no error. **Bump the
pre-aggregation name** to force one clean rebuild.

Per `src/cube/CLAUDE.md`, the pre-aggregation build must be validated on a
branch staging deployment before merge.

## Documentation and sequencing

Documentation is a required deliverable, not a follow-up: this change redefines
existing metrics rather than only adding a capability.

**[revised]** The original draft's table named two locations in
`assessment-cube-reference.md`. There are eight, plus four other files.

| File                                 | Change                                                                                                                                                                                                         |
| ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `assessment-cube-reference.md`       | Global vocabulary block; the `notSet` instruction; the `_root_description` rationale; the i-Ready, DIBELS, STAR, NJ and FL per-source lines; the hard-coded 302,907 vendor row count; the i-Ready dedup recipe |
| `assessment-cube-orchestrator.md`    | The "never rely on the silent default blend" protocol                                                                                                                                                          |
| `project_knowledge/README.md`        | The same protocol restated                                                                                                                                                                                     |
| `student_assessment_scores.yml`      | Four `response_type*` dimension descriptions; `avg_scale_score` Grain clause; pre-agg comment                                                                                                                  |
| `student_assessment_scores_view.yml` | View description clause asserting the breakdown is Illuminate only                                                                                                                                             |
| `fct_..._enrollment_scoped.yml`      | Model grain and DIBELS scope; four `response_type*` column descriptions; `is_mastery` null-on-subtests note                                                                                                    |

The i-Ready dedup recipe deserves particular attention: it instructs analysts to
reduce to "one row per student per window", which at the new grain collapses
fourteen rows into one and destroys the feature silently.

**Sequencing is a gating step, not a checklist row.**
`src/cube/mcp/project_knowledge/README.md` states the repo is the source of
truth and the claude.ai Project is the **deployment target** — changed files are
re-uploaded manually. The fact rebuilds on a `0 0,10,13,15,17 * * *` cron, so
the data change lands within hours of merge, ungated. If the re-upload lags the
merge, every agent following the still-published `notSet` protocol returns zero
rows for i-Ready, DIBELS, STAR, and both states, silently.

**The re-upload must precede the model merge and must have a named owner in the
PR body.**

Consumers that cannot be enumerated from the repo — Superset saved charts,
Tableau workbooks on the Cube SQL API, direct Cube API callers, ad-hoc BigQuery
— sit inside Cube, so no dbt exposure covers them. #4708 follow-up 3 (the
saved-consumer audit) is therefore a **prerequisite**, not a follow-up, and an
announcement to that audience is the only available mitigation.

## Rollback

Stakeholders must be able to back this out. The model is `materialized: table`,
so a revert plus a rebuild genuinely restores prior output — but the key churn
and the doc re-upload are not covered by that alone, and a rollback nobody can
verify is not a rollback.

**Capture the baseline before merging** and commit it alongside this spec:

- row counts by `score_source` × `response_type`
- `pct_proficient` and `count_scores` by `assessment_type`
- a sample of `assessment_score_key` values for vendor rows
- `proficiency_rollup` partition count and build bytes

**Runbook:**

1. `git revert` the implementation range.
1. `uv run dbt build --select fct_assessment_scores_enrollment_scoped+` — the
   full CTAS restores prior rows.
1. Re-upload the prior versions of the knowledge-doc files listed above.
1. Bump the pre-aggregation name again to force a clean rebuild.
1. Assert the restored table against the captured baseline.

**One-way:** `assessment_score_key` values for vendor rows do not return to
their pre-change values on rollback, because the revert restores the seven-input
key while any external system that persisted the eight-input values holds
neither. This is documented rather than solved; #4708 follow-up 4 asks whether
any external system persisted them, and that question should be answered before
merge, not after.

## Validation

**[revised]** Three of the original draft's five bullets were not runnable or
could not fail. Corrected:

- **`accepted_values` on `response_type`** —
  `[not_taken, overall, group, standard]`. This is the test that makes the
  unified vocabulary a contract rather than a convention, and it is only
  tractable because the column becomes non-nullable.
- **`accepted_values` on `relative_placement`** — the six values above, so a
  reworded vendor label fails loudly instead of deflating `pct_proficient`.
- **`unique` on `assessment_score_key` must pass.** This is the proof
  `response_type_code` is a sufficient discriminator. **[revised]** The draft
  also named a `not_null` test on the PK; `d51920ff8` removed it on 2026-08-07,
  and repo convention forbids re-adding it — `generate_surrogate_key` never
  returns NULL.
- **The existing `relationships` test on `assessment_administration_key` must
  stay green.** **[revised]** This replaces the draft's FK null-rate comparison,
  which named a column the fact does not have and compared a rate that reads 0%
  in both the success and failure cases. The test is `warn` severity, so pull it
  with `get_job_run_error(warning_only=true)`.
- **Per-source before/after counts.** **[revised]** The draft asserted that the
  count of `response_type is null` rows must be unchanged; under unification
  that count goes to zero. The replacement: `count(response_type = 'overall')`
  after must equal `count(response_type is null)` before, **per
  `score_source`**, and `count(response_type = 'not_taken')` must equal
  1,073,422.
- **Adding `illuminate_subject` and the unit test.**
  `unit_iready_domain_unpivot_placement_scale_score` has twelve `expect` rows.
  The `given` block is `format: sql` and must gain the column or the model fails
  to resolve — loud. **[revised]** The draft said omitting it from the expect
  rows fails on mismatched column counts. It does not: dbt derives the compared
  column set from `expected_rows[0].keys()`, so omitting it from all twelve
  compiles, runs and **passes** with the column silently uncompared. The real
  risks are partial edits (loud) and inconsistent key order (silent — the
  neighbouring columns are all STRING, so BigQuery unions positionally into the
  wrong columns).
- **Pre-aggregation build on a branch staging deployment**, confirming partition
  count and that queries hit the rollup rather than the fact.

**Row-count reconciliation.** Verified against the built table on 2026-08-28:
`int_iready__domain_unpivot` holds 1,635,032 rows; after `completion_date`,
`_dbt_source_project` and `Not Assessed` filters, 1,572,858; after excluding
`comprehension_overall`, **1,453,102**. These are upper bounds — the resolver's
INNER JOIN drops further rows, asymmetrically (see below).

**[revised] The enrollment-scoping gate is asymmetric.**
`int_assessments__resolved_section_enrollments` still filters DIBELS to
`measure_standard = 'Composite'` and i-Ready to
`overall_scale_score is not null`. So a DIBELS subtest row for a student with no
Composite row, and an i-Ready diagnostic with domain placements but no
subject-level scale score, both have no resolver row and are dropped. Whether to
widen the resolver is deferred; the asymmetry is recorded so the row
reconciliation is not read as a defect.

## Out of scope

- DIBELS progress-monitoring rows.
- State-assessment subclaim or strand breakdowns.
- Changing `response_type` in `int_assessments__response_rollup` or the CARAT
  lineage — this change is scoped to the fact's UNION branches.
- Domain-level `national_percentile`.
- A uniqueness test on `int_iready__domain_unpivot` — still absent after #4709.
  Pre-existing gap.
- Consuming i-Ready's absolute `placement` column.
- Widening `int_assessments__resolved_section_enrollments` to cover subtest and
  scoreless-diagnostic rows.
- Fixing the null `measure_standard_level_int` on 5,565 DIBELS subtest rows.

## Known dependency: i-Ready ingestion

Verified in Dagster on 2026-08-28: `kippmiami/iready/diagnostic_results` and
`kippnewark/iready/diagnostic_results` both last materialized **2026-07-18**.
[PR #4951](https://github.com/TEAMSchools/teamster/pull/4951) documents the
cause — Curriculum Associates renamed the FY27 SFTP exports, and the FY27
partition holds FY26 rows.

The i-Ready half of this change therefore ships domain rows for a source that is
not currently ingesting current-year data. The DIBELS half has no such
dependency. Both ship together so there is a single surrogate-key migration
event, but the i-Ready ingestion stall should be resolved before or alongside
this work.

Follow-up items for a data engineer are enumerated on
[#4708](https://github.com/TEAMSchools/teamster/issues/4708).
