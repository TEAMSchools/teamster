{%- set ref_contact = ref("base_kippadb__contact") -%}

with
    roster as (
        select
            se.student_number,
            se.studentid,
            se.academic_year as exit_academic_year,
            se.schoolid as exit_schoolid,
            se.school_name as exit_school_name,
            se.grade_level as exit_grade_level,
            se.exitdate as exit_date,
            se.exitcode as exit_code,
            se._dbt_source_relation as exit_db_name,
            se.contact_1_name as powerschool_contact_1_name,
            se.contact_1_email_current as powerschool_contact_1_email_current,
            se.contact_1_phone_primary as powerschool_contact_1_phone_primary,
            se.contact_1_phone_mobile as powerschool_contact_1_phone_mobile,
            se.street as powerschool_street,
            se.city as powerschool_city,
            se.state as powerschool_state,
            se.zip as powerschool_zip,
            se.is_504 as powerschool_is_504,
            se.street
            || ' '
            || se.city
            || ', '
            || se.state
            || ' '
            || se.zip as powerschool_mailing_address,

            (
                ({{ var("current_academic_year") }} - se.academic_year) + se.grade_level
            ) as current_grade_level_projection,

            {{
                dbt_utils.star(
                    from=ref_contact,
                    relation_alias="c",
                    except=[
                        "contact_current_kipp_student",
                        "contact_mailing_address",
                    ],
                )
            }},
            c.contact_mailing_street
            || ' '
            || c.contact_mailing_city
            || ', '
            || c.contact_mailing_state
            || ' '
            || c.contact_mailing_postal_code as contact_mailing_address,
            coalesce(
                c.contact_current_kipp_student, 'Missing from Salesforce'
            ) as contact_current_kipp_student,
            (
                {{ var("current_fiscal_year") }}
                - extract(year from c.contact_actual_hs_graduation_date)
            ) as years_out_of_hs,

            coalesce(c.contact_kipp_hs_class, se.cohort) as ktc_cohort,
            coalesce(c.contact_first_name, se.first_name) as first_name,
            coalesce(c.contact_last_name, se.last_name) as last_name,
            coalesce(
                c.contact_last_name || ', ' || c.contact_first_name, se.lastfirst
            ) as lastfirst,
            if(
                se.enroll_status = 0,
                coalesce(c.contact_email, se.student_email_google),
                c.contact_email
            ) as email,
            case
                when se.enroll_status = 0
                then concat(se.school_level, se.grade_level)
                when c.contact_kipp_hs_graduate
                then 'HSG'
                /* identify HS grads before SF enr update */
                when (se.school_level = 'HS' and se.exitcode = 'G1')
                then 'HSG'
                when
                    (
                        c.contact_kipp_ms_graduate
                        and not c.contact_kipp_hs_graduate
                        and c.record_type_name = 'HS Student'
                    )
                then 'TAFHS'
                when (c.contact_kipp_ms_graduate and not c.contact_kipp_hs_graduate)
                then 'TAF'
            end as ktc_status,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref_contact }} as c on se.student_number = c.contact_school_specific_id
        where se.rn_undergrad = 1 and se.grade_level between 8 and 12
    )

select *,
from roster
where ktc_status is not null
