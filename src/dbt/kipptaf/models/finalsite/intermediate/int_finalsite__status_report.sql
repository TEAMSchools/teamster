with
    finalsite_report as (
        select
            f.* except (school),

            x.powerschool_school_id as schoolid,
            x.abbreviation as school,

            initcap(regexp_extract(f._dbt_source_relation, r'kipp(\w+)_')) as region,

        from {{ ref("stg_finalsite__status_report") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    )

select
    * except (powerschool_student_number),

    'KTAF' as org,

    /* since we get snapshot data, these will ensure only the latest of these fields is
    used for a student, retroactively, for a given enroll academic year */
    coalesce(
        first_value(schoolid) over (
            partition by enrollment_academic_year, finalsite_student_id
            order by status_start_date desc
        ),
        0
    ) as latest_schoolid,

    coalesce(
        first_value(school) over (
            partition by enrollment_academic_year, finalsite_student_id
            order by status_start_date desc
        ),
        'No School Assigned'
    ) as latest_school,

    first_value(region) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as latest_region,

    first_value(powerschool_student_number) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_date desc
    ) as powerschool_student_number,

    date(enrollment_academic_year - 1, 10, 16) as sre_academic_year_start,
    date(enrollment_academic_year, 06, 30) as sre_academic_year_end,

from finalsite_report
