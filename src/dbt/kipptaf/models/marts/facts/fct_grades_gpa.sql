with
    student_enrollments as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            student_number,
            entrydate,
            exitdate,
            academic_year,
            rn_year,
        from {{ ref("base_powerschool__student_enrollments") }}
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
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'quarter'
    ),

    gpa_term as (
        select
            gt._dbt_source_relation,
            gt.studentid,
            gt.schoolid,
            gt.yearid,
            gt.term_name,
            gt.semester,
            gt.is_current,
            gt.gpa_term,
            gt.gpa_y1,
            gt.gpa_y1_unweighted,
            gt.gpa_semester,
            gt.n_failing_y1,
            gt.total_credit_hours_term,
            gt.total_credit_hours_y1,
            gt.grade_avg_term,
            gt.grade_avg_y1,

            gc.cumulative_y1_gpa,
            gc.cumulative_y1_gpa_unweighted,
            gc.cumulative_y1_gpa_projected,
            gc.earned_credits_cum,
            gc.potential_credits_cum,

            initcap(regexp_extract(gt._dbt_source_relation, r'kipp(\w+)_')) as region,

            row_number() over (
                partition by gt._dbt_source_relation, gt.studentid, gt.schoolid
                order by
                    gt.yearid desc,
                    case
                        gt.term_name
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
        from {{ ref("int_powerschool__gpa_term") }} as gt
        left join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on gt.studentid = gc.studentid
            and gt.schoolid = gc.schoolid
            and {{ union_dataset_join_clause(left_alias="gt", right_alias="gc") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "gt.studentid",
                "gt._dbt_source_relation",
                "gt.yearid",
                "gt.term_name",
            ]
        )
    }} as grades_gpa_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "enr.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,

    enr.student_number,
    enr.academic_year,
    gt.term_name,
    gt.semester,

    gt.gpa_term,
    gt.gpa_y1,
    gt.gpa_y1_unweighted,
    gt.gpa_semester,
    gt.grade_avg_term,
    gt.grade_avg_y1,

    gt.cumulative_y1_gpa,
    gt.cumulative_y1_gpa_unweighted,
    gt.cumulative_y1_gpa_projected,

    gt.total_credit_hours_term as credit_hours_term,
    gt.total_credit_hours_y1 as credit_hours_y1,
    gt.earned_credits_cum as credit_hours_earned_cumulative,
    gt.potential_credits_cum as credit_hours_attempted_cumulative,

    gt.n_failing_y1,

    gt.is_current as is_current_term,

    if(gt.rn_current = 1, true, false) as is_current_row,
from gpa_term as gt
inner join
    student_enrollments as enr
    on gt.studentid = enr.studentid
    and gt.yearid = enr.yearid
    and {{ union_dataset_join_clause(left_alias="gt", right_alias="enr") }}
    and enr.rn_year = 1
left join
    reporting_terms as rt
    on gt.term_name = rt.code
    and gt.schoolid = rt.school_id
    and gt.region = rt.region
    and gt.yearid = rt.powerschool_year_id - 1990
