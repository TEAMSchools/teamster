with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_finalsite", "stg_finalsite__status_report"),
                    source("kippnewark_finalsite", "stg_finalsite__status_report"),
                ]
            )
        }}
    ),

    region_calc as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *, initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    )

select
    *,

    last_value(region ignore nulls) over (
        partition by enrollment_academic_year, finalsite_student_id
        order by status_start_timestamp asc, status_order asc
        rows between unbounded preceding and unbounded following
    ) as latest_region,

from region_calc
