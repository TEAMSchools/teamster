with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippcamden_finalsite", "stg_finalsite__status_report"),
                    source("kippmiami_finalsite", "stg_finalsite__status_report"),
                    source("kippnewark_finalsite", "stg_finalsite__status_report"),
                    source("kipppaterson_finalsite", "stg_finalsite__status_report"),
                ]
            )
        }}
    ),

    region_calc as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            * except (extract_year, first_name, sre_academic_year),

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            initcap(first_name) as first_name,

            coalesce(extract_year, 'Next_Year') as extract_year,

        from union_relations
    ),

    latest_region_grade as (
        select
            *,

            last_value(region ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_timestamp asc, status_order asc
                rows between unbounded preceding and unbounded following
            ) as latest_region,

            last_value(grade_level ignore nulls) over (
                partition by enrollment_academic_year, finalsite_student_id
                order by status_start_timestamp asc, status_order asc
                rows between unbounded preceding and unbounded following
            ) as latest_grade_level,

            last_value(finalsite_student_id ignore nulls) over (
                partition by enrollment_academic_year, latest_powerschool_student_number
                order by status_start_timestamp asc, status_order asc
                rows between unbounded preceding and unbounded following
            ) as latest_finalsite_student_id,

        from region_calc
    )

select l.*,
from latest_region_grade as l
left join
    {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as e
    on l.finalsite_student_id = e.finalsite_student_id
where e.finalsite_student_id is null
