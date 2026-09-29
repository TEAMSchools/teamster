with
    student_enrollments as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            student_number,
            academic_year,
            entrydate,
            exitdate,
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
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["fg.cc_dcid", "fg._dbt_source_project", "fg.storecode"]
        )
    }} as grades_term_key,

    {{ dbt_utils.generate_surrogate_key(["fg.cc_dcid", "fg._dbt_source_project"]) }}
    as student_section_enrollment_key,

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

    fg.termbin_start_date as term_start_date_key,
    fg.termbin_end_date as term_end_date_key,

    fg.academic_year,

    fg.term_percent_grade as percent_grade,
    fg.term_letter_grade as letter_grade,
    fg.term_percent_grade_adjusted as percent_grade_adjusted,
    fg.term_letter_grade_adjusted as letter_grade_adjusted,
    fg.citizenship as citizenship_grade,

    fg.y1_percent_grade as ytd_percent_grade,
    fg.y1_percent_grade_adjusted as ytd_percent_grade_adjusted,
    fg.y1_letter_grade as ytd_letter_grade,
    fg.y1_letter_grade_adjusted as ytd_letter_grade_adjusted,

    fg.term_grade_points as grade_points_earned,
    fg.y1_grade_points as ytd_grade_points,

    fg.potential_credit_hours,

    fg.lastgradeupdate as last_grade_update_date,

    cast(fg.exclude_from_gpa as bool) as is_excluded_from_gpa,
from {{ ref("int_students__final_grades") }} as fg
-- Retained as a row-population filter: a term grade must fall within a covering
-- school enrollment. Enrollment linkage now flows through
-- `student_section_enrollment_key` to `dim_student_section_enrollments`, joined
-- on `student_number` rather than `studentid`. The Focus branch has no
-- PowerSchool `studentid`, and `student_number` is the only student key both
-- branches carry. Measured against prod before the swap: row-identical to the
-- `studentid` join for all 3 NJ regions.
inner join
    student_enrollments as enr
    on fg.student_number = enr.student_number
    and fg.academic_year = enr.academic_year
    and fg.termbin_start_date >= enr.entrydate
    and fg.termbin_start_date < enr.exitdate
    and fg._dbt_source_project = enr._dbt_source_project
inner join
    {{ ref("dim_regions") }} as dr on fg._dbt_source_project = dr.dagster_code_location
left join
    reporting_terms as rt
    on fg.storecode = rt.name
    and fg.schoolid = rt.school_id
    and dr.`name` = rt.region
    and fg.yearid = rt.powerschool_year_id
