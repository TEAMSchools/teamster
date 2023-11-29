with
    dates as (
        select
            extract(year from date_day) as academic_year,
            extract(year from date_day) + 1 as next_academic_year,

            date(extract(year from date_day), 7, 1) as default_entry_date,
            date((extract(year from date_day) + 1), 6, 30) as default_exit_date,

            date(extract(year from date_day), 9, 1) as denominator_start_date,
            date((extract(year from date_day) + 1), 8, 31) as attrition_date,

            date((extract(year from date_day) + 1), 4, 30) as effective_date,
        from {{ ref("utils__date_spine") }}
        where extract(month from date_day) = 7 and extract(day from date_day) = 1
    ),
    denom as (
        select distinct
            d.academic_year, d.attrition_date, d.effective_date, srh.employee_number,
        from {{ ref("base_people__staff_roster_history") }} as srh
        inner join
            dates as d
            on (
                date(srh.work_assignment__fivetran_start) <= d.denominator_start_date
                and date(srh.work_assignment__fivetran_end) >= d.effective_date
            )
            or (
                date(srh.work_assignment__fivetran_start)
                between d.denominator_start_date and d.effective_date
            )
            or (
                date(srh.work_assignment__fivetran_end)
                between d.denominator_start_date and d.effective_date
            )
        where
            srh.primary_indicator = true
            and srh.assignment_status not in ('Terminated', 'Deceased')
            and srh.job_title != 'Intern'
            and coalesce(srh.assignment_status_reason, 'Missing/no Reason')
            != 'Internship Ended'
    ),
    pm_scores as (
        select
            employee_number,
            academic_year,
            avg(overall_score) as overage_overall_score,
            case
                when avg(overall_score) >= 3.5
                then 4
                when avg(overall_score) >= 2.745
                then 3
                when avg(overall_score) >= 1.745
                then 2
                when avg(overall_score) < 1.75
                then 1
            end as overall_tier,
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where form_type = 'PM' and form_term in ('PM2', 'PM3')
        group by employee_number, academic_year
    ),
    core_attrition_table as (
        select
            dc.academic_year,
            dc.effective_date,
            dc.employee_number,

            case
                when srh.assignment_status in ('Terminated', 'Deceased')
                then coalesce(srh.assignment_status_reason, 'Missing/no Reason')
            end as termination_reason,  -- pulling assignment status reason as of 9/1 of next year
            case
                when srh.assignment_status in ('Terminated', 'Deceased') then 1 else 0
            end as is_attrition,
            sum(
                case
                    when srh.assignment_status not in ('Terminated', 'Deceased')
                    then 1
                    else 0
                end
            ) over (partition by dc.employee_number order by dc.academic_year)
            as year_at_kipp,  -- Counting year as the year a person is in.
            sum(
                case
                    when
                        srh.assignment_status not in ('Terminated', 'Deceased')
                        and srh.job_title in (
                            'Teacher',
                            'Teacher in Residence',
                            'Learning Specialist',
                            'Teacher ESL',
                            'Teacher,ESL',
                            'Teacher in Residence ESL',
                            'Co-Teacher',
                            'Co-Teacher_historical'
                        )
                    then 1
                    else 0
                end
            ) over (partition by dc.employee_number order by dc.academic_year)
            as years_teaching_at_kipp,  -- Counting year as the year a person is in.
        from denom as dc
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on dc.attrition_date
            between date(srh.work_assignment__fivetran_start) and date(
                srh.work_assignment__fivetran_end
            )
            and dc.employee_number = srh.employee_number
    )
select
    cat.academic_year,
    cat.employee_number,
    cat.is_attrition,
    cat.year_at_kipp,
    srh.preferred_name_lastfirst,
    cat.termination_reason as termination_reason,
    srh.business_unit_home_name,
    srh.home_work_location_name,
    srh.home_work_location_abbreviation,
    srh.home_work_location_grade_band,
    srh.department_home_name,
    srh.job_title,
    srh.base_remuneration_annual_rate_amount_amount_value,
    srh.additional_remuneration_rate_amount_value,
    srh.report_to_employee_number,
    srh.gender_identity,
    srh.race_ethnicity_reporting,
    srh.community_grew_up,
    srh.community_professional_exp,
    srh.primary_grade_level_taught,
    srh.level_of_education,
    srh.alumni_status,
    pm.overall_tier,
    coalesce(srh.years_exp_outside_kipp, 0)
    + cat.years_teaching_at_kipp as total_years_teaching,
from core_attrition_table as cat
inner join
    {{ ref("base_people__staff_roster_history") }} as srh
    on cat.effective_date between date(srh.work_assignment__fivetran_start) and date(
        srh.work_assignment__fivetran_end
    )  -- where you worked on 4/30 is the reporting data
    and cat.employee_number = srh.employee_number
left join
    pm_scores as pm
    on cat.employee_number = pm.employee_number
    and cat.academic_year = pm.academic_year