with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__pm_student_summary"),
                    source("amplify", "stg_amplify__mclass__api__pm_student_summary"),
                ],
                source_column_name="_dbt_source_relation_2",
            )
        }}
    ),

    location_xref as (
        select
            ur.*,

            x.abbreviation as school,
            x.powerschool_school_id as schoolid,

            initcap(regexp_extract(x.dagster_code_location, r'kipp(\w+)')) as region,
        from union_relations as ur
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on ur.school_name = x.name
    )

select
    * except (
        enrollment_teacher_staff_id_teachernumber,
        official_teacher_staff_id,
        enrollment_teacher_name,
        official_teacher_name,
        device_date,
        client_date,
        account_name,
        district_name,
        schoolid,
        school_primary_id,
        student_primary_id,
        student_primary_id_studentnumber,
        student_id_state_id,
        secondary_student_id_stateid,
        primary_school_id
    ),

    coalesce(
        enrollment_teacher_staff_id_teachernumber, official_teacher_staff_id
    ) as official_teacher_staff_id,
    coalesce(enrollment_teacher_name, official_teacher_name) as official_teacher_name,
    coalesce(device_date, client_date) as client_date,
    coalesce(account_name, district_name) as district_name,
    coalesce(schoolid, school_primary_id) as school_primary_id,
    coalesce(
        student_primary_id, student_primary_id_studentnumber
    ) as student_primary_id,
    coalesce(student_id_state_id, secondary_student_id_stateid) as student_id_state_id,

from location_xref
