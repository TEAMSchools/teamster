with
    att_mem as (
        select
            _dbt_source_relation,
            studentid,
            yearid,
            sum(attendancevalue) as n_attendance,
            sum(membershipvalue) as n_membership,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where membershipvalue = 1
        group by studentid, yearid, _dbt_source_relation
    ),

    target_union as (
        select
            academic_year,
            schoolid,
            false as is_self_contained,
            grade_level,
            target_enrollment,
            financial_model_enrollment as target_enrollment_finance,
            grade_band_ratio,
            at_risk_and_lep_ratio,
            at_risk_only_ratio,
            lep_only_ratio,
            sped_ratio,
            '`{{ target.database }}`.`'
            || regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
            || '_powerschool'
            || '`.`base_powerschool__student_enrollments`' as _dbt_source_relation,
        from {{ ref("stg_finance__enrollment_targets") }}

        union all

        /* Newark/Miami SC & OOD students */
        select
            academic_year,
            reporting_schoolid,
            is_self_contained,
            grade_level,
            1 as target_enrollment,
            1 as target_enrollment_finance,
            null as grade_band_ratio,
            null as at_risk_and_lep_ratio,
            null as at_risk_only_ratio,
            null as lep_only_ratio,
            null as sped_ratio,
            _dbt_source_relation,
        from {{ ref("base_powerschool__student_enrollments") }}
        where
            (is_self_contained or is_out_of_district)
            and rn_year = 1
            and regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
            in ('kippnewark', 'kippmiami')
    ),

    targets as (
        select
            _dbt_source_relation,
            academic_year,
            schoolid,
            is_self_contained,
            grade_level,
            sum(target_enrollment) as target_enrollment,
            sum(target_enrollment_finance) as target_enrollment_finance,
            max(grade_band_ratio) as grade_band_ratio,
            max(at_risk_and_lep_ratio) as at_risk_and_lep_ratio,
            max(at_risk_only_ratio) as at_risk_only_ratio,
            max(lep_only_ratio) as lep_only_ratio,
            max(sped_ratio) as sped_ratio,
        from target_union
        group by
            academic_year,
            schoolid,
            grade_level,
            is_self_contained,
            _dbt_source_relation
    )

select
    se.student_number,
    se.lastfirst,
    se.academic_year,
    se.region,
    se.school_level,
    se.schoolid,
    se.reporting_schoolid,
    se.school_name,
    se.grade_level,
    se.enroll_status,
    se.entrydate,
    se.exitdate,
    se.exitcode,
    se.exitcomment,
    se.spedlep as iep_status,
    se.special_education_code as specialed_classification,
    se.lep_status,
    se.is_504 as c_504_status,
    se.is_self_contained as is_pathways,
    se.lunch_status as lunchstatus,
    se.lunch_application_status as lunch_app_status,
    se.ethnicity,
    se.gender,
    se.is_enrolled_y1,
    se.is_enrolled_oct01,
    se.is_enrolled_oct15,
    se.is_enrolled_recent,
    null as is_enrolled_oct15_week,
    null as is_enrolled_jan15_week,
    se.track,
    se.exit_code_kf,
    se.exit_code_ts,
    se.districtcoderesident,
    se.referral_date,
    se.parental_consent_eval_date,
    se.eligibility_determ_date,
    se.initial_iep_meeting_date,
    se.parent_consent_intial_iep_date,
    se.annual_iep_review_meeting_date,
    se.reevaluation_date,
    se.parent_consent_obtain_code,
    se.initial_process_delay_reason,
    se.special_education_placement,
    se.time_in_regular_program,
    se.early_intervention_yn,
    se.determined_ineligible_yn,
    se.counseling_services_yn,
    se.occupational_therapy_serv_yn,
    se.physical_therapy_services_yn,
    se.speech_lang_theapy_services_yn,
    se.other_related_services_yn,
    lead(se.schoolid, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_schoolid,
    lead(se.exitdate, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_exitdate,
    lead(se.exitcode, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_exitcode,
    lead(se.exit_code_kf, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_exit_code_kf,
    lead(se.exit_code_ts, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_exit_code_ts,
    lead(se.exitcomment, 1) over (
        partition by se.student_number order by se.academic_year asc
    ) as next_exitcomment,
    lead(se.is_enrolled_oct01, 1, false) over (
        partition by se.student_number order by se.academic_year
    ) as is_enrolled_oct01_next,
    lead(se.is_enrolled_oct15, 1, false) over (
        partition by se.student_number order by se.academic_year
    ) as is_enrolled_oct15_next,

    cal.days_remaining,
    cal.days_total,

    ifnull(att_mem.n_attendance, 0) as n_attendance,
    ifnull(att_mem.n_membership, 0) as n_membership,

    t.target_enrollment,
    t.target_enrollment_finance,
    t.grade_band_ratio,
    t.at_risk_and_lep_ratio,
    t.at_risk_only_ratio,
    t.lep_only_ratio,
    t.sped_ratio,
from {{ ref("base_powerschool__student_enrollments") }} as se
left join
    {{ ref("int_powerschool__calendar_rollup") }} as cal
    on se.schoolid = cal.schoolid
    and se.yearid = cal.yearid
    and se.track = cal.track
    and {{ union_dataset_join_clause(left_alias="se", right_alias="cal") }}
left join
    att_mem
    on se.studentid = att_mem.studentid
    and se.yearid = att_mem.yearid
    and {{ union_dataset_join_clause(left_alias="se", right_alias="att_mem") }}
left join
    targets as t
    on se.academic_year = t.academic_year
    and se.reporting_schoolid = t.schoolid
    and se.grade_level = t.grade_level
    and se.is_self_contained = t.is_self_contained
    and {{ union_dataset_join_clause(left_alias="se", right_alias="t") }}
where se.rn_year = 1
