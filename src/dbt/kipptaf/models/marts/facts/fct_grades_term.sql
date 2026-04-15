with
    student_enrollments as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            student_number,
            entrydate,
            exitdate,
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
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["fg.cc_dcid", "fg._dbt_source_relation", "fg.storecode"]
        )
    }} as grades_term_key,

    {{ dbt_utils.generate_surrogate_key(["fg.cc_dcid", "fg._dbt_source_relation"]) }}
    as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "fg.academic_year",
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

    fg.termbin_start_date as term_start_date_key,
    fg.termbin_end_date as term_end_date_key,

    enr.student_number,
    fg.academic_year,
    fg.storecode as term_code,

    fg.term_percent_grade as percent_grade,
    fg.term_letter_grade as letter_grade,
    fg.term_percent_grade_adjusted as percent_grade_adjusted,
    fg.term_letter_grade_adjusted as letter_grade_adjusted,
    fg.citizenship,

    fg.y1_percent_grade,
    fg.y1_percent_grade_adjusted,
    fg.y1_letter_grade,
    fg.y1_letter_grade_adjusted,

    fg.term_grade_points as grade_points,
    fg.y1_grade_points,

    fg.potential_credit_hours,
    fg.exclude_from_gpa,

    fg.lastgradeupdate as last_grade_update_date,
from {{ ref("base_powerschool__final_grades") }} as fg
inner join
    student_enrollments as enr
    on fg.studentid = enr.studentid
    and fg.yearid = enr.yearid
    and fg.termbin_start_date >= enr.entrydate
    and fg.termbin_start_date < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="fg", right_alias="enr") }}
left join
    reporting_terms as rt
    on fg.storecode = rt.code
    and fg.schoolid = rt.school_id
    and initcap(regexp_extract(fg._dbt_source_relation, r'kipp(\w+)_')) = rt.region
    and fg.yearid = rt.powerschool_year_id - 1990
