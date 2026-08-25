-- The powerschool package dropped the contact/emergency/pickup columns from
-- base_powerschool__student_enrollments; the contact surface now lives in
-- int_students__contacts_pivot, consumed downstream by int_extracts. This
-- comment also forces state:modified so CI rebuilds the wrapper against the
-- narrowed district schema.
{% set invalid_lunch_status = ["", "NoD", "1", "2"] %}

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "base_powerschool__student_enrollments",
                    ),
                ]
            )
        }}
    ),

    -- One row per Miami student per year, carrying the prior year's grade so
    -- boy_status and is_retained_year reproduce the PowerSchool derivation.
    -- rn_year = 1 picks the primary stint, matching the year grain PowerSchool
    -- computes these over.
    focus_year_grain as (
        select
            network_student_number,
            academic_year,
            grade_level,

            lag(grade_level) over (
                partition by network_student_number order by academic_year asc
            ) as grade_level_prev,

            lag(academic_year) over (
                partition by network_student_number order by academic_year asc
            ) as academic_year_prev,
        from {{ ref("int_focus__student_enrollments") }}
        where rn_year = 1
    ),

    focus_conformed as (
        select
            enr._dbt_source_relation,
            enr._dbt_source_project,
            enr.region,
            enr.academic_year,
            enr.exitdate,
            enr.enroll_status,
            enr.entrycode,
            enr.exitcode,
            enr.grade_level,
            enr.rn_year,
            enr.rn_all,
            enr.year_in_school,
            enr.year_in_network,
            enr.is_enrolled_fdos,
            enr.is_enrolled_oct01,
            enr.is_enrolled_oct15,
            enr.is_enrolled_mar15,
            enr.dob,
            enr.state,
            enr.school_level,
            enr.school_abbreviation,
            enr.reporting_schoolid,

            stu.spedlep,
            stu.lep_status,
            stu.lunchstatus,
            stu.homeless_code,
            stu.homeless_primary_nighttime_residence_code,
            stu.is_homeless,
            stu.gifted_and_talented,
            stu.ethnicity,
            stu.gender,
            stu.state_studentnumber,

            adv.advisory_section_number,
            adv.advisory_name,
            adv.advisor_lastfirst,

            yg.grade_level_prev,
            yg.academic_year_prev,

            enr.ps_schoolid as schoolid,
            enr.startdate as entrydate,
            enr.student_first_name as first_name,
            enr.student_last_name as last_name,
            enr.student_name as lastfirst,
            enr.school as school_name,
            enr.school as reporting_school_name,
            enr.network_student_number as student_number,

            (enr.academic_year + 13) + (-1 * enr.grade_level) as cohort_primary,

            if(yg.grade_level_prev = enr.grade_level, true, false) as is_retained_year,
        from {{ ref("int_focus__student_enrollments") }} as enr
        left join
            {{ ref("int_focus__students") }} as stu
            on enr.network_student_number = stu.student_number
            and enr._dbt_source_project = stu._dbt_source_project
        left join
            focus_year_grain as yg
            on enr.network_student_number = yg.network_student_number
            and enr.academic_year = yg.academic_year
        left join
            {{ ref("int_focus__advisory") }} as adv
            on enr.student_number = adv.student_number
            and enr.academic_year = adv.academic_year
            and enr.schoolid = adv.schoolid
            and enr._dbt_source_project = adv._dbt_source_project
    ),

    focus_windowed as (
        select
            *,

            max(if(year_in_school = 1, cohort_primary, null)) over (
                partition by student_number, schoolid
            ) as cohort_secondary,

            max(if(year_in_network = 1, schoolid, null)) over (
                partition by student_number
            ) as entry_schoolid,

            max(if(year_in_network = 1, grade_level, null)) over (
                partition by student_number
            ) as entry_grade_level,

            max(is_retained_year) over (
                partition by student_number
            ) as is_retained_ever,
        from focus_conformed
    ),

    -- boy_status and cohort read cohort_secondary, so they follow the window
    -- CTE rather than sharing its select list -- BigQuery rejects a lateral
    -- alias reference.
    focus_final as (
        select
            *,

            case
                when grade_level = 99
                then 'Graduated'
                when year_in_network = 1
                then 'New'
                when grade_level_prev is null
                then 'New'
                when academic_year - academic_year_prev > 1
                then 'Re-Enrolled'
                when grade_level_prev < grade_level
                then 'Promoted'
                when grade_level_prev = grade_level
                then 'Retained'
                when grade_level_prev > grade_level
                then 'Demoted'
            end as boy_status,

            case
                when grade_level >= 9 then cohort_secondary else cohort_primary
            end as cohort,
        from focus_windowed
    ),

    powerschool_conformed as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    ),

    with_region as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select * except (academic_year_prev),
        from focus_final
    )

select
    ar.* except (
        lep_status,
        lunchstatus,
        spedlep,
        prevstudentid,
        homeless_code,
        homeless_primary_nighttime_residence_code,
        gifted_and_talented
    ),

    -- same value as _dbt_source_project, named for the Dagster code location;
    -- projected here rather than re-derived from _dbt_source_relation (#3142)
    ar._dbt_source_project as code_location,

    -- Pearson reports the KIPP student_number as LocalStudentIdentifier for all
    -- NJ regions, including Paterson (#4103); no legacy district-id translation
    -- is needed. prevstudentid is the pre-KIPP Paterson SIS id and never matches.
    ar.student_number as pearson_local_student_identifier,

    /* regional differences */
    suf.fleid,
    suf.newark_enrollment_number,
    suf.infosnap_id,
    suf.infosnap_opt_in,
    suf.media_release,
    suf.rides_staff,

    njs.districtcoderesident,
    njs.referral_date,
    njs.parental_consent_eval_date,
    njs.eligibility_determ_date,
    njs.initial_iep_meeting_date,
    njs.parent_consent_intial_iep_date,
    njs.annual_iep_review_meeting_date,
    njs.reevaluation_date,
    njs.parent_consent_obtain_code,
    njs.initial_process_delay_reason,
    njs.special_education_placement,
    njs.time_in_regular_program,
    njs.early_intervention_yn,
    njs.determined_ineligible_yn,
    njs.counseling_services_yn,
    njs.occupational_therapy_serv_yn,
    njs.physical_therapy_services_yn,
    njs.speech_lang_theapy_services_yn,
    njs.other_related_services_yn,
    njs.lepbegindate,
    njs.lependdate,
    njs.lep_tf,
    njs.liep_parent_refusal_date,
    njs.programtypecode,
    njs.home_language,

    sr.mail as advisor_email,
    sr.work_cell as advisor_phone,

    tpd.total_balance as lunch_balance,

    adb.id as salesforce_contact_id,
    adb.college_match_display_gpa as salesforce_contact_college_match_display_gpa,
    adb.kipp_hs_class as salesforce_contact_kipp_hs_class,
    adb.owner_id as salesforce_contact_owner_id,
    adb.graduation_year,

    adbu.name as salesforce_contact_owner_name,
    adbu.phone as salesforce_contact_owner_phone,
    adbu.email as salesforce_contact_owner_email,

    ill.student_id as illuminate_student_id,

    -- suf covers all four districts and previously carried Miami's PowerSchool
    -- value; Miami's students_dcid is now always null (Focus has no
    -- equivalent), so suf never matches a Miami row and ar.gifted_and_talented
    -- (from int_focus__students, via focus_conformed) is the fallback.
    coalesce(
        njs.gifted_and_talented, suf.gifted_and_talented, ar.gifted_and_talented, 'N'
    ) as gifted_and_talented,

    -- Both njr and suf join through students_dcid, which Focus never
    -- populates, so Miami has no 504 source at all -- null means unknown,
    -- not the fabricated negative false would imply.
    if(
        ar.region = 'Miami', null, coalesce(njr.pid_504_tf, suf.is_504, false)
    ) as is_504,

    coalesce(adb.kipp_hs_class, ar.cohort) as ktc_cohort,

    sl.google_email as student_email_google,

    /* Both Paterson carve-outs here went stale in 4e11acd72, which retired the
    PowerSchool student_email path they were withheld for -- Paterson's Google
    address is now the login generator's google_email like every other region,
    so the username and password behind it come from the same place. Leaving the
    password null failed every Paterson row of the Google Directory user sync
    (#4756). The Miami/Paterson SPED exceptions below are NOT stale: neither
    region has rows in the edplan njsmart union, so they must keep reading
    ar.spedlep or their IEP data drops to null. */
    sl.username as student_web_id,
    sl.default_password as student_web_password,

    if(ar.region = 'Miami' and fte.survey_2 is not null, true, false) as is_fldoe_fte_2,
    if(ar.region = 'Miami' and fte.survey_3 is not null, true, false) as is_fldoe_fte_3,
    if(
        ar.region = 'Miami' and fte.survey_2 is not null and fte.survey_3 is not null,
        true,
        false
    ) as is_fldoe_fte_all,

    if(
        ar.region in ('Miami', 'Paterson'), ar.spedlep, sped.special_education_code
    ) as special_education_code,

    if(adb.latest_fafsa_date is null, 'No', 'Yes') as salesforce_contact_df_has_fafsa,

    /* The NJ re-enrollment extension records homelessness per enrollment stint,
    but is not written until well after year end -- it is empty for the current
    year. The student-level tables are maintained live yet overwritten in place,
    so they describe only current status. Reading the current year from the
    student-level tables and closed years from the re-enrollment extension keeps
    both the live value and the history accurate (#4814). */
    if(
        ar.academic_year = {{ var("current_academic_year") }},
        ar.homeless_code,
        njr.homeless_code
    ) as homeless_code,

    -- njs (stg_powerschool__s_nj_stu_x) only ever matches NJ, via
    -- students_dcid; ar.homeless_primary_nighttime_residence_code (from
    -- int_focus__students, via focus_conformed) is the Miami equivalent and is
    -- only ever populated there. The two never overlap, so coalescing is safe.
    if(
        ar.academic_year = {{ var("current_academic_year") }},
        coalesce(
            njs.homelessprimarynighttimeres,
            ar.homeless_primary_nighttime_residence_code
        ),
        njr.homelessprimarynighttimeres
    ) as homeless_primary_nighttime_residence_code,

    coalesce(
        if(ar.region in ('Miami', 'Paterson'), ar.spedlep, sped.spedlep), 'No IEP'
    ) as spedlep,

    case
        when ar.region = 'Miami'
        then ar.lep_status
        when njs.lepbegindate is null
        then false
        when njs.lependdate < ar.entrydate
        then false
        when njs.lepbegindate <= ar.exitdate
        then true
        else false
    end as lep_status,

    case
        when ar.lunchstatus in unnest({{ invalid_lunch_status }})
        then null
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunchstatus
        when ar.region = 'Miami'
        then ar.lunchstatus
        when ar.rn_year = 1
        then coalesce(if(tpd.is_directly_certified, 'F', null), tpd.eligibility_name)
    end as lunch_status,

    case
        when ar.academic_year < {{ var("current_academic_year") }}
        then ar.lunchstatus
        when ar.region = 'Miami'
        then ar.lunchstatus
        when ar.rn_year = 1
        then
            case
                when tpd.is_directly_certified
                then 'Direct Certification'
                when tpd.eligibility_determination_reason is null
                then 'No Application'
                else tpd.eligibility || ' - ' || tpd.eligibility_determination_reason
            end
    end as lunch_application_status,

    case
        when adb.college_match_display_gpa >= 3.50
        then '3.50+'
        when adb.college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when adb.college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when adb.college_match_display_gpa >= 2.00
        then '2.00-2.49'
        when adb.college_match_display_gpa < 2.00
        then '<2.00'
        else 'No GPA'
    end as salesforce_contact_college_match_gpa_band,

    if(
        extract(
            month
            from coalesce(adb.actual_hs_graduation_date, adb.expected_hs_graduation)
        )
        < 10,
        extract(
            year
            from coalesce(adb.actual_hs_graduation_date, adb.expected_hs_graduation)
        ),
        extract(
            year
            from coalesce(adb.actual_hs_graduation_date, adb.expected_hs_graduation)
        )
        + 1
    ) as salesforce_graduation_year,

from with_region as ar
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on ar.students_dcid = suf.studentsdcid
    and ar._dbt_source_project = suf._dbt_source_project
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
    on ar.students_dcid = njs.studentsdcid
    and ar._dbt_source_project = njs._dbt_source_project
left join
    {{ ref("stg_powerschool__s_nj_ren_x") }} as njr
    on ar.reenrollments_dcid = njr.reenrollmentsdcid
    and ar._dbt_source_project = njr._dbt_source_project
left join
    {{ ref("stg_people__student_logins") }} as sl
    on ar.student_number = sl.student_number
left join
    {{ ref("int_people__staff_roster") }} as sr
    on ar.advisor_teachernumber = sr.powerschool_teacher_number
left join
    {{ ref("int_edplan__njsmart_powerschool_union") }} as sped
    on ar.student_number = sped.student_number
    and ar.academic_year = sped.academic_year
    and ar._dbt_source_project = sped._dbt_source_project
    and sped.rn_student_year_desc = 1
left join
    {{ ref("stg_titan__person_data") }} as tpd
    on ar.student_number = tpd.person_identifier
    and ar.academic_year = tpd.academic_year
    and ar._dbt_source_project = tpd._dbt_source_project
left join
    {{ ref("int_fldoe__fte_pivot") }} as fte
    on ar.state_studentnumber = fte.student_id
    and ar.academic_year = fte.academic_year
    and ar._dbt_source_project = fte._dbt_source_project
left join
    {{ ref("stg_kippadb__contact") }} as adb
    on ar.student_number = adb.school_specific_id
left join {{ ref("stg_kippadb__user") }} as adbu on adb.owner_id = adbu.id
left join
    {{ ref("stg_illuminate__public__students") }} as ill
    on ar.student_number = ill.local_student_id
