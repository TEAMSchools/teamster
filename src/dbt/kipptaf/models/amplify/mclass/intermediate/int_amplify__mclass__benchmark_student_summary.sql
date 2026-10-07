with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_amplify__mclass__sftp__benchmark_student_summary"),
                    ref("stg_amplify__mclass__api__benchmark_student_summary"),
                ],
                source_column_name="_dbt_source_relation_2",
            )
        }}
    ),

    location_xref as (
        select
            ur.*,

            x.location_abbreviation as school,
            x.location_powerschool_school_id as schoolid,
            x.location_dagster_code_location as _dbt_source_project,

            initcap(
                regexp_extract(x.location_dagster_code_location, r'kipp(\w+)')
            ) as region,
        from union_relations as ur
        left join
            {{ ref("int_people__location_crosswalk") }} as x
            on ur.school_name = x.location_name
    )

select
    * except (student_primary_id),

    {{
        focus_student_number(
            "student_primary_id", "academic_year", "_dbt_source_project"
        )
    }} as student_primary_id,

from location_xref
