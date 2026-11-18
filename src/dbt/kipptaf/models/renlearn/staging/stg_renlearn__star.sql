with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_renlearn", "int_renlearn__star"),
                ]
            )
        }}
    ),

    sourced as (
        select
            * except (student_display_id, student_identifier),

            {{
                focus_student_number(
                    "student_display_id",
                    "_dagster_partition_fiscal_year - 1",
                    extract_source_project(),
                )
            }} as student_display_id,
            {{
                focus_student_number(
                    "student_identifier",
                    "_dagster_partition_fiscal_year - 1",
                    extract_source_project(),
                )
            }} as student_identifier,
        from union_relations
    )

select s.*, lc.location_dagster_code_location as _dbt_source_project,
from sourced as s
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on s.school_name = lc.location_name
