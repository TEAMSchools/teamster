with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    responses as (
        select
            employee_number,
            academic_year,
            survey_code,
            survey_response_id,
            date_submitted,
        from {{ ref("rpt_tableau__survey_responses") }}
        where round_rn = 1
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="responses",
                partition_by="employee_number, academic_year, survey_code",
                order_by="date_submitted desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/ST06): contract column order is mandated
select
    sl.employee_number,
    sl.assignment_status,
    sl.preferred_name_lastfirst,
    sl.hire_date,
    sl.survey,
    sl.academic_year,
    sl.survey_round,
    sl.is_current,

    lc.location_clean_name,
    lc.campus_name,

    case
        sr2.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else sr2.home_business_unit_name
    end as home_business_unit_name,
    sr2.home_department_name,
    sr2.job_function,
    sr2.job_title,

    sr2.mail,
    sr2.user_principal_name,
    sr2.sam_account_name,

    sr2.reports_to_mail,
    sr2.reports_to_sam_account_name,

    sr.survey_response_id,

    if(sr.survey_response_id is not null, 1, 0) as completion,
from {{ ref("rpt_tableau__survey_links") }} as sl
left join
    {{ ref("int_people__staff_roster") }} as sr2
    on sl.employee_number = sr2.employee_number
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr2.home_work_location_name = lc.location_name
left join
    deduplicate as sr
    on sl.employee_number = sr.employee_number
    and sl.academic_year = sr.academic_year
    and sl.survey_round = sr.survey_code
where sl.survey not in ('TNTP Insight Survey', 'Gallup Q12 Survey')
