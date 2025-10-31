with
    es_grad as (
        select
            _dbt_source_relation,
            student_number,
            entry_school_abbreviation as entry_school,

            max(
                if(
                    grade_level = 4 and exitdate >= date(academic_year + 1, 6, 1),
                    true,
                    false
                )
            ) as is_es_grad,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_year = 1
        group by _dbt_source_relation, student_number, entry_school_abbreviation
    ),

    dlm as (
        select _dbt_source_relation, student_number, max(pathway_option) as dlm,
        from {{ ref("int_students__graduation_path_codes") }}
        where rn_discipline_distinct = 1 and final_grad_path_code = 'M'
        group by _dbt_source_relation, student_number
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

            (
                {{ var("current_academic_year") }} - se.academic_year + se.grade_level
            ) as current_grade_level_projection,
        from {{ ref("int_extracts__student_enrollments") }} as se
        left join
            {{ ref("int_kippadb__contact") }} as c
            on se.student_number = c.contact_school_specific_id
        left join
            {{ ref("int_overgrad__students") }} as os
            on se.salesforce_contact_id = os.external_student_id
            and {{ union_dataset_join_clause(left_alias="se", right_alias="os") }}
        left join
            es_grad as e
            on se.student_number = e.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="e") }}
        left join
            dlm as d
            on se.student_number = d.student_number
            and {{ union_dataset_join_clause(left_alias="se", right_alias="d") }}
        where se.rn_undergrad = 1 and se.grade_level between 8 and 12
    )

select *,
from roster
where ktc_status is not null
