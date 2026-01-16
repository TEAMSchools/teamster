with
    finalsite_report as (
        select
            f.* except (school),

            x.powerschool_school_id as schoolid,
            x.abbreviation as school,

            row_number() over (
                partition by f.academic_year, f.finalsite_student_id,
                order by f.status_start_date desc
            ) as rn,

        -- TODO: replace with real data source once it is ready
        from {{ ref("stg_google_sheets__finalsite__sample_data") }} as f
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on f.school = x.name
    )

select
    * except (
        region, finalsite_student_id, powerschool_student_number, schoolid, school
    ),

    /* since we get snapshot data, these will ensure only the latest of these fields
       is used for a student, retroactively, for a given academic year */
    first_value(region) over (
        partition by academic_year, finalsite_student_id order by status_start_date desc
    ) as region,

    first_value(finalsite_student_id) over (
        partition by academic_year, finalsite_student_id order by status_start_date desc
    ) as finalsite_student_id,

    first_value(powerschool_student_number) over (
        partition by academic_year, finalsite_student_id order by status_start_date desc
    ) as powerschool_student_number,

    first_value(schoolid) over (
        partition by academic_year, finalsite_student_id order by status_start_date desc
    ) as schoolid,

    first_value(school) over (
        partition by academic_year, finalsite_student_id order by status_start_date desc
    ) as school,

from finalsite_report
