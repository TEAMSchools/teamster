select
    f.* except (grade_level, `status`),

    f.grade_level as grade_level_name,

    x.abbreviation as school_abbreviation,
    x.powerschool_school_id as schoolid,

    initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)_')) as region,

    initcap(replace(f.`status`, '_', ' ')) as `status`,

    if(
        f.grade_level = 'Kindergarten', 'K', regexp_extract(f.grade_level, r'\d+')
    ) as grade_level_string,

    if(
        f.grade_level = 'Kindergarten',
        0,
        safe_cast(regexp_extract(f.grade_level, r'^(.*?)\s*(?:st|nd|rd|th)') as int64)
    ) as grade_level,

from {{ ref("stg_finalsite__status_report") }} as f
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as x on f.school = x.name
