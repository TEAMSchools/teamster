with
    es_grad as (
        select
            co._dbt_source_relation,
            co.student_number,

            s.abbreviation as entry_school,

            max(
                if(
                    co.grade_level = 4
                    and co.exitdate >= date(co.academic_year + 1, 6, 1),
                    true,
                    false
                )
            ) as is_es_grad,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_powerschool__schools") }} as s
            on co.entry_schoolid = s.school_number
            and {{ union_dataset_join_clause(left_alias="co", right_alias="s") }}
        where co.rn_year = 1
        group by co._dbt_source_relation, co.student_number, s.abbreviation
    ),

    dlm as (
        select _dbt_source_relation, student_number, max(pathway_option) as dlm,
        from {{ ref("int_students__graduation_path_codes") }}
        where rn_discipline_distinct = 1 and final_grad_path_code = 'M'
        group by _dbt_source_relation, student_number
    ),

    tier as (
        select
            contact,
            `subject` as tier,

            row_number() over (
                partition by contact order by `date` desc
            ) as rn_tier_recent,
        from {{ ref("stg_kippadb__contact_note") }}
        where regexp_contains(`subject`, r'Tier\s\d$')
    ),

    roster as (
        select
            se._dbt_source_relation as exit_db_name,
            se.student_number,
            se.studentid,
            se.state_studentnumber,
            se.dob,
            se.enroll_status as powerschool_enroll_status,
            se.street as powerschool_street,
            se.city as powerschool_city,
            se.state as powerschool_state,
            se.zip as powerschool_zip,
            se.academic_year as exit_academic_year,
            se.region,
            se.schoolid as exit_schoolid,
            se.school_name as exit_school_name,
            se.grade_level as exit_grade_level,
            se.exitdate as exit_date,
            se.exitcode as exit_code,
            se.is_504 as powerschool_is_504,
            se.lep_status,
            se.es_graduated,

            se.contact_1_email_current as powerschool_contact_1_email_current,
            se.contact_1_name as powerschool_contact_1_name,
            se.contact_1_phone_daytime as powerschool_contact_1_phone_daytime,
            se.contact_1_phone_home as powerschool_contact_1_phone_home,
            se.contact_1_phone_mobile as powerschool_contact_1_phone_mobile,
            se.contact_1_phone_primary as powerschool_contact_1_phone_primary,
            se.contact_1_phone_work as powerschool_contact_1_phone_work,
            se.contact_1_relationship as powerschool_contact_1_relationship,
            se.contact_2_email_current as powerschool_contact_2_email_current,
            se.contact_2_name as powerschool_contact_2_name,
            se.contact_2_phone_daytime as powerschool_contact_2_phone_daytime,
            se.contact_2_phone_home as powerschool_contact_2_phone_home,
            se.contact_2_phone_mobile as powerschool_contact_2_phone_mobile,
            se.contact_2_phone_primary as powerschool_contact_2_phone_primary,
            se.contact_2_phone_work as powerschool_contact_2_phone_work,
            se.contact_2_relationship as powerschool_contact_2_relationship,
            se.emergency_1_name as powerschool_emergency_contact_1_name,
            se.emergency_1_phone_daytime
            as powerschool_emergency_contact_1_phone_daytime,
            se.emergency_1_phone_home as powerschool_emergency_contact_1_phone_home,
            se.emergency_1_phone_mobile as powerschool_emergency_contact_1_phone_mobile,
            se.emergency_1_phone_primary
            as powerschool_emergency_contact_1_phone_primary,
            se.emergency_1_relationship as powerschool_emergency_contact_1_relationship,
            se.emergency_2_name as powerschool_emergency_contact_2_name,
            se.emergency_2_phone_daytime
            as powerschool_emergency_contact_2_phone_daytime,
            se.emergency_2_phone_home as powerschool_emergency_contact_2_phone_home,
            se.emergency_2_phone_mobile as powerschool_emergency_contact_2_phone_mobile,
            se.emergency_2_phone_primary
            as powerschool_emergency_contact_2_phone_primary,
            se.emergency_2_relationship as powerschool_emergency_contact_2_relationship,
            se.emergency_3_name as powerschool_emergency_contact_3_name,
            se.emergency_3_phone_daytime
            as powerschool_emergency_contact_3_phone_daytime,
            se.emergency_3_phone_home as powerschool_emergency_contact_3_phone_home,
            se.emergency_3_phone_mobile as powerschool_emergency_contact_3_phone_mobile,
            se.emergency_3_phone_primary
            as powerschool_emergency_contact_3_phone_primary,
            se.emergency_3_relationship as powerschool_emergency_contact_3_relationship,

            c.* except (contact_current_kipp_student, contact_lastfirst),

            os.id as overgrad_students_id,
            os.graduation_year as overgrad_students_graduation_year,
            os.school__name as overgrad_students_school,
            os.is_ed_ea,
            os.best_guess_pathway,
            os.desired_pathway,
            os.personal_statement_status,
            os.supplemental_essay_status,
            os.recommendation_1_status,
            os.recommendation_2_status,
            os.created_fsa_id_student,
            os.created_fsa_id_parent,
            os.common_app_linked,
            os.wishlist_signed_off_by_counselor,
            os.wishlist_notes,

            e.entry_school,
            e.is_es_grad,

            t.tier,

            concat(
                os.assigned_counselor__last_name,
                ', ',
                os.assigned_counselor__first_name
            ) as overgrad_students_assigned_counselor_lastfirst,

            concat(
                se.street, ' ', se.city, ', ', se.state, ' ', se.zip
            ) as powerschool_mailing_address,

            coalesce(
                c.contact_current_kipp_student, 'Missing from Salesforce'
            ) as contact_current_kipp_student,

            coalesce(c.contact_kipp_hs_class, se.cohort) as ktc_cohort,
            coalesce(c.contact_first_name, se.student_first_name) as first_name,
            coalesce(c.contact_last_name, se.student_last_name) as last_name,
            coalesce(c.contact_lastfirst, se.student_name) as lastfirst,

            if(
                se.enroll_status = 0,
                coalesce(c.contact_email, se.student_email),
                c.contact_email
            ) as email,

            if(d.dlm is not null, true, false) as is_dlm,

            case
                when se.enroll_status = 0
                then concat(se.school_level, se.grade_level)
                when c.contact_kipp_hs_graduate
                then 'HSG'
                /* identify HS grads before SF enr update */
                when se.school_level = 'HS' and se.exitcode = 'G1'
                then 'HSG'
                when
                    c.contact_kipp_ms_graduate
                    and not c.contact_kipp_hs_graduate
                    and c.record_type_name = 'HS Student'
                then 'TAFHS'
                when c.contact_kipp_ms_graduate and not c.contact_kipp_hs_graduate
                then 'TAF'
            end as ktc_status,

            case
                when contact_college_match_display_gpa >= 3.50
                then '3.50+'
                when contact_college_match_display_gpa >= 3.00
                then '3.00-3.49'
                when contact_college_match_display_gpa >= 2.50
                then '2.50-2.99'
                when contact_college_match_display_gpa >= 2.00
                then '2.00-2.50'
                when contact_college_match_display_gpa < 2.00
                then '<2.00'
            end as hs_gpa_bands,

            (
                {{ var("current_academic_year") }} - se.academic_year + se.grade_level
            ) as current_grade_level_projection,
        from {{ ref("int_extracts__student_enrollments") }} as se
        left join
            {{ ref("base_kippadb__contact") }} as c
            on se.student_number = c.contact_school_specific_id
        left join
            {{ ref("int_overgrad__students") }} as os
            on se.salesforce_id = os.external_student_id
            and {{ union_dataset_join_clause(left_alias="se", right_alias="os") }}
        left join
            es_grad as e
            on se.student_number = e.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="e") }}
        left join
            dlm as d
            on se.student_number = d.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="d") }}
        left join tier as t on se.salesforce_id = t.contact and t.rn_tier_recent = 1
        where se.rn_undergrad = 1 and se.grade_level between 8 and 12
    )

select *,
from roster
where ktc_status is not null
