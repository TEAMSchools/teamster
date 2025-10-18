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
    )

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

    u.metric,
    u.metric_string,
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
