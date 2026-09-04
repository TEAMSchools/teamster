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

    -- The roster has first_day_of_school but no year-end date.
    -- int_students__calendar_week remaps Focus's internal school id to the
    -- network school number, which is the id ps_schoolid carries; school
    -- numbers are network-unique, so no region filter is needed here.
    focus_school_year_end as (
        select
            academic_year, schoolid, max(last_day_school_year) as last_day_school_year,
        from {{ ref("int_students__calendar_week") }}
        group by academic_year, schoolid
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
        from {{ ref("int_focus__student_enrollment_roster") }}
        where rn_year = 1
    ),

    -- Focus's stand-in for PowerSchool's "Out of District" special-program
    -- row (#5041). custom_863, the IDEA educational environment, is the only
    -- Focus field recording a placement at another institution, and its age
    -- 6-21 options are exactly PowerSchool's out-of-district set. Florida's
    -- age 3-5 options are excluded: Miami enrolls no pre-K, so classifying
    -- them would assert a rule nothing has reviewed --
    -- test_focus__idea_educational_environment_classified warns if one lands.
    -- Derived in its own CTE because BigQuery has no lateral column aliases,
    -- so the four columns below cannot share an alias computed beside them.
    focus_students as (
        select
            _dbt_source_project,
            ethnicity,
            gender,
            gifted_and_talented,
            homeless_code,
            homeless_primary_nighttime_residence_code,
            idea_educational_environment,
            idea_educational_environment_label,
            is_504,
            is_homeless,
            lep_status,
            lunchstatus,
            middle_name,
            spedlep,
            state_studentnumber,
            student_number,

            florida_education_identifier as fleid,

            -- PowerSchool's fedethnicity: 1 = Hispanic/Latino, 0 = not. Focus
            -- stores the answer as a select option; the label is the stable key.
            case
                ethnicity_hispanic_or_latino_label when 'Yes' then 1 when 'No' then 0
            end as fedethnicity,

            if(
                idea_educational_environment_code in ('C', 'D', 'F', 'H', 'P'),
                true,
                false
            ) as is_out_of_district,
        from {{ ref("int_focus__students") }}
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
            enr.school_abbreviation,

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
            stu.middle_name,
            stu.fedethnicity,
            stu.fleid,
            stu.is_504,

            -- Focus's 8400-prefixed student id, the canonical Miami student
            -- number in Focus-keyed systems (student logins, parts of iReady).
            -- student_number stays the bare network number, which Illuminate,
            -- kippadb and the assessment feeds key on.
            enr.student_number as focus_student_id,

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
            enr.network_student_number as student_number,

            (enr.academic_year + 13) + (-1 * enr.grade_level) as cohort_primary,

            if(yg.grade_level_prev = enr.grade_level, true, false) as is_retained_year,

            -- #4996. PowerSchool's own expressions, reproduced rather than
            -- simplified: exitdate is never null here because the roster
            -- coalesces it, so is_enrolled_y1 is always true today, and a
            -- `true` literal would silently diverge if that ever changes.
            if(enr.exitdate is not null, true, false) as is_enrolled_y1,

            case
                when enr.exitdate >= sye.last_day_school_year
                then true
                when
                    current_date('{{ var("local_timezone") }}')
                    between enr.startdate and enr.exitdate
                then true
                else false
            end as is_enrolled_recent,

            -- #4996, #5041. PowerSchool drives these four columns off one
            -- "Out of District" specprog row, so Focus branches all four on
            -- the same custom_863 match. reporting_schoolid takes the Focus
            -- option id, the analogue of PowerSchool's specprog programid --
            -- a hospital or a center school has no Florida school number. The
            -- if() form is null-safe on both counts: a roster row with no
            -- matching student, and a student with no custom_863 value, both
            -- fall to the in-district branch. Every Miami row is Z or null
            -- today, so all four still resolve to the in-district values.
            -- is_self_contained has no such source and stays null (#4968).
            if(stu.is_out_of_district, true, false) as is_out_of_district,

            if(
                stu.is_out_of_district,
                stu.idea_educational_environment,
                enr.reporting_schoolid
            ) as reporting_schoolid,

            if(
                stu.is_out_of_district,
                stu.idea_educational_environment_label,
                enr.school
            ) as reporting_school_name,

            if(stu.is_out_of_district, 'OD', enr.school_level) as school_level,
        from {{ ref("int_focus__student_enrollment_roster") }} as enr
        left join
            focus_students as stu
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
        left join
            focus_school_year_end as sye
            on enr.academic_year = sye.academic_year
            and enr.ps_schoolid = sye.schoolid
    ),

    focus_windowed as (
        select
            * except (is_enrolled_y1, is_enrolled_recent),

            -- Year grain, matching PowerSchool's max() over
            -- (studentid, yearid): any qualifying stint counts.
            max(is_enrolled_y1) over (
                partition by student_number, academic_year
            ) as is_enrolled_y1,

            max(is_enrolled_recent) over (
                partition by student_number, academic_year
            ) as is_enrolled_recent,

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
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from union_relations
    ),

    -- Both branches list every column. UNION ALL CORRESPONDING matches by name
    -- and errors when the two lists differ, so a column one SIS lacks has to
    -- be written down as an explicit null here instead of being padded
    -- silently (the FULL form did that, and hid the Miami nulls #5148 fixes).
    with_region as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            student_number,
            grade_level,
            schoolid,
            entrydate,
            exitdate,
            entrycode,
            exitcode,
            lunchstatus,
            state_studentnumber,
            first_name,
            middle_name,
            last_name,
            lastfirst,
            enroll_status,
            dob,
            state,
            fedethnicity,
            gender,
            ethnicity,
            academic_year,
            cohort_primary,
            rn_all,
            rn_year,
            grade_level_prev,
            year_in_school,
            year_in_network,
            is_enrolled_y1,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            is_enrolled_recent,
            is_enrolled_fdos,
            is_retained_year,
            is_retained_ever,
            boy_status,
            cohort_secondary,
            entry_schoolid,
            entry_grade_level,
            school_name,
            school_abbreviation,
            spedlep,
            lep_status,
            homeless_code,
            is_homeless,
            advisory_section_number,
            advisory_name,
            advisor_lastfirst,
            is_out_of_district,
            reporting_schoolid,
            reporting_school_name,
            school_level,
            cohort,

            /* PowerSchool only */
            studentid,
            students_dcid,
            reenrollments_dcid,
            exitcomment,
            fteid,
            street,
            city,
            zip,
            home_phone,
            next_school,
            sched_nextyeargrade,
            highest_grade_level_achieved,
            yearid,
            track,
            rn_school,
            yearid_prev,
            rn_undergrad,
            cohort_graduated,
            prevstudentid,
            advisor_teachernumber,
            exit_code_kf,
            exit_code_ts,
            is_self_contained,

            /* Focus only */
            cast(null as int64) as homeless_primary_nighttime_residence_code,
            cast(null as string) as gifted_and_talented,
            cast(null as string) as fleid,
            cast(null as int64) as focus_student_id,
            cast(null as bool) as is_504,
        from powerschool_conformed

        union all corresponding

        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            student_number,
            grade_level,
            schoolid,
            entrydate,
            exitdate,
            entrycode,
            exitcode,
            lunchstatus,
            state_studentnumber,
            first_name,
            middle_name,
            last_name,
            lastfirst,
            enroll_status,
            dob,
            state,
            fedethnicity,
            gender,
            ethnicity,
            academic_year,
            cohort_primary,
            rn_all,
            rn_year,
            grade_level_prev,
            year_in_school,
            year_in_network,
            is_enrolled_y1,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            is_enrolled_recent,
            is_enrolled_fdos,
            is_retained_year,
            is_retained_ever,
            boy_status,
            cohort_secondary,
            entry_schoolid,
            entry_grade_level,
            school_name,
            school_abbreviation,
            spedlep,
            lep_status,
            homeless_code,
            is_homeless,
            advisory_section_number,
            advisory_name,
            advisor_lastfirst,
            is_out_of_district,
            reporting_schoolid,
            reporting_school_name,
            school_level,
            cohort,

            /* PowerSchool only: no Focus source */
            cast(null as int64) as studentid,
            cast(null as int64) as students_dcid,
            cast(null as int64) as reenrollments_dcid,
            cast(null as string) as exitcomment,
            cast(null as int64) as fteid,
            cast(null as string) as street,
            cast(null as string) as city,
            cast(null as string) as zip,
            cast(null as string) as home_phone,
            cast(null as int64) as next_school,
            cast(null as int64) as sched_nextyeargrade,
            cast(null as int64) as highest_grade_level_achieved,
            cast(null as int64) as yearid,
            cast(null as string) as track,
            cast(null as int64) as rn_school,
            cast(null as int64) as yearid_prev,
            cast(null as int64) as rn_undergrad,
            cast(null as int64) as cohort_graduated,
            cast(null as int64) as prevstudentid,
            cast(null as string) as advisor_teachernumber,
            cast(null as string) as exit_code_kf,
            cast(null as string) as exit_code_ts,
            cast(null as bool) as is_self_contained,

            /* Focus only */
            homeless_primary_nighttime_residence_code,
            gifted_and_talented,
            fleid,
            focus_student_id,
            is_504,
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
        gifted_and_talented,
        is_504
    ),

    -- same value as _dbt_source_project, named for the Dagster code location;
    -- projected here rather than re-derived from _dbt_source_relation (#3142)
    ar._dbt_source_project as code_location,

    -- Pearson reports the KIPP student_number as LocalStudentIdentifier for all
    -- NJ regions, including Paterson (#4103); no legacy district-id translation
    -- is needed. prevstudentid is the pre-KIPP Paterson SIS id and never matches.
    ar.student_number as pearson_local_student_identifier,

    /* regional differences */
    -- fleid comes only from Focus (florida_education_identifier), via ar.*;
    -- the PowerSchool u_studentsuserfields copy is retired.
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

    -- njr and suf join through students_dcid, which Focus never populates, so
    -- Miami reads int_focus__students.is_504 (Section 504 Eligible). Null
    -- there means unset, not the fabricated negative false would imply.
    if(
        ar.region = 'Miami', ar.is_504, coalesce(njr.pid_504_tf, suf.is_504, false)
    ) as is_504,

    coalesce(adb.kipp_hs_class, ar.cohort) as ktc_cohort,

    sl.google_email as student_email_google,

    /* Both Paterson carve-outs here went stale in 4e11acd72, which retired the
    PowerSchool student_email path they were withheld for -- Paterson's Google
    address is now the login generator's google_email like every other region,
    so the username and password behind it come from the same place. Leaving the
    password null failed every Paterson row of the Google Directory user sync
    (#4756). The Miami SPED exception below is NOT stale: Miami has no rows in
    the edplan njsmart union, so it must keep reading ar.spedlep or its IEP data
    drops to null. Paterson used to share that exception and no longer does --
    it now pulls EdPlan like Newark and Camden. */
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
        ar.region = 'Miami', ar.spedlep, sped.special_education_code
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

    coalesce(if(ar.region = 'Miami', ar.spedlep, sped.spedlep), 'No IEP') as spedlep,

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
    on if(ar.region = 'Miami', ar.focus_student_id, ar.student_number)
    = sl.student_number
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
