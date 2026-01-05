with
    transformations as (
        select
            f.* except (enrollment_type),

            x.abbreviation as school_abbreviation,
            x.powerschool_school_id as schoolid,

            initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)_')) as region,

            initcap(replace(f.`status`, '_', ' ')) as detailed_status,

            cast(f.academic_year as string)
            || '-'
            || right(cast(f.academic_year + 1 as string), 2) as academic_year_display,

        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    )

select
    *,

    concat(first_name, last_name) as name_join,

    concat(first_name, last_name, grade_level) as name_grade_level_join,

from transformations
