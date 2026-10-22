with
    final_grades as (
        select
            *,

            {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
            as student_section_enrollment_key,
        from {{ ref("int_students__final_grades") }}
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

    fg.student_section_enrollment_key,

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
from final_grades as fg
inner join
    {{ ref("dim_student_section_enrollments") }} as sse
    on fg.student_section_enrollment_key = sse.student_section_enrollment_key
inner join
    {{ ref("dim_regions") }} as dr on fg._dbt_source_project = dr.dagster_code_location
left join
    reporting_terms as rt
    on fg.storecode = rt.name
    and fg.schoolid = rt.school_id
    and dr.`name` = rt.region
    and fg.yearid = rt.powerschool_year_id
where sse.student_enrollment_key is not null
