with
    date_spine as (
        select last_day(date_quarter, month) as quarter_end_date,
        from
            unnest(
                generate_date_array(
                    '2022-07-31',  -- Start date (first day of a month)
                    date_add(
                        current_date('{{ var("local_timezone") }}'), interval 100 year
                    ),  -- Far-future cutoff
                    interval 3 month  -- Quarterly interval
                )
            ) as date_quarter
    ),

    latest_sr as (
        select *,
        from
            (
                select
                    sr.*,
                    ds.quarter_end_date,
                    row_number() over (
                        partition by ds.quarter_end_date, sr.employee_number
                        order by sr.effective_date_start desc
                    ) as rn,
                from {{ ref("int_people__staff_roster_history") }} as sr
                left join
                    date_spine as ds
                    on ds.quarter_end_date between sr.effective_date_start and date(
                        {{ var("current_fiscal_year") }}, 07, 30
                    )
            )
    )

select
    sr.quarter_end_date as report_date,
    sr.job_title,
    sr.home_work_location_name,
    sr.assignment_status,
    sr.legal_given_name,
    sr.legal_family_name,
    sr.position_id,
    sr.home_business_unit_name,
    sr.employee_number,
    sr.worker_original_hire_date,
    sr.wage_law_coverage as payclass,
    sr.legal_address_line_one,
    sr.legal_address_city_name,
    sr.legal_address_country_subdivision_level_1_code,
    sr.legal_address_postal_code,
    sr.base_remuneration_annual_rate_amount,
    sr.worker_termination_date,
    sr.level_of_education,
    null as custom_miami_aces_number,
    sr.birth_date,
    '2x Month' as pay_frequency,
    '' as duty_days,
    'N/A' as teacher_eval,
    'N/A' as contribution504b,
    'B' as basiclifeplan,
from latest_sr as sr
where
    sr.home_business_unit_name = 'KIPP Miami'
    and sr.rn = 1
    and (
        sr.worker_termination_date > date({{ var("current_academic_year") }}, 07, 01)
        or sr.worker_termination_date is null
    )
