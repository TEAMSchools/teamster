# Build survey submissions from response grain

Refs #5277. Refs #5276. Refs #5270. Refs #3918.

`int_surveys__survey_submissions` produces about 129,000 submissions by
collapsing `int_surveys__survey_responses`, a 4.1M-row question-grain view. The
submissions already exist at response grain 2 models upstream. This spec makes
`int_surveys__survey_submissions` read those response-grain sources directly and
makes `int_surveys__survey_responses` read submissions for its per-submission
columns, reversing today's dependency. It also closes #5276 by fixing the sheet
row that causes the 68-submission ambiguity and adding the test that would have
caught it.

## Decision

- `int_surveys__survey_submissions` reads response-grain sources and owns every
  per-submission derived column: survey title, reporting term, roster identity,
  and `round_rn`. Table, eager (no cron).
- `int_surveys__survey_responses` drops its roster and reporting-terms joins and
  inner-joins `int_surveys__survey_submissions` on (`survey_id`,
  `survey_response_id`) for those columns. Output columns are unchanged, so its
  7 consumers need no edits.
- `dbt_utils.mutually_exclusive_ranges` on `stg_google_sheets__reporting__terms`
  for `SURVEY` rows, partitioned by `name`, error severity.
- The `KTAF Support Survey` row with `academic_year` 2026 and window 2026-01-04
  to 2026-01-15 in the reporting-terms Google Sheet is corrected by the sheet
  owner. CI is red on the new test until that lands.
- One PR. No change to the 3 marts, to `int_google_forms__form_responses`, or to
  the archive arm.

## What was verified (2026-09-14, prod)

A response-grain candidate for both live arms was compared against a fresh
collapse of the current `int_surveys__survey_responses` view, so both sides read
the same snapshot. Keys and all 8 output columns were compared.

| Arm          | Current keys | Candidate keys | Column diffs                |
| ------------ | -----------: | -------------: | --------------------------- |
| Alchemer     |       46,000 |         46,000 | 0                           |
| Google Forms |       80,821 |         80,817 | 68, on `academic_year` only |

Two residuals, both explained:

- **68 `academic_year` diffs** are the #5276 set. All 68 are Google Forms
  submissions of `KTAF Support Survey` submitted 2026-01-12 to 2026-01-15. The
  reporting-terms sheet has 2 `SURVEY` rows with that name whose windows
  overlap: `2025:KTAF 2026-01-01..2026-02-28` and
  `2026:KTAF 2026-01-04..2026-01-15`. At question grain the fan-out was hidden
  by the `survey_question_id` tiebreak; at response grain it is 68 duplicate
  keys. The cause is the sheet, not the Alchemer `coalesce` that #5276 also
  suspected: the Alchemer arm had 0 diffs.
- **4 keys only in the current logic are phantom submissions.**
  `int_google_forms__form_responses` left-joins responses from the items side on
  `form_id` alone, so 4 forms with items and zero responses emit rows with a
  null `response_id`. Those reach `fct_survey_submissions` today under a
  placeholder hash. The response-grain build drops them. Accepted.

Also settled from #5277's unverified list:

- **Alchemer source path.** `stg_alchemer__survey` (title, default link),
  `stg_alchemer__survey_response` (112,318 rows, 1 per response), and
  `stg_alchemer__survey_campaign` joined on `survey_id` and
  `date_started between link_open_date and link_close_date`. This is the join
  the disabled `int_alchemer__survey_results` uses. All 3 are frozen tables in
  `kipptaf_alchemer` (last modified 2025-08-28). Title, campaign fields,
  `date_submitted`, `response_session_id` and `survey_link_default` are constant
  within every response in `base_alchemer__survey_results`, so the
  response-grain path loses nothing.
- **`int_surveys__response_identifiers`** (frozen 2024-08-27) covers 45,977 of
  the 46,000 Alchemer submissions. Today's model left-joins it; so does the new
  one. No change.
- **`survey_title` for Google Forms** is `stg_google_forms__form.info_title`, 1
  row per form, 28 forms.
- **Cadence.** Google Forms responses ingest on a 15-minute sensor and the
  `survey_dashboard` Tableau exposure refreshes hourly through
  `rpt_tableau__survey_responses`, which reads `int_surveys__survey_responses`.
  A nightly-cron table upstream of that view would hold new responses until
  03:00. The repo rule says an intraday consumer vetoes the nightly cron, so the
  cron comes off. The rebuild is affordable now: about 193,000 input rows
  instead of 4.1M.

## `int_surveys__survey_submissions`

### Shape

```text
gdir_alias_map            (moved here from int_surveys__survey_responses)
live_gforms               1 row per stg_google_forms__responses row
live_alchemer             1 row per stg_alchemer__survey_response row that
                          matches a SURVEY reporting term (inner join, as today)
archive_source /
archive_submissions       unchanged
all_submissions           union all of the 3 arms
final select              adds survey_submission_key, unchanged hash inputs
```

No ranked column, no `dbt_utils.deduplicate` on the live arms. Nothing
collapses, so the existing uniqueness test on `survey_submission_key` becomes
the guard against any future terms fan-out.

### Google Forms arm

```sql
from {{ ref("stg_google_forms__responses") }} as r
inner join {{ ref("stg_google_forms__form") }} as f on r.form_id = f.form_id
left join {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on f.info_title = rt.name
    and r.last_submitted_date between rt.start_date and rt.end_date
    and rt.type = 'SURVEY'
-- roster: srh, gam, srh_alias joins moved verbatim from
-- int_surveys__survey_responses, keyed on r.respondent_email and
-- r.last_submitted_timestamp
```

Today's join uses `date(fr.last_submitted_time)` on a string column, which
BigQuery resolves as the UTC date. Verified on prod 2026-09-14: that equals
`date(last_submitted_timestamp)` on all 80,817 rows, and differs from the
existing `last_submitted_date_local` on 3,552. To preserve behavior the arm
derives `last_submitted_date` as `date(last_submitted_timestamp)` in a CTE (UTC)
and joins on that plain column. Whether the terms join should use the local date
instead is a separate question and is not changed here.
`timestamp(fr.last_submitted_time)` equals `last_submitted_timestamp` on every
row, so `date_submitted` reads that staging column directly.

`survey_response_link` is built from `form_id` and `response_id` as today.
`date_started` is `create_timestamp`.

### Alchemer arm

```sql
from {{ source("alchemer", "stg_alchemer__survey") }} as s
inner join {{ source("alchemer", "stg_alchemer__survey_response") }} as sr
    on s.id = sr.survey_id
left join {{ source("alchemer", "stg_alchemer__survey_campaign") }} as sc
    on sr.survey_id = sc.survey_id
    and sr.date_started between sc.link_open_date and sc.link_close_date
inner join {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on s.title = rt.name
    and sr.date_submitted_date between rt.start_date and rt.end_date
left join {{ source("surveys", "int_surveys__response_identifiers") }} as ri
    on sr.survey_id = ri.survey_id and sr.id = ri.response_id
-- roster joins as today, keyed on ri.respondent_mail and sr.date_submitted
```

`academic_year` is `coalesce(sc.fiscal_year - 1, rt.academic_year)` and
`term_code` is `coalesce(regexp_extract(sc.name, r'\s(.*)'), rt.code)`, both as
today. `date_submitted_date` does not exist on `stg_alchemer__survey_response`
and is derived in a CTE (no calculations in join predicates).

The Alchemer models sit under a project-level `+enabled: false`, so they are
read through `source()`, the way `base_alchemer__survey_results` is today.
`models/alchemer/sources-bigquery.yml` already declares `stg_alchemer__survey`;
this change adds `stg_alchemer__survey_response` and
`stg_alchemer__survey_campaign` to it, matching the existing entries' shape
(Dagster asset key under `kipptaf / alchemer / <table>`).

### Columns

Existing, unchanged: `survey_id`, `survey_response_id`, `survey_title`,
`respondent_email`, `respondent_employee_number`, `date_submitted`,
`academic_year`, `term_code`, `survey_submission_key`.

Added, all null on the archive arm: `respondent_preferred_name`,
`respondent_samaccountname`, `respondent_userprincipalname`,
`respondent_identifier`, `term_name`, `date_started`, `survey_response_link`,
`round_rn`.

`round_rn` is
`dense_rank() over (partition by respondent_email, academic_year, term_code, survey_id order by date_submitted desc)`
on the Google Forms arm and the literal 1 on the Alchemer arm, as today. It is
per submission, so it moves here unchanged in meaning.

### Config

`materialized: table`. Remove `automation_condition.cron_schedule` so the
default eager table condition applies. Update the properties description: the
model no longer collapses anything, and it is now the single home of respondent
and term resolution for surveys. Column descriptions for the 8 new columns move
from `int_surveys__survey_responses.yml` wording.

## `int_surveys__survey_responses`

Both arms of `enriched` drop `rt`, `srh`, `gam`, `srh_alias` and the
`gdir_alias_map` CTE, and add:

```sql
inner join {{ ref("int_surveys__survey_submissions") }} as ss
    on <arm key> = ss.survey_id and <arm response id> = ss.survey_response_id
```

selecting `ss.survey_title`, `ss.respondent_email`, `ss.academic_year`,
`ss.term_code`, `ss.term_name`, `ss.respondent_employee_number`,
`ss.respondent_preferred_name`, `ss.respondent_samaccountname`,
`ss.respondent_userprincipalname`, `ss.date_started`, `ss.date_submitted`,
`ss.survey_response_link`, `ss.round_rn`, and `ss.respondent_identifier` in the
final select in place of the `coalesce` there. The Alchemer arm's inner join to
reporting terms is now enforced through the inner join to `ss`, whose Alchemer
arm keeps that inner join. Output column list and names are unchanged.

The join key types differ per arm: Google Forms keys are strings; the Alchemer
arm casts `sr.survey_id` and `sr.response_id` to string before joining, as the
current model already does for its output.

The `question_departments` join and `rated_department_*` columns stay.

## Reporting-terms test

In `stg_google_sheets__reporting__terms.yml`, model-level `data_tests`:

```yaml
- dbt_utils.mutually_exclusive_ranges:
    arguments:
      lower_bound_column: start_date
      upper_bound_column: end_date
      partition_by: name
      gaps: allowed
    config:
      severity: error
      where: type = 'SURVEY'
```

Against prod on 2026-09-14: 81 `SURVEY` rows, 23 names, exactly 1 overlapping
pair (the `KTAF Support Survey` pair). The test fails today and passes after the
sheet fix. It sits on this staging table for the same reason the existing
`dim_terms` grain guard does: the table rebuilds on every sheet edit, so the
test fires exactly when the sheet can break.

Known limit: `gaps: allowed` compiles to `end_date <= next start_date`, so 2
windows that touch on one day pass while a `between` join still double-matches
that day. Narrower than today; not addressed.

## Sheet fix

Owned by the sheet owner, not this PR's code. The 2026 row is the anomaly: a
January 2026 survey belongs to academic year 2025 under the repo's July-start
convention, and the 2025 row already covers the window. Whether the 2026 row is
deleted or re-dated is the owner's call; either makes the test pass. The #5276
reproduce query must return 0 afterward.

## Verification

Run with the sheet fix in place, main versus branch, per #5270's method:
`bit_xor(farm_fingerprint(key))` over the distinct key set, alongside row and
distinct counts.

| Model                             | Keys                                                 | Expected                                                   |
| --------------------------------- | ---------------------------------------------------- | ---------------------------------------------------------- |
| `int_surveys__survey_submissions` | `survey_submission_key`                              | 4 fewer, phantom rows                                      |
| `fct_survey_submissions`          | `survey_submission_key`, `survey_administration_key` | 4 fewer submissions                                        |
| `dim_survey_administrations`      | `survey_administration_key`                          | identical                                                  |
| `fct_survey_responses`            | response key, `survey_submission_key`                | identical or fewer only by the phantom rows' question rows |

Plus:

- The candidate's `date_submitted` and reporting-term join date equal today's
  `timestamp(fr.last_submitted_time)` and `date(fr.last_submitted_time)` on
  every row, if the staging columns are used.
- `uv run dbt build --select int_surveys__survey_submissions+` in the worktree,
  dev target, deferred to prod.
- The #5276 reproduce query returns 0 for `varying_academic_year`.
- The 68 previously ambiguous submissions land on `academic_year` 2025 and their
  `survey_administration_key` is explainable row by row.

## Out of scope

- `int_google_forms__form_responses`' item-by-response grid. It is the shape
  `int_surveys__survey_responses` and the survey dashboard need.
- The 23 Alchemer submissions missing from the frozen
  `int_surveys__response_identifiers`.
- Any change to the 3 marts beyond what the fingerprints confirm.
- A model-level tiebreak for overlapping terms. The test and the sheet fix
  replace it.
