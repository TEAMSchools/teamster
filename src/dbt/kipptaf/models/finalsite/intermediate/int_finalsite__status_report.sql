with
    transformations as (
        select
            f.* except (enrollment_type, enrollment_year, grade_level, `status`),

            f.grade_level as grade_level_name,

            x.abbreviation as school_abbreviation,
            x.powerschool_school_id as schoolid,

            initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)_')) as region,

            initcap(replace(f.`status`, '_', ' ')) as detailed_status,

            cast(f.academic_year as string)
            || '-'
            || right(cast(f.academic_year + 1 as string), 2) as academic_year_display,

            if(
                f.grade_level = 'Kindergarten',
                'K',
                regexp_extract(f.grade_level, r'\d+')
            ) as grade_level_string,

            if(
                f.grade_level = 'Kindergarten',
                0,
                safe_cast(regexp_extract(f.grade_level, r'\d+') as int64)
            ) as grade_level,

        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    )

select
    *,

    concat(first_name, last_name) as name_join,

    concat(first_name, last_name, grade_level) as name_grade_level_join,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "academic_year",
                "last_name",
                "first_name",
                "grade_level",
                "school",
                "powerschool_student_number",
            ]
        )
    }} as surrogate_key,

from transformations
