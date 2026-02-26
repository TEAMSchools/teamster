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
            * except (first_name),

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
            initcap(first_name) as first_name,

            if(
                application_grade in ('K', 'Kindergarten'),
                0,
                cast(regexp_extract(application_grade, r'\d+') as int)
            ) as grade_level,

            cast(active_school_year_int as string)
            || '-'
            || right(
                cast(active_school_year_int + 1 as string), 2
            ) as active_school_year_display,

        from union_relations
    )

select
    l.*,

    {{ var("current_academic_year") }} as current_academic_year,
    {{ var("current_academic_year") }} + 1 as next_academic_year,

from region_calc as l
left join
    {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as e
    on l.finalsite_enrollment_id = e.finalsite_student_id
where e.finalsite_student_id is null
