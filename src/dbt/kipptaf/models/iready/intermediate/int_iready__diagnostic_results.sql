with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnj_iready", "int_iready__diagnostic_results"),
                    source("kippmiami_iready", "int_iready__diagnostic_results"),
                ]
            )
        }}
    ),

    sourced as (
        select
            * except (student_id),

            {{
                focus_student_number(
                    "student_id", "academic_year_int", extract_source_project()
                )
            }} as student_id,
        from union_relations
    ),

    transformations as (
        select
            dr.* except (_dbt_source_relation),

            lc.location_region as region,
            lc.location_abbreviation as school_abbreviation,
            lc.location_powerschool_school_id as schoolid,

            regexp_replace(
                dr._dbt_source_relation,
                r'kipp[a-z]+_',
                lc.location_dagster_code_location || '_'
            ) as _dbt_source_relation,

            case
                lc.location_dagster_code_location
                when 'kippnewark'
                then 'NJSLA'
                when 'kippcamden'
                then 'NJSLA'
                when 'kipppaterson'
                then 'NJSLA'
                when 'kippmiami'
                then 'FL'
            end as state_assessment_type,
        from sourced as dr
        left join
            {{ ref("int_people__location_crosswalk") }} as lc
            on dr.school = lc.location_name
    )

select *, {{ extract_source_project() }} as _dbt_source_project,
from transformations
