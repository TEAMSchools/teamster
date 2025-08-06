with
    subjects as (
        select
            iready_subject,

            case
                iready_subject
                when 'Reading'
                then 'Text Study'
                when 'Math'
                then 'Mathematics'
            end as illuminate_subject_area,

            case
                iready_subject when 'Reading' then 'ENG' when 'Math' then 'MATH'
            end as powerschool_credittype,

            case
                iready_subject when 'Reading' then 'ela' when 'Math' then 'math'
            end as grad_unpivot_subject,

            case
                iready_subject when 'Reading' then 'ELA' when 'Math' then 'Math'
            end as discipline,

        from unnest(['Reading', 'Math']) as iready_subject
    )

select
    co._dbt_source_relation,
    co.studentid,
    co.students_dcid,
    co.student_number,
    co.grade_level,
    co.schoolid,
    co.entrydate,
    co.exitdate,
    co.entrycode,
    co.exitcode,
    co.exitcomment,
    co.fteid,
    co.state_studentnumber,
    co.first_name,
    co.middle_name,
    co.last_name,
    co.lastfirst,
    co.enroll_status,
    co.dob,
    co.fedethnicity,
    co.gender,
    co.ethnicity,
    co.yearid,
    co.academic_year,
    co.exit_code_kf,
    co.exit_code_ts,
    co.rn_all,
    co.rn_year,
    co.rn_school,
    co.grade_level_prev,
    co.yearid_prev,
    co.rn_undergrad,
    co.year_in_school,
    co.year_in_network,
    co.is_enrolled_y1,
    co.is_enrolled_oct01,
    co.is_enrolled_oct15,
    co.is_enrolled_recent,
    co.is_retained_year,
    co.cohort_graduated,
    co.is_retained_ever,
    co.boy_status,
    co.cohort_secondary,
    co.entry_schoolid,
    co.entry_grade_level,
    co.school_name,
    co.school_abbreviation,
    co.is_homeless,
    co.advisory_name,
    co.advisor_teachernumber,
    co.advisor_lastfirst,
    co.cohort,
    co.is_self_contained,
    co.is_out_of_district,
    co.reporting_schoolid,
    co.reporting_school_name,
    co.school_level,
    co.code_location,
    co.region,
    co.advisor_email,
    co.advisor_phone,
    co.student_web_id,
    co.student_web_password,
    co.student_email_google,
    co.fleid,
    co.lepbegindate,
    co.lependdate,
    co.salesforce_contact_id,
    co.salesforce_contact_college_match_display_gpa,
    co.salesforce_contact_kipp_hs_class,
    co.salesforce_contact_owner_id,
    co.salesfoce_contact_owner_name,
    co.illuminate_student_id,
    co.gifted_and_talented,
    co.is_504,
    co.ktc_cohort,
    co.is_fldoe_fte_2,
    co.is_fldoe_fte_3,
    co.is_fldoe_fte_all,
    co.special_education_code,
    co.spedlep,
    co.lep_status,
    co.lunch_status,
    co.lunch_application_status,
    co.salesforce_contact_college_match_gpa_band,

    cw.week_start_monday,
    cw.week_end_sunday,
    cw.quarter,
    cw.semester,
    cw.school_week_start_date,
    cw.school_week_end_date,
    cw.week_number_academic_year,
    cw.week_number_quarter,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    sj.grad_unpivot_subject,
    sj.discipline,

    if(
        cw.week_start_monday between co.entrydate and co.exitdate, true, false
    ) as is_enrolled_week,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on co.academic_year = cw.academic_year
    and co.schoolid = cw.schoolid
cross join subjects as sj
where co.grade_level != 99
