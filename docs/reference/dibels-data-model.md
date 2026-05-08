# DIBELS Dashboard Data Model

Reference document for `rpt_tableau__dibels_dashboard` — the Tableau extract
that powers the DIBELS benchmark and progress monitoring dashboard.

## What is DIBELS?

DIBELS 8 (Dynamic Indicators of Basic Early Literacy Skills) is a literacy
assessment created by the University of Oregon and administered through Amplify
mCLASS. KIPP TAF uses it to assess literacy knowledge and growth for students in
grades K–8.

Reference:
[DIBELS at the University of Oregon](https://dibels.uoregon.edu/about-dibels)

## Assessment types

### Benchmark (BM)

Three administrations per year: **BOY** (Beginning of Year), **MOY** (Middle of
Year), and **EOY** (End of Year). These are point-in-time snapshots that track
literacy growth across administrations within a year and across years.

### Progress Monitoring (PM)

Shorter, more frequent assessments administered during two windows:

- **BOY→MOY** — between the BOY and MOY benchmark administrations
- **MOY→EOY** — between the MOY and EOY benchmark administrations

PM is primarily administered to students who scored **Below Benchmark** or
**Well Below Benchmark** on the composite score of the preceding benchmark.
Other students may take PM, but only the probe-eligible population (Below/Well
Below composite) is tracked for growth reporting.

PM was first implemented in AY 2023–2024. The testing strategy and supporting
data model have evolved each year since.

## Current data model (AY 2023–2026)

Lineage diagram for `rpt_tableau__dibels_dashboard`:

```mermaid
flowchart TD
    %% ── Sources ───────────────────────────────────────────────────────────────
    subgraph SRC ["Sources"]
        direction TB
        src_amp["Amplify\ndds__data_farming_unpivot"]
        src_gs_exp["Google Sheets\ndibels__expected_assessments"]
        src_gs_bm["Google Sheets\ndibels__bm_goals"]
        src_gs_pm["Google Sheets\ndibels__pm_goals"]
        src_gs_long["Google Sheets\ndibels__goals_long"]
        src_gs_terms["Google Sheets\nreporting__terms"]
        src_gs_xwalk["Google Sheets\nassessments__course_subject_crosswalk"]
        src_ps_districts["PowerSchool\n(kippnewark / kippcamden\n/ kippmiami / kipppaterson)"]
        src_ps_spenroll["PowerSchool\nspenrollments"]
        src_ps_terms["PowerSchool\nterms"]
        src_ps_schools["PowerSchool\nschools"]
        src_ps_cal["PowerSchool\ncalendar_day"]
        src_ps_nj_crs["PowerSchool\ns_nj_crs_x"]
        src_ps_nj_stu["PowerSchool\ns_nj_stu_x"]
    end

    %% ── Staging ───────────────────────────────────────────────────────────────
    subgraph STG ["Staging"]
        direction TB
        stg_exp["stg_google_sheets__\ndibels_expected_assessments"]
        stg_bm["stg_google_sheets__\ndibels_bm_goals"]
        stg_pm["stg_google_sheets__\ndibels_pm_goals"]
        stg_long["stg_google_sheets__\ndibels_goals_long"]
        stg_terms["stg_google_sheets__\nreporting__terms"]
        stg_ps_terms["stg_powerschool__terms"]
        stg_schools["stg_powerschool__schools"]
        stg_cal["stg_powerschool__calendar_day"]
        stg_nj_crs["stg_powerschool__s_nj_crs_x"]
    end

    %% ── Base ──────────────────────────────────────────────────────────────────
    subgraph BASE ["Base"]
        base_ce["base_powerschool__\ncourse_enrollments"]
    end

    %% ── Intermediate — Amplify / mClass ──────────────────────────────────────
    subgraph INT_AMP ["Intermediate · Amplify"]
        direction TB
        int_bm_sum["int_amplify__mclass__\nbenchmark_student_summary"]
        int_bm_unpivot["int_amplify__mclass__\nbenchmark_student_summary_unpivot"]
        int_pm_sum["int_amplify__mclass__\npm_student_summary"]
        int_all["int_amplify__all_assessments"]
        int_pm_crit["int_amplify__pm_met_criteria"]
    end

    %% ── Intermediate — Google Sheets ─────────────────────────────────────────
    subgraph INT_GS ["Intermediate · Google Sheets"]
        int_gs_exp["int_google_sheets__\ndibels_expected_assessments"]
        int_gs_pm_exp["int_google_sheets__\ndibels_pm_expectations"]
    end

    %% ── Intermediate — Students / Enrollments ────────────────────────────────
    subgraph INT_STU ["Intermediate · Students"]
        direction TB
        int_spenroll["int_powerschool__spenrollments"]
        int_nj_stu["int_powerschool__\ns_nj_stu_x_unpivot"]
        int_enroll["int_extracts__\nstudent_enrollments"]
        int_enroll_subj["int_extracts__\nstudent_enrollments_subjects"]
        int_dibels_roster["int_students__\ndibels_participation_roster"]
    end

    %% ── Intermediate — Other assessments (feed enrollment_subjects) ──────────
    subgraph INT_OTHER ["Intermediate · Other Assessments"]
        direction TB
        int_fast["int_assessments__\nfast_previous_year"]
        int_pearson["int_pearson__\nall_assessments"]
        int_fldoe["int_fldoe__\nall_assessments"]
        int_iready["int_iready__\ndiagnostic_results"]
        int_deanslist["int_deanslist__\nroster_assignments"]
    end

    %% ── Final report ─────────────────────────────────────────────────────────
    RPT(["rpt_tableau__dibels_dashboard"])

    %% ── Edges: Sources → Staging ─────────────────────────────────────────────
    src_gs_exp   --> stg_exp
    src_gs_bm    --> stg_bm
    src_gs_pm    --> stg_pm
    src_gs_long  --> stg_long
    src_gs_terms --> stg_terms
    src_ps_spenroll --> int_spenroll
    src_ps_terms --> stg_ps_terms
    src_ps_schools --> stg_schools
    src_ps_cal   --> stg_cal
    src_ps_nj_crs --> stg_nj_crs
    src_ps_nj_stu --> int_nj_stu

    %% ── Edges: Sources / Staging → Base ──────────────────────────────────────
    src_ps_districts --> base_ce
    src_gs_xwalk     --> base_ce
    stg_nj_crs       --> base_ce

    %% ── Edges: Sources → Amplify Intermediate ────────────────────────────────
    src_amp --> int_bm_sum
    src_amp --> int_bm_unpivot
    src_amp --> int_pm_sum

    %% ── Edges: Amplify Intermediate → int_amplify__all_assessments ───────────
    int_bm_sum    --> int_all
    int_bm_unpivot --> int_all
    int_pm_sum    --> int_all
    int_gs_exp    --> int_all

    %% ── Edges: Staging → Google Sheets Intermediate ──────────────────────────
    stg_exp   --> int_gs_exp
    stg_terms --> int_gs_exp

    stg_exp      --> int_gs_pm_exp
    stg_terms    --> int_gs_pm_exp
    stg_schools  --> int_gs_pm_exp
    stg_cal      --> int_gs_pm_exp
    stg_long     --> int_gs_pm_exp

    %% ── Edges: Student enrollment chain ──────────────────────────────────────
    int_spenroll --> int_enroll
    stg_ps_terms --> int_enroll

    int_enroll      --> int_enroll_subj
    base_ce         --> int_enroll_subj
    int_nj_stu      --> int_enroll_subj
    int_fast        --> int_enroll_subj
    int_pearson     --> int_enroll_subj
    int_fldoe       --> int_enroll_subj
    int_iready      --> int_enroll_subj
    int_deanslist   --> int_enroll_subj

    %% ── Edges: DIBELS participation roster ───────────────────────────────────
    int_enroll_subj --> int_dibels_roster
    int_gs_exp      --> int_dibels_roster
    int_all         --> int_dibels_roster

    %% ── Edges: PM met criteria ───────────────────────────────────────────────
    stg_pm          --> int_pm_crit
    int_all         --> int_pm_crit
    int_dibels_roster --> int_pm_crit

    %% ── Edges: → Final report ────────────────────────────────────────────────
    int_enroll_subj  --> RPT
    int_gs_exp       --> RPT
    stg_bm           --> RPT
    int_gs_pm_exp    --> RPT
    stg_pm           --> RPT
    base_ce          --> RPT
    int_all          --> RPT
    int_dibels_roster --> RPT
    int_pm_crit      --> RPT

    %% ── Styling ───────────────────────────────────────────────────────────────
    classDef source    fill:#e8f4f8,stroke:#5b9bd5,color:#000
    classDef staging   fill:#e2f0d9,stroke:#70ad47,color:#000
    classDef base      fill:#fff2cc,stroke:#ffc000,color:#000
    classDef intmodel  fill:#fce4d6,stroke:#ed7d31,color:#000
    classDef report    fill:#d9e1f2,stroke:#4472c4,color:#000,font-weight:bold

    class src_amp,src_gs_exp,src_gs_bm,src_gs_pm,src_gs_long,src_gs_terms,src_gs_xwalk,src_ps_districts,src_ps_spenroll,src_ps_terms,src_ps_schools,src_ps_cal,src_ps_nj_crs,src_ps_nj_stu source
    class stg_exp,stg_bm,stg_pm,stg_long,stg_terms,stg_ps_terms,stg_schools,stg_cal,stg_nj_crs staging
    class base_ce base
    class int_bm_sum,int_bm_unpivot,int_pm_sum,int_all,int_pm_crit,int_gs_exp,int_gs_pm_exp,int_spenroll,int_nj_stu,int_enroll,int_enroll_subj,int_dibels_roster,int_fast,int_pearson,int_fldoe,int_iready,int_deanslist intmodel
    class RPT report
```

### Layer summary

| Layer        | Count | Purpose                                                                   |
| ------------ | ----- | ------------------------------------------------------------------------- |
| Sources      | 14    | Raw Google Sheets, Amplify DDS, and district PowerSchool tables           |
| Staging      | 9     | Light cleaning and type-casting of source data                            |
| Base         | 1     | Union of 4 district `course_enrollments` tables                           |
| Intermediate | 17    | Business logic — enrollment, DIBELS roster, assessment joins, PM criteria |
| Report       | 1     | Final Tableau extract with both Benchmark and PM branches                 |

### Key data flows

**Benchmark branch** — Amplify mClass benchmark summaries (BOY/MOY/EOY) are
joined to the student enrollment/subject roster and filtered against
`int_google_sheets__dibels_expected_assessments` to determine which students
were expected to test. School- and region-level goal aggregates come from
`stg_google_sheets__dibels_bm_goals`.

**PM branch** — Amplify PM summaries are joined to custom goal thresholds from
`stg_google_sheets__dibels_pm_goals` and evaluated in
`int_amplify__pm_met_criteria` to produce met/not-met flags per round. The
criteria logic is AND/OR per round: some rounds require all tracked measures to
be met; others require a specific combination (e.g., measure A OR measure B). PM
eligibility is determined by the preceding benchmark composite score (Below/Well
Below = probe-eligible).

Both the Benchmark and PM branches land in `rpt_tableau__dibels_dashboard` via a
`UNION ALL`.

### Configuration: `stg_google_sheets__dibels_expected_assessments`

This Google Sheet is the primary configuration table for the DIBELS model. It
defines which assessment rounds exist, which measures are expected per round,
and how PM goal logic should be applied. Three fields control behavior:

**`assessment_include`** — scaffold gate. A `NULL` value means the row is active
and will be used as a scaffold for student-level joins. `FALSE` excludes the
entire row from the model. Benchmark administrations (BOY, MOY, EOY) are never
excluded. PM rounds may be retroactively excluded — for example, if a round was
cancelled mid-year — by setting this field to `FALSE`.

**`pm_goal_include`** — goal display gate, independent of `assessment_include`.
A measure can be tested in a round (`assessment_include = NULL`) but excluded
from goal calculation (`pm_goal_include = FALSE`). This handles cases where a
measure was not administered consistently across all rounds of a PM season. For
goal trajectory to be calculated correctly, all rounds must exist in the data;
`pm_goal_include` suppresses the goal display for rounds where the measure
wasn't consistently given, without removing those rows from the scaffold.

Example: in the BOY→MOY season, a measure is tested in rounds 1–4, but another
measure is only given in rounds 2 and 4. The second measure still needs rows for
all four rounds to support the trajectory calculation, but only rounds 2 and 4
have `pm_goal_include = NULL` — rounds 1 and 3 are set to `FALSE` so no goal is
shown.

**`pm_goal_criteria`** — mastery logic for multi-measure PM rounds:

| Value                     | Meaning                                                                                                   |
| ------------------------- | --------------------------------------------------------------------------------------------------------- |
| `NULL`                    | BM rows — field is PM-only; BM rows (`BOY`/`MOY`/`EOY`) are always blank here                             |
| `OR`                      | Mastery on any one of the tested measures = round mastery                                                 |
| `AND`                     | Mastery on all tested measures = round mastery                                                            |
| Combined (e.g., `AND/OR`) | Two measures both met OR a third measure met — group-level logic applied at the `measure_name_code` grain |

In `int_amplify__pm_met_criteria`, this is implemented via `min()` (AND — all
must be 1) and `max()` (OR/NULL — any must be 1) window functions partitioned by
student / round.

### Source of truth: `int_amplify__all_assessments`

The single model any team member should use to pull DIBELS scores. It surfaces
only scores that T&L considers valid for reporting — no consumer needs to
understand historical assessment strategy to use it safely.

#### How validity filtering works

Every branch of the internal UNION inner-joins to
`int_google_sheets__dibels_expected_assessments` on
`academic_year + region + grade + admin_season + measure_standard` with two
additional filters:

- **`assessment_include is null`** — excludes any row the data team has
  explicitly cancelled (e.g., a mid-year PM round cancellation)
- **`pm_goal_include is null`** — for PM, excludes scaffold-only rows that exist
  for trajectory math but don't represent real tested rounds

If a score exists in Amplify but no matching row exists in the expected
assessments config, it is silently excluded. This is intentional — new measures
or grades only appear once the data team adds them to the config.

#### Internal structure

The model has three UNION branches in the `assessments_scores` CTE:

| Branch             | Source                                                     | Scope                            |
| ------------------ | ---------------------------------------------------------- | -------------------------------- |
| Benchmark (mCLASS) | `int_amplify__mclass__benchmark_student_summary` + unpivot | All years except SY24 grades 7–8 |
| Benchmark (DDS)    | `int_amplify__dds__data_farming_unpivot`                   | SY24 grades 7–8 only             |
| PM                 | `int_amplify__mclass__pm_student_summary`                  | All PM years                     |

The `max_score` CTE deduplicates using
`row_number() over (partition by surrogate_key, round_number, measure_standard order by measure_standard_level_int desc)`,
keeping the highest-level score when a student has multiple entries for the same
assessment slot. The final SELECT is a `UNION ALL` of two branches (Benchmark
and PM), each filtered by `rn_highest = 1`.

#### Computed fields

| Field                                               | Logic                                                                                                  |
| --------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `overall_probe_eligible`                            | `'Yes'` if composite at BOY (for BOY period) or MOY (for MOY period) was Below or Well Below Benchmark |
| `boy_composite` / `moy_composite` / `eoy_composite` | Pivoted composite levels — available on every row for cross-window lookups                             |
| `benchmark_goal_season`                             | Next BM season this score contributes goals toward (`BOY` → `MOY`, `MOY` → `EOY`)                      |
| `aggregated_measure_standard_level`                 | Two-bucket: `At/Above` vs `Below/Well Below` (used in Foundation goal reporting)                       |
| `foundation_measure_standard_level`                 | Three-bucket: `At/Above`, `Below`, `Well Below` (used in Foundation goal rate join)                    |

#### Measures by grade (AY 2024–2025)

Which measures appear in `int_amplify__all_assessments` is controlled by
`stg_google_sheets__dibels_expected_assessments`, not hardcoded in the model.
The configuration below reflects AY 2024–2025 and may change year-to-year.

**Benchmark** — consistent across BOY, MOY, and EOY for all grades:

- **K** — Composite, Letter Names (LNF), Phonemic Awareness (PSF), Letter Sounds
  (NWF-CLS), Decoding (NWF-WRC), Word Reading (WRF)
- **Grade 1** — Composite, Letter Names (LNF), Phonemic Awareness (PSF), Letter
  Sounds (NWF-CLS), Decoding (NWF-WRC), Word Reading (WRF), Reading Fluency
  (ORF), Reading Accuracy (ORF-Accu)
- **Grades 2–3** — Composite, Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Word
  Reading (WRF), Reading Fluency (ORF), Reading Accuracy (ORF-Accu), Reading
  Comprehension (Maze)
- **Grades 4–8** — Composite, Reading Fluency (ORF), Reading Accuracy
  (ORF-Accu), Reading Comprehension (Maze)

Early literacy measures (LNF, PSF) exit after grade 1. NWF and WRF exit after
grade 3. ORF, ORF-Accu, and Maze run through grade 8.

**Progress Monitoring** — no Composite; varies by grade and season:

BOY→MOY:

- **K–1** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Phonemic Awareness
  (PSF)
- **Grade 2** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Reading Accuracy
  (ORF-Accu), Reading Comprehension (Maze), Word Reading (WRF)
- **Grade 3** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Reading Accuracy
  (ORF-Accu), Reading Fluency (ORF), Reading Comprehension (Maze), Word Reading
  (WRF)
- **Grades 4–5** — Reading Accuracy (ORF-Accu), Reading Fluency (ORF), Reading
  Comprehension (Maze), Word Reading (WRF)
- **Grades 6–8** — Reading Accuracy (ORF-Accu), Reading Fluency (ORF), Reading
  Comprehension (Maze)

MOY→EOY:

- **K** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Reading Accuracy
  (ORF-Accu), Word Reading (WRF)
- **Grade 1** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Reading Accuracy
  (ORF-Accu), Reading Fluency (ORF), Word Reading (WRF)
- **Grades 2–3** — Letter Sounds (NWF-CLS), Decoding (NWF-WRC), Reading Accuracy
  (ORF-Accu), Reading Fluency (ORF), Reading Comprehension (Maze), Word Reading
  (WRF)
- **Grades 4–5** — Reading Accuracy (ORF-Accu), Reading Fluency (ORF), Reading
  Comprehension (Maze), Word Reading (WRF)
- **Grades 6–8** — Reading Accuracy (ORF-Accu), Reading Fluency (ORF), Reading
  Comprehension (Maze)

!!! note "AY 2026–2027: PM measures will change" With cohort-differentiated
testing (Well Below vs. Below may test different measures) and the aimline
migration, the PM measure set is expected to change. See
[#3834](https://github.com/TEAMSchools/teamster/issues/3834).

#### Assessment strategy history

**Benchmark**:

| Period       | Scope                                                                                        |
| ------------ | -------------------------------------------------------------------------------------------- |
| AY 2021–2023 | K–2 only (primary years of BM implementation)                                                |
| AY 2023–2024 | K–4 added; grades 3–4 coverage inconsistent across regions                                   |
| AY 2023–2024 | MS grades added but also inconsistent                                                        |
| AY 2024–2025 | K–8 implemented; grades 7–8 tested on Amplify DDS (separate platform — see DDS branch above) |
| AY 2025–2026 | First year all K–8 BM data on the same platform (mCLASS); DDS branch is SY24-only from here  |

**Progress Monitoring**:

| Period       | Scope                                                                      |
| ------------ | -------------------------------------------------------------------------- |
| AY 2024–2025 | Camden and Newark only; K–2 only                                           |
| AY 2025–2026 | K–8 for both NJ and FL; Paterson included for the first time               |
| AY 2026–2027 | K–8 all regions; PM source migrates to aimline; model updated, not removed |

#### AY 2026–2027 changes

`int_amplify__all_assessments` retains both BM and PM branches — it is the
single safe read point for all valid assessment scores and must stay that way.
The PM branch will be updated to pull from a new aimline-based PM intermediate
instead of `int_amplify__mclass__pm_student_summary`. The DDS branch stays
indefinitely to preserve SY24 7–8 grade benchmark history. The
`int_google_sheets__dibels_expected_assessments` inner join and all computed
fields remain unchanged for the BM branch.

!!! note "Deprecation approach" Per team convention, deprecated models in this
refactor are **deactivated** (`config: enabled: false` in properties YAML)
rather than deleted. This preserves them as reference implementations for
similar future work.

### Benchmark goal pipeline: `stg_google_sheets__dibels_foundation_goals` → `stg_google_sheets__dibels_bm_goals`

#### What Foundation goals are

KIPP Foundation sets annual benchmark growth targets for MOY and EOY. The
targets are expressed as a **percentage of students who should be At/Above
Benchmark** by that administration, broken out by region, grade level, and
benchmark band (`At/Above` vs. `Well Below`). The T&L team receives these from
Foundation and shares them with the data team, who hand-enters them into the
Google Sheet that becomes `stg_google_sheets__dibels_foundation_goals`.

Grain: one row per
`academic_year × region × grade_level × period × grade_goal_type`.

The hand-entry step is error-prone. The source document from Foundation is not
in a machine-readable format, and transcription mistakes are difficult to catch
until the downstream calculations look wrong.

#### How the goals are calculated: `rpt_gsheets__dibels_bm_goals_calculations`

After each benchmark window (BOY or MOY),
`rpt_gsheets__dibels_bm_goals_calculations` joins the current year's benchmark
composite scores (`int_amplify__all_assessments`) to the Foundation goal rates
(`stg_google_sheets__dibels_foundation_goals`) and computes, per school and
region:

- **Actual counts** — students At/Above and Below/Well Below by grade and
  period, computed at both school and region granularity
- **Expected count** — `ceiling(total_enrolled × grade_goal_rate) + 5` — the
  number of At/Above students the school needs to meet the Foundation target
  plus the T&L planning buffer
- **Students to move** (gap) — `(expected − actual_at_above) × 1.5` — how many
  currently-Below/Well Below students need to reach At/Above to close the gap,
  inflated by 1.5× to build headroom for students who start PM but don't
  complete it. A negative value means the school already exceeds the Foundation
  target.

The `+ 5` and `× 1.5` values are **T&L-set planning buffers** — added at T&L's
request to build in margin above the Foundation floor. Neither is derived from
the Foundation targets themselves. Both should be reconfirmed with T&L at the
start of each academic year before the BOY goals calculation is run (see Annual
rollover procedure below).

!!! warning "Open question: `grade_goal_type` and `max(grade_goal)`"
`stg_google_sheets__dibels_foundation_goals` contains two goal types:
`'At/Above'` and `'Well Below'`, each with its own `grade_goal` rate. The model
collapses them via `max(grade_goal)`, but for some MS grades the Well Below rate
is _higher_ than the At/Above rate — meaning `max()` picks the Well Below rate
and uses it to compute the expected At/Above student count. Whether this is
intentional needs confirmation with T&L before the next BOY goals run. Tracked
in issue [#3834](https://github.com/TEAMSchools/teamster/issues/3834).

#### The snapshot freeze: copy-paste → `stg_google_sheets__dibels_bm_goals`

The output of `rpt_gsheets__dibels_bm_goals_calculations` is **manually
copy-pasted** into a separate Google Sheet, which is the source for
`stg_google_sheets__dibels_bm_goals`. That staged table is what
`rpt_tableau__dibels_dashboard` joins in the Benchmark branch.

The manual step exists deliberately: enrollment corrections and score
adjustments continue after a benchmark window closes, and if the goals were
calculated live from `rpt_gsheets__dibels_bm_goals_calculations`, they would
shift retroactively every time the underlying data changed. The copy-paste
freezes the calculation as of the moment the goals were set, making them stable
for the remainder of the year.

!!! warning "Error risk at two points" The pipeline has two manual steps where
mistakes are hard to catch: (1) hand-entry of Foundation rate targets into
`stg_google_sheets__dibels_foundation_goals`, and (2) the copy-paste from the
calculations extract into the goals sheet. A wrong cell in step 1 silently
produces wrong expected counts; a missed row or column in step 2 produces NULL
goals on the dashboard with no error.

#### Process improvement opportunity

The copy-paste freeze could be replaced with a **Dagster-managed BigQuery
append**: after each benchmark window closes, a one-time asset run would
`INSERT INTO` a permanent BigQuery table the output of
`rpt_gsheets__dibels_bm_goals_calculations` for that year and period. The table
would be partitioned by `academic_year + period` and written once — never
updated. `stg_google_sheets__dibels_bm_goals` would then be replaced by a
`sources-bigquery.yml` entry pointing to that table, eliminating the Google
Sheet intermediary and the copy-paste risk entirely.

The hand-entry problem for Foundation goal rates could be reduced by requesting
the data from Foundation in a CSV or structured format and uploading directly,
rather than transcribing from a document.

### PM expectations scaffold: `int_google_sheets__dibels_pm_expectations`

This intermediate model auto-generates the PM goal calculation scaffold by
joining the three configuration sources together. It replaced an older model,
`stg_amplify__dibels_pm_expectations`, which was a manually-maintained Google
Sheet requiring the data team to enumerate every expected round × measure ×
region × grade combination by hand each year. The current model derives that
same grid automatically from two already-required inputs: the expected
assessments config and the reporting terms calendar.

**What it produces** (one row per
`academic_year × region × grade × admin_season × round_number × measure`):

- All round and measure metadata from
  `int_google_sheets__dibels_expected_assessments` (`round_number`,
  `min_pm_round`, `max_pm_round`, `pm_goal_include`, `pm_goal_criteria`,
  `expected_measure_standard`, etc.)
- Term window dates (`start_date`, `end_date`, `code`) from
  `stg_google_sheets__reporting__terms`
- School day counts (`pm_round_days`, `pm_days`) computed from the PowerSchool
  calendar — counting in-session days within each `LIT`/`PLIT` window by region
- `benchmark_goal` (`grade_level_standard`) from
  `stg_google_sheets__dibels_goals_long`, joined on measure × grade × matching
  PM season

This enriched scaffold is what `rpt_gsheets__dibels_pm_goal_setting` joins to
when computing per-round growth targets — it provides everything needed for the
`pm_round_days / pm_days` proportioning math without any additional manual data
entry.

**AY 2026–2027 outlook**: school-day counting (`pm_round_days`, `pm_days`) and
`benchmark_goal` are confirmed deprecated with the aimline migration — the
`PLIT` rows in `stg_google_sheets__reporting__terms` that feed them go away too.
The round scaffold (which measures are expected per round/region/grade) stays
useful and `int_google_sheets__dibels_pm_expectations` may take on a PM
completion tracking role: determining whether students completed their required
probes for each round. Final scope depends on T&L's PM tracking requirements for
AY 2026–2027 — see open questions in the Upcoming changes section.

### PM goal pipeline: `rpt_gsheets__dibels_pm_goal_setting` → `stg_google_sheets__dibels_pm_goals`

This pipeline is the PM equivalent of the BM goals pipeline described above —
same copy-paste freeze pattern, same motivation, different source calculation
and snapshot timing.

#### History

In AY 2024–2025, the Literacy Team leader hand-calculated per-round PM goals
using the same collective-average methodology. In AY 2025–2026 the data team
automated her process via `rpt_gsheets__dibels_pm_goal_setting`. The methodology
did not change — only the calculation moved into dbt.

#### What the calculation produces

`rpt_gsheets__dibels_pm_goal_setting` takes the average BOY (or MOY) composite
score for probe-eligible (Below/Well Below) students and works out, per region ×
grade × measure × round:

- **`pm_round_days`** — School days before plus during a round, used to
  proportion the round's share of total PM growth.
- **`pm_days`** — Total school days across the full PM admin season (BOY→MOY or
  MOY→EOY).
- **`benchmark_goal`** — Amplify's published word goal for the measure by end of
  admin, padded by **+3 words** and rounded to the nearest tenth.
- **`average_starting_words`** — Average score for Below/Well Below students on
  the given measure at the start of the PM season, rounded to the nearest
  integer.
- **`required_growth_words`** — `benchmark_goal − average_starting_words` (the
  +3 padding is already embedded in `benchmark_goal`), rounded to the nearest
  integer. Total words a student must grow by end of admin to meet the padded
  Amplify goal.
- **`daily_growth_rate`** — `required_growth_words / pm_days`, rounded to 2
  decimal places. Words per school day a student must gain to reach the
  end-of-admin (EOA) goal.
- **`round_growth_words_goal`** — Round 1:
  `(pm_round_days × required_growth_words / pm_days) + average_starting_words`.
  Round 2+: same formula without adding `average_starting_words` (starting
  baseline is not re-added in subsequent rounds).
- **`cumulative_growth_words`** — Running cumulative target by round. This is
  the actual score threshold compared against a student's score in
  `int_amplify__pm_met_criteria`.
- **`benchmark_goal`**, **`pm_goal_include`**, **`pm_goal_criteria`** — passed
  through from `int_google_sheets__dibels_pm_expectations`.

#### The snapshot freeze: copy-paste → `stg_google_sheets__dibels_pm_goals`

Just like the BM pipeline, the output is manually copy-pasted into a Google
Sheet to freeze it before downstream corrections can shift the numbers. The
freeze happens **twice per year**:

- **After BOY testing** (all regions complete) — for the BOY→MOY PM season
- **After MOY testing** (all regions complete) — for the MOY→EOY PM season

`int_amplify__pm_met_criteria` then uses `stg_google_sheets__dibels_pm_goals` as
its goal spine: inner-joining on
`academic_year + region + grade + admin_season + round_number + measure_standard`,
filtering to `pm_goal_include is null` (active goal rows), and comparing each
student's score to `cumulative_growth_words` to set `met_measure_standard_goal`.
The AND/OR round criteria logic runs on top of that.

!!! warning "Entire pipeline deprecated in AY 2026–2027" With aimline providing
per-student goals, `rpt_gsheets__dibels_pm_goal_setting`,
`stg_google_sheets__dibels_pm_goals`, and `int_amplify__pm_met_criteria`'s
current score-comparison logic are all replaced. See the deprecation list in
issue [#3834](https://github.com/TEAMSchools/teamster/issues/3834).

### Reference table: `stg_google_sheets__dibels_goals_long`

A digitized version of the first page of the
[DIBELS 8 Official Goals document](https://dibels.uoregon.edu/sites/default/files/2021-06/DIBELS8thEditionGoals.pdf)
(University of Oregon, 2021). The source sheet maps each measure × grade ×
benchmark administration season to four score thresholds:

| Column                 | Meaning                                                     |
| ---------------------- | ----------------------------------------------------------- |
| `Grade_Level_Standard` | Minimum score to be classified as "At Benchmark" (the norm) |
| `Above`                | Threshold above which a student is "Above Benchmark"        |
| `Below`                | Upper boundary of the "Below Benchmark" band                |
| `Well_Below`           | Upper boundary of the "Well Below Benchmark" band           |

The staging model adds two computed columns:

- **`matching_pm_season`** — maps the BM admin season to the PM window that
  follows it (`MOY` → `BOY→MOY`, `EOY` → `MOY→EOY`). BOY produces NULL because
  there is no PM window before it.
- **`grade_level`** — integer grade; kindergarten mapped from `'K'` to `0`.

**Current use**: `int_google_sheets__dibels_pm_expectations` left joins to this
table on `measure_standard + grade + admin_season` to pull
`grade_level_standard` as `benchmark_goal`. That value was used to derive PM
goals from a collective average of probe-eligible students (Below/Well Below
composite).

**Likely deprecated in AY 2026–2027**: the Amplify aimline file provides a
per-student personalized goal, making the collective-average approach obsolete.
Once `int_amplify__mclass__pm_student_summary` is replaced by the aimline
source, `int_google_sheets__dibels_pm_expectations` will no longer need this
join, and this table can be retired.

### Assessment calendar: `stg_google_sheets__reporting__terms`

A multi-domain Google Sheet (one row per term × region × school) that defines
the date windows for all KIPP TAF reporting periods. The DIBELS model filters to
`type = 'LIT'` rows, which contain three kinds of entries:

- **Benchmark windows** (`code = BOY / MOY / EOY`) — administration start/end
  dates by region.
- **PM round windows** (`code = LIT1`, `LIT2`, … ) — start/end dates for each
  round within a PM season (`BOY→MOY`, `MOY→EOY`), by region.
- **Pre-round windows** (`code = PLIT1`, `PLIT2`, … ) — date ranges covering the
  days _before_ each PM round within the same season window. Added starting AY
  2025–2026.

The `PLIT` rows exist because the collective-average PM goal calculation in
`rpt_gsheets__dibels_pm_goal_setting` apportions each round's goal
proportionally to school days:
`round_goal = (pm_round_days / pm_days) × required_growth`. `pm_round_days` for
round N counts the school days in both the `LITN` window (during the round) and
the `PLITN` window (before the round), giving a longer "elapsed time"
denominator that produces a more accurate daily growth rate. Generating `PLIT`
start/end dates requires consulting each region's academic calendar manually —
one of the more labor-intensive parts of the annual rollover.

**All `PLIT` rows are likely deprecated in AY 2026–2027.** With aimline
providing per-student goals directly, the collective-average goal pipeline
(`rpt_gsheets__dibels_pm_goal_setting` → `stg_google_sheets__dibels_pm_goals`)
is no longer needed, and `pm_round_days` / `pm_days` lose their purpose.

These dates must be manually entered by the data team after receiving the
testing calendar from Teaching & Learning. Like
`stg_google_sheets__dibels_expected_assessments`, this sheet has two separate
update steps:

- **Benchmark dates** can be added at any time — the benchmark schedule is fixed
  and does not require T&L approval to enter.
- **PM round dates** must wait for T&L sign-off on the PM plan for the year,
  since round counts and timing can change.

`int_google_sheets__dibels_expected_assessments` joins to this table to attach
start/end dates to each expected assessment row.
`int_google_sheets__dibels_pm_expectations` uses it to compute the number of
school days in each PM round and season (`pm_round_days`, `pm_days`), which feed
the Tableau dashboard.

!!! warning "Missing LIT rows block date resolution" If
`stg_google_sheets__reporting__terms` does not yet have LIT rows for a new
academic year, downstream models that join to it will produce rows with NULL
dates — no error, just missing window information.

### Historical fixture: `stg_google_sheets__dibels_df_student_xwalk`

This table is a **one-time workaround for AY 2023–2024 (SY24) only** and must
not be removed.

**Background**: In SY24, grades 7–8 took the benchmark assessment for the first
time. At that point, Amplify operated two separate systems: mCLASS (used for
grades K–6) and Data Farming System / DDS (used for grades 7–8). The DDS export
file did not include enrollment region or testing season — information that
every other part of the DIBELS model requires.

**What the table provides**: A hand-maintained crosswalk that maps
`student_number + admin_season → region, grade_level` for the 7/8-grade cohort
in SY24. `int_amplify__dds__data_farming_unpivot` inner joins to it to supply
region and grade for those rows before they enter
`int_amplify__all_assessments`.

**Why it must stay**: Without it, the SY24 7/8-grade benchmark rows would be
missing from the dashboard. The DDS path has a code comment ("7/8 benchmark
scores SY24 only") that confirms the scope is limited. After SY24, grades 7–8
returned to the standard mCLASS system, so no new rows will ever be needed in
this sheet.

### Participation roster: `int_students__dibels_participation_roster`

This model builds a per-student × per-assessment-round participation record by
crossing the enrollment roster against the expected assessment schedule, then
left-joining to actual scores to determine whether each student completed each
round.

#### Structure: three-branch UNION ALL

**Branch 1 — Benchmark**: All enrolled ELA students (K–8, `enroll_status` in
0/2/3) whose enrollment window overlaps a scheduled Benchmark round (BOY/MOY/EOY
from `int_google_sheets__dibels_expected_assessments` where
`assessment_include is null`). Left-joined to `int_amplify__all_assessments` for
actual score rows. `completed_test_round` is `TRUE` under two conditions (either
is sufficient):

- All expected probe rows arrived: `expected_row_count = actual_row_count`
- A non-"No data" composite score exists for the season (fallback for students
  who tested but where not every individual probe row was captured)

**Branch 2 — BOY→MOY PM**: Students where the BOY composite was "Below
Benchmark" or "Well Below Benchmark" (`boy_probe_eligible = 'Yes'`), crossed
against active BOY→MOY rounds. `completed_test_round` is stricter here:
`expected_row_count = actual_row_count` only — there is no composite fallback
for PM.

**Branch 3 — MOY→EOY PM**: Same pattern using `moy_probe_eligible = 'Yes'`
against MOY→EOY rounds.

The final `where rn = 1` deduplicates students whose enrollment date ranges
produce multiple matches against the same assessment window.

#### Grain and purpose

One row per `academic_year + student_number + admin_season + round_number`. This
model is the "did they test" spine. `int_amplify__pm_met_criteria` inner-joins
to it to attach `completed_test_round` / `completed_test_round_int` to each
student-goal row, keeping goal-met and test-completed as separate trackable
fields downstream.

!!! note "Legacy grain: `completed_test_round` in uniqueness key"
`completed_test_round` is part of the uniqueness test grain because an earlier
version of this model also produced rows for assessment windows where the
student was **not enrolled** — which could yield both a TRUE and a FALSE row for
the same student × round combination. The current model filters enrollment dates
correctly, but the dual-row case may still occur at the edges. This is a
candidate for simplification in a future cleanup pass.

#### AY 2026–2027 considerations

The BM branch is unaffected by the aimline migration. The PM branches require
redesign: the aimline file does not provide a reliable completion signal because
T&L picks which standards to test per cohort (Well Below vs. Below students may
be assigned different measures within the same round and grade). The current
`expected_row_count = actual_row_count` check assumes a fixed expected probe
count per student, which no longer holds when expected probes vary by cohort.
`int_google_sheets__dibels_pm_expectations` may be used to derive the correct
expected count per student based on their benchmark band, but the approach needs
design before the first PM round of AY 2026–2027.

---

### PM goal evaluation: `int_amplify__pm_met_criteria`

This model determines, for each probe-eligible student in each PM round, whether
they met their goal — evaluated at three levels of granularity — and produces a
single overall pass/fail flag per student per round.

#### Three-CTE pipeline

**`met_standard_goal`** — The base join layer. Joins the PM goals spine
(`stg_google_sheets__dibels_pm_goals`, filtered to `pm_goal_include is null`) to
actual PM scores from `int_amplify__all_assessments` (type `'PM'`,
`overall_probe_eligible = 'Yes'`), then to the participation roster for
completion status. Two binary goal flags per student × measure standard:

- `met_measure_standard_goal = 1` if score ≥ `cumulative_growth_words` (the
  per-round cumulative growth target)
- `met_admin_benchmark_goal = 1` if score ≥ `benchmark_goal` (the absolute
  benchmark threshold for the season, regardless of PM round)

**`met_measure_code_goal`** — Collapses across measure standards within a
`measure_name_code` group. NWF (Nonsense Word Fluency), for example, has two
standards always tested together — `met_measure_name_code_goal = 1` only when
every standard under the code is met. This prevents partial NWF credit from
satisfying an OR gate at the round level.

**`met_round_criteria`** — Applies the AND/OR logic from `pm_goal_criteria`
across all measure codes for the student in that round:

- `AND`: `min(met_measure_name_code_goal)` — every code must be met
- else: `max(met_measure_name_code_goal)` — meeting any one code is enough

#### Final flag: `met_pm_round_overall_criteria`

The most conservative overall flag:

| `pm_goal_criteria` | `met_pm_round_criteria` | `completed_test_round` | Result |
| ------------------ | ----------------------- | ---------------------- | ------ |
| `'AND'`            | 1                       | `TRUE`                 | 1      |
| `NULL`             | 1                       | any                    | 1      |
| anything else      | any                     | any                    | 0      |

The NULL case does **not** require `completed_test_round` — this is intentional.
`pm_goal_criteria` controls the AND/OR pass logic across measures that were
**expected** to be tested in a given round. When it is NULL, the round has no
formal multi-measure completion requirement: if a student scored on a valid
measure, that score counts without gating on whether they finished every probe.
This matters because `int_amplify__pm_met_criteria` only surfaces assessments
that appear in `stg_google_sheets__dibels_expected_assessments` — unexpected
probes are already excluded upstream — so NULL rounds are genuinely
criteria-free, not data-entry gaps.

#### AY 2026–2027 refactor

The three-CTE structure and AND/OR aggregation logic stay. The changes:

- Goal spine: `stg_google_sheets__dibels_pm_goals` →
  `int_google_sheets__dibels_expected_assessments` (for `pm_goal_criteria`) +
  aimline file (for per-student `aimline_status`)
- `cumulative_growth_words` score comparison → `aimline_status = 'At or Above'`
  check
- `met_admin_benchmark_goal` — score ≥ `benchmark_goal` (the Amplify
  end-of-admin target padded by +3 words from the PM goals sheet). This is an
  absolute season-level threshold, not a round-by-round target — a student who
  reaches it at any round has already hit the full-season standard. In AY
  2026–2027 it will compare against the aimline `goal` field directly.

---

### Final extract: `rpt_tableau__dibels_dashboard`

The model is a two-branch `UNION ALL` — one row per enrolled student × expected
measure standard per administration round. Both branches share the same
enrollment spine and the same output column list (fields not applicable to a
branch are set to `null`).

#### Enrollment spine

Both branches start from `int_extracts__student_enrollments_subjects` filtered
to:

- `iready_subject = 'Reading'` — Reading ELA students only
- `enroll_status in (0, 2, 3)` — active enrollment
- `not is_self_contained`, `not is_out_of_district`

#### BM branch

| Join                | Model                                            | Type  | Effect if no match                                     |
| ------------------- | ------------------------------------------------ | ----- | ------------------------------------------------------ |
| Expected schedule   | `int_google_sheets__dibels_expected_assessments` | INNER | Student × measure must be in the active BM schedule    |
| Foundation goals    | `stg_google_sheets__dibels_bm_goals`             | LEFT  | All goal count columns are NULL (goals not yet frozen) |
| ELA course schedule | `base_powerschool__course_enrollments`           | LEFT  | Teacher / section columns are NULL                     |
| Actual scores       | `int_amplify__all_assessments`                   | LEFT  | Score columns are NULL (student did not test)          |
| Completion flags    | `int_students__dibels_participation_roster`      | LEFT  | Completion columns are NULL                            |

All PM goal fields (`average_starting_words`, `pm_round_days`, `benchmark_goal`,
etc.) and all `met_*` flags are hardcoded `null` in BM rows.

#### PM branch

| Join                 | Model                                               | Type  | Effect if no match                                                                          |
| -------------------- | --------------------------------------------------- | ----- | ------------------------------------------------------------------------------------------- |
| Expected PM schedule | `int_google_sheets__dibels_pm_expectations`         | INNER | Student × measure × round must be in the active PM schedule                                 |
| PM goals spine       | `stg_google_sheets__dibels_pm_goals`                | INNER | Student is **excluded** — no goals row means no PM row                                      |
| Probe eligibility    | `int_amplify__all_assessments` (composite)          | INNER | Student is **excluded** — must have a composite score with `overall_probe_eligible = 'Yes'` |
| ELA course schedule  | `base_powerschool__course_enrollments`              | LEFT  | Teacher / section columns are NULL                                                          |
| Actual PM scores     | `int_amplify__all_assessments` (by round + measure) | LEFT  | Score columns are NULL (student did not test that round)                                    |
| Completion flags     | `int_students__dibels_participation_roster`         | LEFT  | Completion columns are NULL                                                                 |
| Met-goal flags       | `int_amplify__pm_met_criteria`                      | LEFT  | Met-goal flags are NULL                                                                     |

All Foundation BM goal count columns (`n_admin_season_*`) and
`aggregated_measure_standard_level` / `foundation_measure_standard_level` are
`null` in PM rows.

The two INNER joins on the PM branch mean a student only appears in PM rows if
they are (a) probe-eligible with a composite benchmark score **and** (b) have a
corresponding row in the frozen PM goals sheet. This is stricter than the BM
branch, where the Foundation goals join is LEFT and does not filter students
out.

---

## Annual rollover procedure

Two Google Sheets must be updated at the start of each academic year before the
data model will produce rows for that year:

- **`stg_google_sheets__dibels_expected_assessments`** — defines which
  assessment rounds exist, which measures are expected, and PM goal logic
- **`stg_google_sheets__reporting__terms`** — defines the date windows (start /
  end) for each benchmark administration and each PM round

Both sheets have a BM step that can be done immediately and a PM step that
requires T&L sign-off. These steps have different dependencies and can be done
at different times.

### Step 1 — Replicate Benchmark rows (no approval required)

**In `stg_google_sheets__dibels_expected_assessments`**: copy all BM rows (admin
seasons `BOY`, `MOY`, `EOY`) from the prior year and update the `academic_year`
field. The benchmark schedule and measures do not change year-over-year.

**In `stg_google_sheets__reporting__terms`**: add `LIT`-type rows for the BOY,
MOY, and EOY windows with the new academic year's dates. Benchmark dates are
typically known early and do not require T&L input.

### Step 1b — Confirm planning buffer values with T&L (before BOY calculation)

Before running the BOY goals calculation, confirm with Teaching & Learning
whether the two planning buffer values in
`rpt_gsheets__dibels_bm_goals_calculations` should remain the same or change for
the new year:

- **`+ 5`** — added to `ceiling(total × grade_goal)` to produce the expected
  At/Above student count; builds margin above the Foundation floor
- **`× 1.5`** — multiplies the raw gap to produce the intervention target; adds
  headroom for students who start PM but don't complete it

These values are hardcoded in the SQL. If T&L wants different values, the model
must be updated before the BOY snapshot is copy-pasted into
`stg_google_sheets__dibels_bm_goals`.

!!! note "AY 2026–2027: confirm PM buffer equivalents" The aimline migration
introduces per-student goals from Amplify, but T&L may still want planning
buffers applied to PM goal counts or intervention targets. Confirm with T&L what
(if any) padding should be applied in the new PM model before the first PM round
of AY 2026–2027 begins.

### Step 2 — Add PM rows (requires Teaching & Learning sign-off)

These cannot be added until the Teaching & Learning team confirms the PM plan
for the year. T&L delivers **one document per state** (NJ and FL), each
containing:

- Round numbers by PM season (`BOY→MOY`, `MOY→EOY`)
- Date range for each round
- Which measures are expected per region and grade level
- **Starting AY 2026–2027**: which student cohort tests which measures — "Well
  Below Benchmark" students may be assigned different measures than "Below
  Benchmark" students within the same round and grade

Once received, the data team enters the information in both sheets:

- **`stg_google_sheets__dibels_expected_assessments`**: add PM rows with the
  confirmed round numbers, measures, test codes, `pm_goal_include`, and
  `pm_goal_criteria` for each round.
- **`stg_google_sheets__reporting__terms`**: add `LIT`-type rows for each PM
  round with the confirmed start/end dates, by region.

This step must wait for Teaching & Learning guidance regardless of how early in
the year it is attempted. Plan for this dependency when scheduling the rollover.

!!! warning "PM rows block the PM data model" Until Step 2 is complete in both
sheets, the PM data model will produce no rows for the new year — no error, just
missing data.

### Mid-year round cancellations

If a PM round is cancelled after the academic year has started, set
`assessment_include = FALSE` on every row for that round in
`stg_google_sheets__dibels_expected_assessments`. This removes the round from
all downstream scaffolds without deleting the rows — preserving the record that
the round was planned. The change takes effect on the next dbt run after the
sheet is updated.

Benchmark rows (BOY, MOY, EOY) should never be cancelled via this field.

#### Current two-step problem (AY 2023–2026)

Under the collective-average PM goal pipeline, cancelling a round requires a
**second manual step**: the Google Sheet that backs
`stg_google_sheets__dibels_pm_goals` must also be edited to remove or suppress
the cancelled round's goal rows. If only `dibels_expected_assessments` is
updated, the frozen goals sheet still contains goal rows for that round, and
`int_amplify__pm_met_criteria` will continue to use them (because it inner-joins
on `pm_goal_include is null` from the goals sheet, not from the expected
assessments sheet).

These two sheets must therefore stay in sync manually after any mid-year
cancellation — a coordination burden with real risk of inconsistency.

#### AY 2026–2027: partial improvement via aimline

The aimline migration eliminates `stg_google_sheets__dibels_pm_goals` entirely.
After that change, cancelling a round only requires setting
`assessment_include = FALSE` in `stg_google_sheets__dibels_expected_assessments`
— a single-step operation. The `int_amplify__pm_met_criteria` refactor will
source round metadata exclusively from
`int_google_sheets__dibels_expected_assessments`, making the expected
assessments sheet the sole cancellation control.

If PM goals are eventually migrated to a BigQuery-append model (see process
improvements in issue
[#3834](https://github.com/TEAMSchools/teamster/issues/3834)), any
already-frozen goal rows for a cancelled round would need to be suppressed via a
separate override table or a targeted BQ write — not yet designed.

!!! note "AY 2026–2027 design work required: cohort-differentiated measures" The
introduction of cohort-differentiated measures (Well Below vs. Below testing
different things) is a new concept not currently represented in the schema.
`stg_google_sheets__dibels_expected_assessments` does not have a field to
capture which benchmark band a row applies to, and the PM intermediate model
does not yet route students to measures based on their prior composite band.
This will require schema and model design before the first PM round of AY
2026–2027.

## Upcoming changes: AY 2026–2027 PM migration

Starting AY 2026–2027, the PM model migrates from custom goal calculations to
the **Amplify aimline file**
(`stg_amplify__mclass__sftp__pm_student_summary_aimline`). No historical PM data
will be carried forward — the new model starts fresh.

### What the aimline file provides

| Field                                          | Replaces                                                   |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `goal`                                         | Per-student end-of-period goal (was: PM goals sheet)       |
| `aimline_status` (`'At or Above'` / `'Below'`) | Score-vs-goal comparison in `int_amplify__pm_met_criteria` |
| `aimline_value_by_date`                        | Expected score by probe date (new — no prior equivalent)   |
| `measure_standard_score_change`                | Manual score delta calculation (was: `score_change`)       |

The file covers all regions via the location crosswalk join in the kipptaf
staging model. It provides probe-level detail (one row per student / measure /
probe attempt within a PM period).

### What stays the same

- **PM eligibility** is not provided by Amplify — still derived from benchmark
  composite (Below/Well Below) on our side
- **Round assignment** (`round_number`) still driven by
  `stg_google_sheets__dibels_expected_assessments`; `probe_number` from the
  aimline file is not used for reporting
- **`int_amplify__pm_met_criteria`** stays but is refactored:
  `met_measure_standard_goal` is derived from `aimline_status` instead of score
  comparisons; the AND/OR round criteria logic across measures is retained
- **Testing seasons** (BOY→MOY, MOY→EOY) remain the same; only the testing
  cadence within each season changes

### Models being deprecated

| Model                                     | Reason                                                              |
| ----------------------------------------- | ------------------------------------------------------------------- |
| `stg_google_sheets__dibels_pm_goals`      | Goals and status now come from aimline                              |
| `int_amplify__mclass__pm_student_summary` | Replaced by aimline source                                          |
| `rpt_gsheets__dibels_pm_goal_setting`     | Collective-average goal calculation replaced by per-student aimline |
| `PLIT` rows in `reporting__terms`         | Pre-round school day counting no longer needed without goal calc    |

### `pm_goal_criteria` — AND/OR round logic

`pm_goal_criteria` is a column in the source Google Sheet
(`src_google_sheets__dibels__expected_assessments`), passes through
`stg_google_sheets__dibels_expected_assessments` via `select *`, and is
explicitly selected in `int_google_sheets__dibels_expected_assessments`. The
refactored `int_amplify__pm_met_criteria` will source it from there, making
`stg_google_sheets__dibels_pm_goals` fully deprecatable.

### PM status system — Bright Spots (AY 2026–2027)

T&L has defined a **5-tier PM status** to replace the binary `aimline_status`
provided by Amplify. Status is computed per student per round and varies across
three dimensions:

| Dimension       | Values               |
| --------------- | -------------------- |
| PM period       | MOY, EOY             |
| Grade band      | GK–5, G6–8           |
| Benchmark group | At/Above, Well Below |

The five tiers from best to worst:

| Tier        | Meaning                                 |
| ----------- | --------------------------------------- |
| Bright Spot | Score significantly exceeds the PM goal |
| On Track    | Score at or near the PM goal            |
| In Range    | Score slightly below the PM goal        |
| Off Track   | Score significantly below the PM goal   |
| Not Tested  | No score recorded for the round         |

#### Status thresholds

Status is computed from `gap_to_goal = score - goal` (goal from the aimline
file).

**GK–5 — At/Above students:**

| Tier        | `gap_to_goal`          |
| ----------- | ---------------------- |
| Bright Spot | ≥ +5                   |
| On Track    | +1 to +4               |
| In Range    | −1 to −5               |
| Off Track   | more than 5 below goal |

**G6–8 — At/Above students** (tighter bands; exact thresholds pending T&L
confirmation — see [Open questions](#open-questions-as-of-may-2026)):

| Tier        | `gap_to_goal`          |
| ----------- | ---------------------- |
| Bright Spot | ≥ +5                   |
| On Track    | +1 to +3               |
| In Range    | −1 to −4               |
| Off Track   | more than 5 below goal |

!!! note "Well Below thresholds — direction needs clarification" T&L's document
defines Well Below students with status bands that appear directionally inverted
relative to At/Above: "On Track" is 1–4 points _below_ the goal; "Off Track" is
more than 5 points _above_ the goal. The intended interpretation must be
confirmed with T&L before implementation. See
[Open questions](#open-questions-as-of-may-2026).

#### Data model requirements

| New field         | Derivation                                                            | Model                          |
| ----------------- | --------------------------------------------------------------------- | ------------------------------ |
| `gap_to_goal`     | `score - goal` (goal from aimline file)                               | `int_amplify__pm_met_criteria` |
| `grade_band`      | `CASE WHEN assessment_grade_int <= 5 THEN 'GK-5' ELSE 'G6-8' END`     | Same                           |
| `pm_cohort_group` | Derived from prior BM composite band — not provided by Amplify        | Same                           |
| `pm_status`       | 5-tier CASE on `gap_to_goal`, `grade_band`, `pm_cohort_group`         | Same                           |
| `is_sped`         | Student join (PowerSchool) — only if SPED goals branch is implemented | TBD                            |

All five fields must be surfaced in `rpt_tableau__dibels_dashboard`.

#### SPED goals (nice to have)

T&L's document includes a separate SPED goals branch with the same 4-tier status
structure. Implementing requires: (a) a SPED-specific PM goals data source
(currently unknown), (b) a staging model for that source, and (c) an `is_sped`
flag derived from PowerSchool. This is **not in scope** for the initial AY
2026–2027 migration.

### Open questions (as of May 2026)

- **Expected PM measures** — not yet defined in
  `stg_google_sheets__dibels_expected_assessments`; to be confirmed with T&L
  later in the summer
- **T&L PM tracking requirements for aimline** — until T&L confirms what they
  want to see on the dashboard for AY 2026–2027 PM, the following cannot be
  finalized: (a) which goal display fields replace the collective-average growth
  columns in `rpt_tableau__dibels_dashboard`; (b) whether
  `int_google_sheets__dibels_pm_expectations` is simplified or replaced; (c)
  whether any aimline fields (`aimline_value_by_date`, score change) need to be
  surfaced directly
- **PM completion signal redesign** — the
  `expected_row_count = actual_row_count` check in
  `int_students__dibels_participation_roster` needs a new approach for
  cohort-differentiated testing; `int_google_sheets__ dibels_pm_expectations` is
  a candidate for deriving the correct expected probe count per student by
  benchmark band
- **`probe_eligible_tag` deduplication** — `int_amplify__all_assessments` uses
  `select distinct` with a `-- TODO` comment noting the original row-number
  deduplication approach failed; needs a correct fix before the aimline
  migration adds new PM rows that may hit the same edge cases
- **`grade_goal_type` / `max(grade_goal)`** — Foundation provides both
  `'At/Above'` and `'Well Below'` goal rates; `max(grade_goal)` picks the wrong
  rate for MS grades where Well Below > At/Above; confirm intended behavior with
  T&L before next BOY goals run
- **Well Below PM status direction** — T&L's Bright Spots document shows Well
  Below student status tiers with direction inverted relative to At/Above: "On
  Track" is 1–4 points _below_ the goal; "Off Track" is more than 5 points
  _above_ the goal; intended interpretation must be confirmed with T&L before
  implementing the `pm_status` CASE logic in `int_amplify__pm_met_criteria`
- **SPED PM goals data source** — T&L's Bright Spots document includes a
  SPED-specific status branch (marked "nice to have"); implementing requires a
  SPED PM goals source not currently in the model — confirm whether one exists
  and what format it takes
- **G6–8 Bright Spots exact thresholds** — T&L's document shows different On
  Track / In Range thresholds for G6–8 (approximately On Track: +1 to +3, In
  Range: −1 to −4); exact values need T&L confirmation before implementing the
  `pm_status` CASE logic

### Planned improvements

- **BM historical goals** — `rpt_gsheets__dibels_bm_goals_calculations` is
  current-year-only; prior-year goal counts exist only in the frozen
  `stg_google_sheets__dibels_bm_goals` snapshot. A Dagster-managed BigQuery
  append will replace the copy-paste freeze and build historical data going
  forward (tracked in
  [#3834](https://github.com/TEAMSchools/teamster/issues/3834))

Tracking issue: [#3834](https://github.com/TEAMSchools/teamster/issues/3834)
