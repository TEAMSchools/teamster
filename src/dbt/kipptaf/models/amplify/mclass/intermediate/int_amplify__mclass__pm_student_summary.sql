with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__pm_student_summary"),
                    ref("stg_amplify__mclass__api__pm_student_summary"),
                ],
                source_column_name="_dbt_source_relation_2",
            )
        }}
    ),

    location_xref as (
        select
            ur.* except (school_primary_id),

            x.location_abbreviation as school,
            x.location_dagster_code_location as _dbt_source_project,

            -- string on both sides: Amplify ids can carry letters (2332A), and
            -- the district copy is still int64 until it rebuilds
            cast(ur.school_primary_id as string) as school_primary_id,
            cast(x.location_powerschool_school_id as string) as schoolid,

            initcap(
                regexp_extract(x.location_dagster_code_location, r'kipp(\w+)')
            ) as region,

            count(*) over (
                partition by
                    ur._dbt_source_relation,
                    ur._dbt_source_relation_2,
                    ur.student_primary_id_studentnumber,
                    ur.school_year,
                    ur.pm_period,
                    ur.measure,
                    ur.probe_number,
                    ur.device_date,
                    ur.assessment_grade
            ) as n_key_collisions,
        from union_relations as ur
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on ur.school_name = x.location_name
    )

select
    * except (
        schoolid,
        school_primary_id,
        primary_school_id,
        student_primary_id_studentnumber,
        n_key_collisions
    ),

    coalesce(schoolid, school_primary_id) as school_primary_id,

    {{
        focus_student_number(
            "student_primary_id_studentnumber", "academic_year", "_dbt_source_project"
        )
    }} as student_primary_id,

    if(pm_period = 'BOY->MOY', 'MOY', 'EOY') as matching_season,

from location_xref
where n_key_collisions = 1
