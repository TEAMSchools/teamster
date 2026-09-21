select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level as grade_level_int,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.is_homeless,
    s.iep_status,
    s.is_504,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.enroll_status,
    s.advisory,
    s.cohort,
    s.hos,
    s.nj_student_tier,
    s.is_tutoring as tutoring_nj,
    s.is_sipps,
    s.mtss_enrollment,

    'Benchmark' as assessment_type,
    'BM' as model_type,

    a.start_date as expected_start_date,
    a.end_date as expected_end_date,
    a.admin_season as expected_test,
    a.month_round as expected_month_round,
    a.grade as expected_grade_level_int,
    a.expected_measure_name_code,
    a.expected_measure_name,
    a.expected_measure_standard,

    g.benchmark_goal_season as admin_goal_season,
    g.grade_goal as admin_goal,
    g.grade_range_goal as admin_goal_grade_range,
    g.n_admin_season_school_gl_all,
    g.n_admin_season_school_gl_at_above,
    g.n_admin_season_school_gl_bl_wb,
    g.n_admin_season_school_gl_at_above_expected,
    g.n_admin_season_school_gl_at_above_gap,
    g.n_admin_season_region_gl_all,
    g.n_admin_season_region_gl_at_above,
    g.n_admin_season_region_gl_bl_wb,
    g.n_admin_season_region_gl_at_above_expected,
    g.n_admin_season_region_gl_at_above_gap,

    a.grade as grade_level,
    a.grade_level_text as expected_grade_level,

    cast(null as int64) as average_starting_words,
    cast(null as int64) as pm_round_days,
    cast(null as int64) as pm_days,
    cast(null as float64) as benchmark_goal,
    cast(null as float64) as benchmark_goal_padded,
    cast(null as int64) as required_growth_words,
    cast(null as float64) as daily_growth_rate,
    cast(null as int64) as round_growth_words_goal,
    cast(null as float64) as goal,
    cast(null as float64) as aimline_season_student_goal,
    cast(null as float64) as aimline_season_student_goal_gap,

    c.students_student_number as schedule_student_number,
    c.cc_teacherid as teacherid,
    c.teacher_lastfirst as teacher_name,
    c.courses_course_name as course_name,
    c.cc_course_number as course_number,
    c.cc_section_number as section_number,

    b.student_number as mclass_student_number,
    b.assessment_grade,
    b.period,
    b.client_date,
    b.start_date,
    b.end_date,
    b.measure_name,
    b.measure_name_code,
    b.measure_standard,
    b.measure_standard_score,
    b.measure_standard_level,
    b.measure_standard_level_int,
    b.measure_percentile,
    b.measure_semester_growth,
    b.measure_year_growth,
    b.boy_composite,
    b.moy_composite,
    b.eoy_composite,
    b.aggregated_measure_standard_level,
    b.foundation_measure_standard_level,

    r.expected_row_count,
    r.actual_row_count,
    r.completed_test_round,
    r.completed_test_round_int,
    r.participation_group,
    r.round_test_status,

    cast(null as int64) as met_measure_standard_goal,
    cast(null as int64) as met_admin_benchmark_goal,
    cast(null as int64) as met_admin_benchmark_goal_unpadded,
    cast(null as int64) as met_measure_name_code_goal,
    cast(null as int64) as met_pm_round_criteria,
    cast(null as int64) as met_pm_round_overall_criteria,
    cast(null as string) as measure_standard_goal_status,
    cast(null as string) as measure_name_code_goal_status,
    cast(null as string) as admin_benchmark_goal_status,
    cast(null as string) as pm_round_status,
    cast(null as string) as measure_name_code_benchmark_status,
    cast(null as string) as round_benchmark_status,
    cast(null as string) as measure_name_code_aimline_benchmark_status,
    cast(null as string) as measure_name_code_trajectory_status,
    cast(null as string) as round_trajectory_status,
    cast(null as string) as aimline_cohort_level,
    cast(null as int64) as missed_aimline_consecutive,
    cast(null as string) as aimline_category,

    cast(a.round_number as string) as expected_round_number,
    cast(null as string) as expected_round_label,

    if(
        a.round_number = max(
            if(
                a.start_date <= current_date('{{ var("local_timezone") }}'),
                a.round_number,
                null
            )
        ) over (partition by s.academic_year, s.region, a.grade),
        'Current',
        a.admin_season
    ) as expected_round_selection,
    cast(null as string) as measure_standard_round_verdicts,

    right(c.courses_course_name, 1) as schedule_student_grade_level,

    if(b.measure_standard is null, 'Not Tested', 'Tested') as measure_test_status,

    if(c.students_student_number = s.student_number, 1, 0) as scheduled,

    cast(null as string) as aimline_trajectory_category,
    cast(null as string) as aimline_round_category,

from {{ ref("int_extracts__student_enrollments_subjects") }} as s
inner join
    {{ ref("int_google_sheets__dibels_expected_assessments") }} as a
    on s.academic_year = a.academic_year
    and s.region = a.region
    and s.grade_level = a.grade
    and (
        a.start_date between s.entrydate and s.exitdate
        or a.end_date between s.entrydate and s.exitdate
    )
    and a.assessment_type = 'Benchmark'
    and a.assessment_include is null
left join
    {{ ref("stg_google_sheets__dibels_bm_goals") }} as g
    on a.academic_year = g.academic_year
    and a.region = g.region
    and a.grade = g.assessment_grade_int
    and a.admin_season = g.period
    and s.school = g.school
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on s.academic_year = c.cc_academic_year
    and s.schoolid = c.cc_schoolid
    and s.student_number = c.students_student_number
    and s._dbt_source_project = c._dbt_source_project
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.cc_section_number not like '%SC%'
    and c.courses_course_name in (
        'ELA GrK',
        'ELA K',
        'ELA Gr1',
        'ELA Gr2',
        'ELA Gr3',
        'ELA Gr4',
        'ELA Gr5',
        'ELA Gr6',
        'ELA Gr7',
        'ELA Gr8'
    )
left join
    {{ ref("int_amplify__all_assessments") }} as b
    on a.academic_year = b.academic_year
    and a.admin_season = b.period
    and a.expected_measure_standard = b.measure_standard
    and s.student_number = b.student_number
left join
    {{ ref("int_students__dibels_participation_roster") }} as r
    on a.academic_year = r.academic_year
    and a.grade = r.grade_level
    and a.admin_season = r.admin_season
    and a.round_number = r.round_number
    and s.student_number = r.student_number
where
    s.iready_subject = 'Reading'
    and not s.is_self_contained
    and not s.is_out_of_district
    and s.enroll_status in (0, 2, 3)

union all

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level as grade_level_int,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.is_homeless,
    s.iep_status,
    s.is_504,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.enroll_status,
    s.advisory,
    s.cohort,
    s.hos,
    s.nj_student_tier,
    s.is_tutoring as tutoring_nj,
    s.is_sipps,
    s.mtss_enrollment,

    'PM' as assessment_type,
    'Internal' as model_type,

    e.start_date as expected_start_date,
    e.end_date as expected_end_date,
    e.admin_season as expected_test,
    e.month_round as expected_month_round,
    e.grade as expected_grade_level_int,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,

    cast(null as string) as admin_goal_season,
    cast(null as float64) as admin_goal,
    cast(null as float64) as admin_goal_grade_range,
    cast(null as int64) as n_admin_season_school_gl_all,
    cast(null as int64) as n_admin_season_school_gl_at_above,
    cast(null as int64) as n_admin_season_school_gl_bl_wb,
    cast(null as int64) as n_admin_season_school_gl_at_above_expected,
    cast(null as float64) as n_admin_season_school_gl_at_above_gap,
    cast(null as int64) as n_admin_season_region_gl_all,
    cast(null as int64) as n_admin_season_region_gl_at_above,
    cast(null as int64) as n_admin_season_region_gl_bl_wb,
    cast(null as int64) as n_admin_season_region_gl_at_above_expected,
    cast(null as float64) as n_admin_season_region_gl_at_above_gap,

    g.assessment_grade_int as grade_level,
    g.assessment_grade as expected_grade_level,
    g.starting_words as average_starting_words,
    g.pm_round_days,
    g.pm_days,
    g.benchmark_goal,
    g.benchmark_goal_padded,
    g.required_growth_words,
    g.daily_growth_rate,
    g.round_growth_words_goal,
    g.cumulative_growth_words as goal,
    cast(null as float64) as aimline_season_student_goal,
    cast(null as float64) as aimline_season_student_goal_gap,

    c.students_student_number as schedule_student_number,
    c.cc_teacherid as teacherid,
    c.teacher_lastfirst as teacher_name,
    c.courses_course_name as course_name,
    c.cc_course_number as course_number,
    c.cc_section_number as section_number,

    a.student_number as mclass_student_number,
    a.assessment_grade,
    a.period,
    a.client_date,
    a.start_date,
    a.end_date,
    a.measure_name,
    a.measure_name_code,
    a.measure_standard,
    a.measure_standard_score,
    a.measure_standard_level,
    a.measure_standard_level_int,
    a.measure_percentile,
    a.measure_semester_growth,
    a.measure_year_growth,

    r.boy_composite,
    r.moy_composite,
    r.eoy_composite,

    cast(null as string) as aggregated_measure_standard_level,
    cast(null as string) as foundation_measure_standard_level,

    rs.expected_row_count,
    rs.actual_row_count,
    rs.completed_test_round,
    rs.completed_test_round_int,
    rs.participation_group,
    rs.round_test_status,

    pm.met_measure_standard_goal,
    pm.met_admin_benchmark_goal,
    pm.met_admin_benchmark_goal_unpadded,
    pm.met_measure_name_code_goal,
    pm.met_pm_round_criteria,
    pm.met_pm_round_overall_criteria,
    -- int_amplify__pm_met_criteria holds scored rows only, so a student who was
    -- expected to test and did not has no row there and arrives null. Naming that
    -- state here keeps every PM row carrying a real label, which leaves null on
    -- these three columns meaning one thing only: a Benchmark row.
    coalesce(
        pm.measure_standard_goal_status, 'Not Tested'
    ) as measure_standard_goal_status,
    coalesce(
        pm.measure_name_code_goal_status, 'Not Tested'
    ) as measure_name_code_goal_status,
    coalesce(
        pm.admin_benchmark_goal_status, 'Not Tested'
    ) as admin_benchmark_goal_status,
    coalesce(
        max(pm.pm_round_status) over (
            partition by
                s.academic_year,
                s.region,
                s.student_number,
                e.admin_season,
                e.round_number
        ),
        'Not Tested'
    ) as pm_round_status,
    coalesce(
        pm.measure_name_code_benchmark_status, 'Not Tested'
    ) as measure_name_code_benchmark_status,
    coalesce(
        max(pm.round_benchmark_status) over (
            partition by
                s.academic_year,
                s.region,
                s.student_number,
                e.admin_season,
                e.round_number
        ),
        'Not Tested'
    ) as round_benchmark_status,
    cast(null as string) as measure_name_code_aimline_benchmark_status,
    cast(null as string) as measure_name_code_trajectory_status,
    cast(null as string) as round_trajectory_status,
    cast(null as string) as aimline_cohort_level,
    cast(null as int64) as missed_aimline_consecutive,
    cast(null as string) as aimline_category,

    cast(e.round_number as string) as expected_round_number,
    concat(
        e.admin_season, ': R', cast(e.round_number as string)
    ) as expected_round_label,

    if(
        e.round_number = max(
            if(
                e.start_date <= current_date('{{ var("local_timezone") }}'),
                e.round_number,
                null
            )
        ) over (partition by s.academic_year, s.region, e.grade),
        'Current',
        concat(e.admin_season, ': R', cast(e.round_number as string))
    ) as expected_round_selection,
    string_agg(
        case
            when pm.measure_standard_goal_status is null
            then '.'
            when pm.met_measure_standard_goal = 1
            then 'A'
            when pm.met_measure_standard_goal = 0
            then 'B'
            else '?'
        end,
        '-'
    ) over (
        partition by
            s.academic_year,
            s.region,
            s.student_number,
            e.expected_measure_standard,
            e.admin_season
        order by e.round_number
        rows between unbounded preceding and unbounded following
    ) as measure_standard_round_verdicts,

    right(c.courses_course_name, 1) as schedule_student_grade_level,

    if(a.measure_standard is null, 'Not Tested', 'Tested') as measure_test_status,

    if(c.students_student_number = s.student_number, 1, 0) as scheduled,

    cast(null as string) as aimline_trajectory_category,
    cast(null as string) as aimline_round_category,

from {{ ref("int_extracts__student_enrollments_subjects") }} as s
inner join
    {{ ref("int_google_sheets__dibels_pm_expectations") }} as e
    on s.academic_year = e.academic_year
    and s.region = e.region
    and s.grade_level = e.grade
    and (
        e.start_date between s.entrydate and s.exitdate
        or e.end_date between s.entrydate and s.exitdate
    )
    and e.pm_goal_include is null
inner join
    {{ ref("stg_google_sheets__dibels_pm_goals") }} as g
    on e.academic_year = g.academic_year
    and e.region = g.region
    and e.admin_season = g.admin_season
    and e.round_number = g.round_number
    and e.grade = g.assessment_grade_int
    and e.expected_measure_standard = g.measure_standard
    and g.pm_goal_include is null
inner join
    {{ ref("int_amplify__all_assessments") }} as r
    on s.academic_year = r.academic_year
    and s.student_number = r.student_number
    and s.grade_level = r.assessment_grade_int
    and e.admin_season = r.matching_season
    and r.measure_standard = 'Composite'
    and r.overall_probe_eligible = 'Yes'
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on s.academic_year = c.cc_academic_year
    and s.schoolid = c.cc_schoolid
    and s.student_number = c.students_student_number
    and s._dbt_source_project = c._dbt_source_project
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.cc_section_number not like '%SC%'
    and c.courses_course_name in (
        'ELA GrK',
        'ELA K',
        'ELA Gr1',
        'ELA Gr2',
        'ELA Gr3',
        'ELA Gr4',
        'ELA Gr5',
        'ELA Gr6',
        'ELA Gr7',
        'ELA Gr8'
    )
-- this branch is the INTERNAL method's: it reads the internal expectation gate,
-- the frozen custom goals sheet and int_amplify__pm_met_criteria. Both joins
-- below now carry a row per data method, so without model_type each one matches
-- Internal AND Aimline -- measured at exactly 2 rows per group on every group,
-- compounding to 4x across the pair.
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on e.academic_year = a.academic_year
    and e.admin_season = a.period
    and e.round_number = a.round_number
    and e.expected_measure_standard = a.measure_standard
    and s.student_number = a.student_number
    and a.model_type = 'Internal'
left join
    {{ ref("int_students__dibels_participation_roster") }} as rs
    on e.academic_year = rs.academic_year
    and e.grade = rs.grade_level
    and e.admin_season = rs.admin_season
    and e.round_number = rs.round_number
    and s.student_number = rs.student_number
    and rs.model_type = 'Internal'
left join
    {{ ref("int_amplify__pm_met_criteria") }} as pm
    on e.academic_year = pm.academic_year
    and e.grade = pm.assessment_grade_int
    and e.admin_season = pm.admin_season
    and e.round_number = pm.round_number
    and e.expected_measure_standard = pm.measure_standard
    and s.student_number = pm.student_number
where
    s.iready_subject = 'Reading'
    and not s.is_self_contained
    and not s.is_out_of_district
    and s.enroll_status in (0, 2, 3)

union all

select
    s._dbt_source_relation,
    s.academic_year,
    s.academic_year_display,
    s.district,
    s.state,
    s.region,
    s.school_level,
    s.schoolid,
    s.school,
    s.studentid,
    s.student_number,
    s.student_name,
    s.grade_level as grade_level_int,
    s.is_out_of_district,
    s.gender,
    s.ethnicity,
    s.is_homeless,
    s.iep_status,
    s.is_504,
    s.lep_status,
    s.lunch_status,
    s.gifted_and_talented,
    s.enroll_status,
    s.advisory,
    s.cohort,
    s.hos,
    s.nj_student_tier,
    s.is_tutoring as tutoring_nj,
    s.is_sipps,
    s.mtss_enrollment,

    'PM' as assessment_type,
    'Aimline' as model_type,

    e.start_date as expected_start_date,
    e.end_date as expected_end_date,
    e.admin_season as expected_test,
    e.month_round as expected_month_round,
    e.grade as expected_grade_level_int,
    e.expected_measure_name_code,
    e.expected_measure_name,
    e.expected_measure_standard,

    cast(null as string) as admin_goal_season,
    cast(null as float64) as admin_goal,
    cast(null as float64) as admin_goal_grade_range,
    cast(null as int64) as n_admin_season_school_gl_all,
    cast(null as int64) as n_admin_season_school_gl_at_above,
    cast(null as int64) as n_admin_season_school_gl_bl_wb,
    cast(null as int64) as n_admin_season_school_gl_at_above_expected,
    cast(null as float64) as n_admin_season_school_gl_at_above_gap,
    cast(null as int64) as n_admin_season_region_gl_all,
    cast(null as int64) as n_admin_season_region_gl_at_above,
    cast(null as int64) as n_admin_season_region_gl_bl_wb,
    cast(null as int64) as n_admin_season_region_gl_at_above_expected,
    cast(null as float64) as n_admin_season_region_gl_at_above_gap,

    e.grade as grade_level,
    e.grade_level_text as expected_grade_level,

    cast(null as int64) as average_starting_words,
    cast(null as int64) as pm_round_days,
    cast(null as int64) as pm_days,

    e.benchmark_goal,

    cast(null as float64) as benchmark_goal_padded,
    cast(null as int64) as required_growth_words,
    cast(null as float64) as daily_growth_rate,
    cast(null as int64) as round_growth_words_goal,
    pm.aimline_value_by_date as goal,
    pm.aimline_season_student_goal,
    a.measure_standard_score
    - pm.aimline_season_student_goal as aimline_season_student_goal_gap,

    c.students_student_number as schedule_student_number,
    c.cc_teacherid as teacherid,
    c.teacher_lastfirst as teacher_name,
    c.courses_course_name as course_name,
    c.cc_course_number as course_number,
    c.cc_section_number as section_number,

    a.student_number as mclass_student_number,
    a.assessment_grade,
    a.period,
    a.client_date,
    a.start_date,
    a.end_date,
    a.measure_name,
    a.measure_name_code,
    a.measure_standard,
    a.measure_standard_score,
    a.measure_standard_level,
    a.measure_standard_level_int,
    a.measure_percentile,
    a.measure_semester_growth,
    a.measure_year_growth,

    r.boy_composite,
    r.moy_composite,
    r.eoy_composite,

    cast(null as string) as aggregated_measure_standard_level,
    cast(null as string) as foundation_measure_standard_level,

    rs.expected_row_count,
    rs.actual_row_count,
    rs.completed_test_round,
    rs.completed_test_round_int,
    rs.participation_group,
    rs.round_test_status,

    pm.met_measure_standard_goal,
    pm.met_admin_benchmark_goal,
    cast(null as int64) as met_admin_benchmark_goal_unpadded,
    pm.met_measure_name_code_goal,
    pm.met_pm_round_criteria,
    pm.met_pm_round_overall_criteria,

    coalesce(
        pm.measure_standard_goal_status, 'Not Tested'
    ) as measure_standard_goal_status,
    coalesce(
        pm.measure_name_code_goal_status, 'Not Tested'
    ) as measure_name_code_goal_status,
    coalesce(
        pm.admin_benchmark_goal_status, 'Not Tested'
    ) as admin_benchmark_goal_status,
    coalesce(
        max(pm.pm_round_status) over (
            partition by
                s.academic_year,
                s.region,
                s.student_number,
                e.admin_season,
                e.round_number
        ),
        'Not Tested'
    ) as pm_round_status,
    coalesce(
        pm.measure_name_code_benchmark_status, 'Not Tested'
    ) as measure_name_code_benchmark_status,
    coalesce(
        max(pm.round_benchmark_status) over (
            partition by
                s.academic_year,
                s.region,
                s.student_number,
                e.admin_season,
                e.round_number
        ),
        'Not Tested'
    ) as round_benchmark_status,
    coalesce(
        pm.measure_name_code_aimline_benchmark_status, 'Not Tested'
    ) as measure_name_code_aimline_benchmark_status,
    coalesce(
        pm.measure_name_code_trajectory_status, 'Not Tested'
    ) as measure_name_code_trajectory_status,
    coalesce(
        max(pm.round_trajectory_status) over (
            partition by
                s.academic_year,
                s.region,
                s.student_number,
                e.admin_season,
                e.round_number
        ),
        'Not Tested'
    ) as round_trajectory_status,

    r.overall_aimline_composite_level as aimline_cohort_level,

    pm.missed_aimline_consecutive,

    coalesce(pm.aimline_category, 'Not Tested') as aimline_category,

    cast(e.round_number as string) as expected_round_number,
    concat(
        e.admin_season, ': R', cast(e.round_number as string)
    ) as expected_round_label,

    if(
        e.round_number = max(
            if(
                e.start_date <= current_date('{{ var("local_timezone") }}'),
                e.round_number,
                null
            )
        ) over (partition by s.academic_year, s.region, e.grade),
        'Current',
        concat(e.admin_season, ': R', cast(e.round_number as string))
    ) as expected_round_selection,
    string_agg(
        case
            when pm.measure_standard_goal_status is null
            then '.'
            when pm.met_measure_standard_goal = 1
            then 'A'
            when pm.met_measure_standard_goal = 0
            then 'B'
            else '?'
        end,
        '-'
    ) over (
        partition by
            s.academic_year,
            s.region,
            s.student_number,
            e.expected_measure_standard,
            e.admin_season
        order by e.round_number
        rows between unbounded preceding and unbounded following
    ) as measure_standard_round_verdicts,

    right(c.courses_course_name, 1) as schedule_student_grade_level,

    if(a.measure_standard is null, 'Not Tested', 'Tested') as measure_test_status,

    if(c.students_student_number = s.student_number, 1, 0) as scheduled,

    -- academics' four reporting buckets plus the untested row, deliberately
    -- ignoring round completeness: their legend has no Round Incomplete slice,
    -- so a row classifies on its own verdict. Read off the two flags rather
    -- than aimline_category, which applies T&L's benchmark-wins rule and would
    -- report a below-aimline row as meeting one.
    case
        when a.measure_standard is null
        then 'Not Tested'
        when pm.met_measure_standard_goal is null
        then 'No Aimline Data'
        when pm.met_measure_standard_goal = 0
        then 'Below Aimline'
        when pm.met_admin_benchmark_goal = 1
        then 'On Track to Benchmark'
        else 'On Aimline, Below Benchmark'
    end as aimline_trajectory_category,

    -- pm is null on the measures a student skipped, so the roster's
    -- round-grain status supplies those rows rather than a window broadcast.
    case
        when rs.round_test_status = 'Not Tested'
        then 'Not Tested'
        when rs.round_test_status = 'Round Incomplete'
        then 'Round Incomplete'
        else coalesce(pm.aimline_round_category, 'Not Tested')
    end as aimline_round_category,

from {{ ref("int_extracts__student_enrollments_subjects") }} as s
inner join
    {{ ref("int_amplify__benchmark_student_summary") }} as r
    on s.academic_year = r.academic_year
    and s.student_number = r.student_number
    and s.grade_level = r.assessment_grade_int
    and r.rn_pm_eligibility = 1
inner join
    {{ ref("int_google_sheets__dibels__expected_assessments_by_levels") }} as e
    on s.academic_year = e.academic_year
    and s.region = e.region
    and s.grade_level = e.grade
    and r.matching_season = e.admin_season
    and r.overall_aimline_composite_level = e.measure_standard_level
    and (
        e.start_date between s.entrydate and s.exitdate
        or e.end_date between s.entrydate and s.exitdate
    )
    and e.assessment_include is null
    and e.pm_goal_include is null
left join
    {{ ref("base_powerschool__course_enrollments") }} as c
    on s.academic_year = c.cc_academic_year
    and s.schoolid = c.cc_schoolid
    and s.student_number = c.students_student_number
    and s._dbt_source_project = c._dbt_source_project
    and c.rn_course_number_year = 1
    and not c.is_dropped_section
    and c.cc_section_number not like '%SC%'
    and c.courses_course_name in (
        'ELA GrK',
        'ELA K',
        'ELA Gr1',
        'ELA Gr2',
        'ELA Gr3',
        'ELA Gr4',
        'ELA Gr5',
        'ELA Gr6',
        'ELA Gr7',
        'ELA Gr8'
    )
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on e.academic_year = a.academic_year
    and e.admin_season = a.period
    and e.round_number = a.round_number
    and e.expected_measure_standard = a.measure_standard
    and s.student_number = a.student_number
    and a.model_type = 'Aimline'
left join
    {{ ref("int_students__dibels_participation_roster") }} as rs
    on e.academic_year = rs.academic_year
    and e.grade = rs.grade_level
    and e.admin_season = rs.admin_season
    and e.round_number = rs.round_number
    and s.student_number = rs.student_number
    and rs.model_type = 'Aimline'
left join
    {{ ref("int_amplify__pm_met_criteria_aimline") }} as pm
    on e.academic_year = pm.academic_year
    and e.grade = pm.assessment_grade_int
    and e.admin_season = pm.admin_season
    and e.round_number = pm.round_number
    and e.expected_measure_standard = pm.measure_standard
    and s.student_number = pm.student_number
where
    s.iready_subject = 'Reading'
    and not s.is_self_contained
    and not s.is_out_of_district
    and s.enroll_status in (0, 2, 3)
