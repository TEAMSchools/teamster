with
    dibels_benchmark as (
        select
            academic_year,
            student_number,
            measure_standard_level,
            measure_standard_level_int,
            client_date,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_name_code = 'Composite'
    ),

    dibels_dedupe as (
        {{
            dbt_utils.deduplicate(
                relation="dibels_benchmark",
                partition_by="academic_year, student_number",
                order_by="client_date desc",
            )
        }}
    ),

    union_year as (
        select
            'Academics' as domain,
            'DIBELS Benchmark' as subdomain,

            academic_year,
            student_number,
            'ELA' as discipline,
            measure_standard_level_int as metric,
            measure_standard_level as metric_string,
        from dibels_dedupe

        union all

        select
            'Academics' as domain,
            'i-Ready Diagnostic' as subdomain,

            academic_year_int as academic_year,
            student_id as student_number,
            discipline,
            overall_relative_placement_int as metric,
            overall_relative_placement as metric_string,
        from {{ ref("base_iready__diagnostic_results") }}
        where rn_subj_year = 1
    ),

    union_quarter as (
        select
            'Attendance' as domain,
            'ADA' as subdomain,

            academic_year,
            term,
            _dbt_source_relation,
            studentid,
            cast(null as string) as discipline,
            round(ada_year_running, 2) as metric,
            null as metric_string,
        from {{ ref("int_powerschool__ada_term") }}

        union all

        select
            'Academics' as domain,
            'Core Course Failures' as subdomain,

            academic_year,
            storecode as term,
            _dbt_source_relation,
            studentid,
            cast(null as string) as discipline,
            n_failing_core as metric,
            null as metric_string,
        from {{ ref("int_powerschool__final_grades_rollup") }}

        union all

        select
            'Academics' as domain,
            'Projected Y1 Credits' as subdomain,

            fg.academic_year,
            fg.storecode as term,
            fg._dbt_source_relation,
            fg.studentid,

            cast(null as string) as discipline,

            coalesce(fg.projected_credits_y1_term, 0)
            + coalesce(gc.earned_credits_cum, 0) as metric,

            null as metric_string,
        from {{ ref("int_powerschool__final_grades_rollup") }} as fg
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on fg.studentid = gc.studentid
            and fg.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="fg", right_alias="gc") }}
    ),

    criteria_test_union as (
        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.iep_status,
            co.region,

            rt.name as term,
            rt.is_current as is_current_term,

            g.domain,
            g.subdomain,
            g.subject as discipline,
            g.goal_direction,
            g.cutoff,
            g.rule_group,
            g.rule_group_grade,

            u.metric,
            u.metric_string,

            case
                when g.goal_direction = '<' and u.metric < g.cutoff
                then true
                when g.goal_direction = '<=' and u.metric <= g.cutoff
                then true
                when g.goal_direction = '>' and u.metric > g.cutoff
                then true
                when g.goal_direction = '>=' and u.metric >= g.cutoff
                then true
                else false
            end as is_met_criteria,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on co.academic_year = rt.academic_year
            and co.schoolid = rt.school_id
            and rt.type = 'RT'
        inner join
            {{ ref("stg_google_sheets__topline_student_goals") }} as g
            on co.academic_year = g.academic_year
            and co.region = g.region
            and co.iep_status = g.iep_status
            and co.grade_level = g.grade_level
            and rt.name = g.term
            and g.goal_type = 'Promo'
        left join
            union_year as u
            on co.academic_year = u.academic_year
            and co.student_number = u.student_number
            and g.subject = u.discipline
            and g.domain = u.domain
            and g.subdomain = u.subdomain
        where co.rn_year = 1 and co.grade_level != 99

        union all

        select
            co.student_number,
            co.academic_year,
            co.grade_level,
            co.iep_status,
            co.region,

            rt.name as term,
            rt.is_current as is_current_term,

            g.domain,
            g.subdomain,
            g.subject as discipline,
            g.goal_direction,
            g.cutoff,
            g.rule_group,
            g.rule_group_grade,

            u.metric,
            cast(u.metric_string as string) as metric_string,

            case
                when g.goal_direction = '<' and u.metric < g.cutoff
                then true
                when g.goal_direction = '<=' and u.metric <= g.cutoff
                then true
                when g.goal_direction = '>' and u.metric > g.cutoff
                then true
                when g.goal_direction = '>=' and u.metric >= g.cutoff
                then true
                else false
            end as is_met_criteria,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on co.academic_year = rt.academic_year
            and co.schoolid = rt.school_id
            and rt.type = 'RT'
        inner join
            {{ ref("stg_google_sheets__topline_student_goals") }} as g
            on co.academic_year = g.academic_year
            and co.region = g.region
            and co.iep_status = g.iep_status
            and co.grade_level = g.grade_level
            and rt.name = g.term
            and g.goal_type = 'Promo'
        left join
            union_quarter as u
            on co.academic_year = u.academic_year
            and co.studentid = u.studentid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="u") }}
            and rt.name = g.term
            and g.subject = u.discipline
            and g.domain = u.domain
            and g.subdomain = u.subdomain
        where co.rn_year = 1 and co.grade_level != 99
    ),

    rule_test as (
        select
            student_number,
            academic_year,
            grade_level,
            iep_status,
            region,
            term,
            is_current_term,
            domain,
            subdomain,
            discipline,
            rule_group,
            rule_group_grade,

            min(is_met_criteria) as is_met,
        from criteria_test_union
        group by
            student_number,
            academic_year,
            grade_level,
            iep_status,
            region,
            term,
            is_current_term,
            domain,
            subdomain,
            discipline,
            rule_group,
            rule_group_grade
    )

select
    student_number,
    academic_year,
    grade_level,
    iep_status,
    region,
    term,
    is_current_term,
    domain,
    subdomain,
    discipline,
    rule_group_grade,

    max(is_met) as is_met,
from rule_test
group by
    student_number,
    academic_year,
    grade_level,
    iep_status,
    region,
    term,
    is_current_term,
    domain,
    subdomain,
    discipline,
    rule_group_grade
