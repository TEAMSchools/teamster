with
    scaffold as (
        select
            srh.employee_number,

            t.type,
            t.code,
            t.`name`,
            t.academic_year,
            t.start_date,
            t.end_date,
            t.region,
            t.school_id,
            t.is_current,

            srh.job_title,

            row_number() over (
                partition by
                    srh.employee_number,
                    t.type,
                    t.code,
                    t.`name`,
                    t.start_date,
                    t.region,
                    t.school_id
                order by srh.effective_date_start desc
            ) as rn,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on srh.home_business_unit_name = t.region
            and (
                t.start_date
                between srh.work_assignment_actual_start_date and srh.effective_date_end
                or t.end_date
                between srh.work_assignment_actual_start_date and srh.effective_date_end
            )
            and t.type in ('PMS', 'PMC', 'TR', 'WT', 'O3')
        where
            srh.primary_indicator
            and srh.assignment_status = 'Active'
            and (srh.job_title like '%Teacher%' or srh.job_title like '%Learning%')
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "employee_number",
                "type",
                "code",
                "name",
                "start_date",
                "region",
                "school_id",
            ]
        )
    }} as staff_observation_expectation_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "type",
                "code",
                "name",
                "start_date",
                "region",
                "school_id",
            ]
        )
    }} as term_key,

    academic_year,
    is_current,

    job_title as position_title,
from scaffold
where rn = 1
