with
    student_enrollments as (
        select
            _dbt_source_project,
            schoolid,
            student_number,
            entrydate,
            exitdate,
            academic_year,
        from {{ ref("int_students__student_enrollment_union") }}
    ),

    reporting_terms as (
        select
            `type`,
            code,
            `name`,
            `start_date`,
            end_date,
            region,
            school_id,
            grade_band,
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    ),

    -- Full join: Focus years carry cumulative GPA with no term row.
    gpa_term_cumulative as (
        select
            t.yearid,
            t.term_name,
            t.semester,
            t.gpa_term,
            t.gpa_y1,
            t.gpa_y1_unweighted,
            t.gpa_semester,
            t.n_failing_y1,
            t.total_credit_hours_term,
            t.total_credit_hours_y1,
            t.grade_avg_term,
            t.grade_avg_y1,

            c.cumulative_y1_gpa,
            c.cumulative_y1_gpa_unweighted,
            c.cumulative_y1_gpa_projected,
            c.earned_credits_cum,
            c.potential_credits_cum,

            coalesce(
                t._dbt_source_project, c._dbt_source_project
            ) as _dbt_source_project,
            coalesce(t.schoolid, c.schoolid) as schoolid,
            coalesce(t.academic_year, c.academic_year) as academic_year,
            coalesce(t.student_number, c.student_number) as student_number,
        from {{ ref("int_students__gpa_term") }} as t
        full join
            {{ ref("int_students__gpa_cumulative") }} as c
            on t.student_number = c.student_number
            and t.schoolid = c.schoolid
            and t.academic_year = c.academic_year
            and t._dbt_source_project = c._dbt_source_project
    ),

    gpa_term as (
        select
            *,

            row_number() over (
                partition by _dbt_source_project, student_number, schoolid
                order by
                    academic_year desc,
                    case
                        term_name
                        when 'Q4'
                        then 4
                        when 'Q3'
                        then 3
                        when 'Q2'
                        then 2
                        when 'Q1'
                        then 1
                        else 0
                    end desc
            ) as rn_current,

        from gpa_term_cumulative
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "enr.academic_year",
                "enr.entrydate",
                "gt.term_name",
            ]
        )
    }} as grades_gpa_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "enr.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    enr.academic_year,
    gt.semester,

    gt.gpa_term,
    gt.gpa_y1 as gpa_ytd,
    gt.gpa_y1_unweighted as gpa_ytd_unweighted,
    gt.gpa_semester,
    gt.grade_avg_term,
    gt.grade_avg_y1 as grade_avg_ytd,

    gt.cumulative_y1_gpa as cumulative_gpa,
    gt.cumulative_y1_gpa_unweighted as cumulative_gpa_unweighted,
    gt.cumulative_y1_gpa_projected as cumulative_gpa_projected,

    gt.total_credit_hours_term as credit_hours_term,
    gt.total_credit_hours_y1 as credit_hours_ytd,
    gt.earned_credits_cum as credit_hours_earned_cumulative,
    gt.potential_credits_cum as credit_hours_attempted_cumulative,

    gt.n_failing_y1 as n_failing_ytd,

    if(gt.rn_current = 1, true, false) as is_current,
from gpa_term as gt
inner join
    student_enrollments as enr
    on gt.student_number = enr.student_number
    and gt.schoolid = enr.schoolid
    and gt.academic_year = enr.academic_year
    and gt._dbt_source_project = enr._dbt_source_project
left join
    reporting_terms as rt
    on gt.term_name = rt.`name`
    and gt.schoolid = rt.school_id
    and gt.yearid = rt.powerschool_year_id
