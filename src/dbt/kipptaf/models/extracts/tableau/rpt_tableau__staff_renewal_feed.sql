with
    approvals as (
        select
            subject_employee_number,
            campaign_academic_year,
            max(
                if(
                    approval_level = 'School Leader/DSO',
                    coalesce(respondent_preferred_name, respondent_email),
                    null
                )
            ) as sl_dso_approval_name,
            max(
                if(
                    approval_level = 'ER',
                    coalesce(respondent_preferred_name, respondent_email),
                    null
                )
            ) as er_approval_name,
            max(
                if(
                    approval_level = 'HOS/MDO',
                    coalesce(respondent_preferred_name, respondent_email),
                    null
                )
            ) as hos_mdo_approval_name,
            max(
                if(approval_level = 'School Leader/DSO', date_submitted, null)
            ) as sl_dso_approval_date,
            max(if(approval_level = 'ER', date_submitted, null)) as er_approval_date,
            max(
                if(approval_level = 'HOS/MDO', date_submitted, null)
            ) as hos_mdo_approval_date,
        from {{ ref("int_surveys__renewal_responses_feed") }}
        where rn_level_approval = 1 and valid_approval = 'Valid Approval'

        group by subject_employee_number, campaign_academic_year, rn_level_approval
    ),

    renewal_roster as (

        select
            b.employee_number as df_employee_number,
            b.legal_given_name as first_name,
            b.legal_family_name as last_name,
            b.given_name as preferred_first,
            b.family_name_1 as preferred_last,
            b.assignment_status as position_status,
            b.worker_original_hire_date as original_hire_date,
            b.worker_rehire_date as rehire_date,
            b.worker_termination_date as termination_date,
            b.worker_type_code as worker_category_description,
            b.wage_law_coverage as benefits_eligibility_class_description,
            b.wage_law_name as flsa_description,
            b.race_ethnicity as eeo_ethnic_description,
            b.mail,
            b.user_principal_name as userprincipalname,

            b.race_ethnicity_reporting,
            b.gender_identity,

            m.employee_number as manager_df_employee_number,
            m.mail as manager_mail,

            s.ay_business_unit,
            s.ay_job_title,
            s.ay_department,
            s.ay_location,
            s.salary_or_hourly,
            s.ay_hourly,
            s.ay_salary,
            s.academic_year,
            s.ay_pm4_overall_score,
            s.ay_pm4_overall_tier,
            s.ay_primary_grade_level_taught,
            s.scale_cy_salary,
            s.scale_ny_salary,
            s.scale_step,
            s.pm_salary_increase,
            s.seat_tracker_id_number,
            s.seat_tracker_last_edited,
            s.ny_status as seat_tracker_status,
            s.ny_entity,
            s.ny_location,
            s.ny_dept,
            s.ny_title,
            s.nonrenewal_reason,
            s.nonrenewal_notes,
            s.ny_salary,
            s.ny_hourly,
            s.salary_rule,
            s.ay_school_shortname,
            s.ny_school_shortname,
            s.ay_campus_name,
            s.ny_campus_name,
            s.ay_head_of_school_samaccount,
            s.ny_head_of_school_samaccount,

            rf.salary as ny_salary_from_form,
            rf.salary_modification_explanation,
            rf.renewal_decision as renewal_decision_from_form,
            rf.dept_and_job as dept_and_job_from_form,
            rf.add_comp_amt_1,
            rf.add_comp_amt_2,
            rf.add_comp_amt_3,
            rf.add_comp_amt_4,
            rf.add_comp_amt_5,
            rf.add_comp_name_1,
            rf.add_comp_name_2,
            rf.add_comp_name_3,
            rf.add_comp_name_4,
            rf.add_comp_name_5,
            rf.concated_add_comp,

            ap.sl_dso_approval_name,
            ap.er_approval_name,
            ap.hos_mdo_approval_name,
            ap.sl_dso_approval_date,
            ap.er_approval_date,
            ap.hos_mdo_approval_date,

            rlm.renewal_doc,

            concat(b.family_name_1, ', ', b.given_name) as preferred_name,
            concat(m.family_name_1, ', ', m.given_name) as manager_name,

            case
                when s.seat_tracker_id_number is null
                then
                    concat(
                        'No Seat (',
                        coalesce(s.nonrenewal_reason, 'No Reason Given'),
                        ')'
                    )
                when
                    (
                        count(s.seat_tracker_id_number) over (
                            partition by s.employee_number, s.academic_year
                        )
                    )
                    > 1
                then 'Is in multiple seats. Please update Seat Tracker❗'
                when
                    s.seat_tracker_id_number is not null
                    and s.ay_business_unit != s.ny_entity
                then 'Entity Changer - New Offer Letter'
                when
                    s.seat_tracker_id_number is not null
                    and s.ay_location != s.ny_location
                then 'Renew - Location Change'
                when s.seat_tracker_id_number is not null
                then 'Renew'
                else 'Seat Tracker Error'
            end as ny_status,
            if(
                s.salary_rule = 'Annual Adjustment' and s.salary_or_hourly = 'Hourly',
                s.ny_hourly,
                s.ny_salary
            ) as ny_rate,

        from {{ ref("int_people__staff_roster") }} as b
        left join
            {{ ref("int_people__staff_roster") }} as m
            on b.reports_to_employee_number = m.employee_number
        left join
            {{ ref("int_people__renewal_status") }} as s
            on b.employee_number = s.employee_number
            and s.academic_year = {{ var("current_academic_year") }}
        left join
            {{ ref("int_surveys__renewal_responses_feed") }} as rf
            on s.academic_year = rf.campaign_academic_year
            and b.employee_number = rf.subject_employee_number
            and rf.rn_approval = 1
        left join
            approvals as ap
            on s.academic_year = ap.campaign_academic_year
            and b.employee_number = ap.subject_employee_number
        left join
            {{ ref("stg_people__renewal_letter_mapping") }} as rlm
            on rlm.entity = s.ny_entity
            and rlm.department = s.ny_dept
            and rlm.jobs = s.ny_title
    )

select
    *,
    case
        when
            ny_status in (
                'Is in multiple seats. Please update Seat Tracker❗',
                'Seat Tracker Error',
                'No Seat (Transfer)',
                'No Seat (Renew)',
                'No Seat (Model Issue)',
                'No Seat (No Reason Given)'
            )
        then 'https://www.appsheet.com/start/da7c51f8-1985-4c8d-b786-2aaf816ae1d2'
        else
            concat(
                'https://docs.google.com/forms/d/e/',
                '1FAIpQLSc5df2oBp3aM5QbBWn80WwNUsFzyubt-lCZWmRB-tV76beMSQ/',
                'viewform?entry.1301005781=',
                preferred_name,
                ' - ',
                ay_location,
                ' (',
                safe_cast(df_employee_number as string),
                ')&entry.1650580574=',
                ny_status,
                '&entry.678233722=',
                coalesce(
                    concat(
                        ny_entity, ' - ', ny_location, ' - ', ny_dept, ' ', ny_title
                    ),
                    ''
                ),
                '&entry.1584291699=',
                coalesce(ny_dept, ''),
                ' ',
                coalesce(ny_title, ''),
                '&entry.1125263358=',
                coalesce(
                    if(
                        ay_job_title = ny_title,
                        salary_rule,
                        'Changing Job - Please Look up New Salary'
                    ),
                    ''
                ),
                '&entry.1309133590=',
                coalesce(
                    safe_cast(
                        round(safe_cast(ny_salary_from_form as numeric), 2) as string
                    ),
                    safe_cast(round(safe_cast(ny_rate as numeric), 2) as string),
                    ''
                ),
                '&entry.1059490956=',
                coalesce(replace(salary_modification_explanation, '%', ' percent'), ''),
                '&entry.1601656476=',
                coalesce(add_comp_name_1, ''),
                '&entry.298530295=',
                coalesce(safe_cast(add_comp_amt_1 as string), ''),
                '&entry.1377346020=',
                coalesce(add_comp_name_2, ''),
                '&entry.628899757=',
                coalesce(safe_cast(add_comp_amt_2 as string), ''),
                '&entry.450465171=',
                coalesce(add_comp_name_3, ''),
                '&entry.1812123774=',
                coalesce(safe_cast(add_comp_amt_3 as string), ''),
                '&entry.776627414=',
                coalesce(add_comp_name_4, ''),
                '&entry.624511155=',
                coalesce(safe_cast(add_comp_amt_4 as string), ''),
                '&entry.292647207=',
                coalesce(add_comp_name_5, ''),
                '&entry.830314050=',
                coalesce(safe_cast(add_comp_amt_5 as string), '')
            )

    end as form_link,

from renewal_roster
