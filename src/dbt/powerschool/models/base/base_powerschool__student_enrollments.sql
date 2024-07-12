{%- set invalid_lunch_status = ["", "NoD", "1", "2"] -%}

with
    union_relations as (
        /* terminal (pre, current, transfers) */
        select
            s.id as studentid,
            s.dcid as students_dcid,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.entrydate,
            s.exitdate,
            s.entrycode,
            s.exitcode,
            s.exitcomment,
            s.lunchstatus,
            s.fteid,

            s.state_studentnumber,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.lastfirst,
            s.enroll_status,
            s.dob,
            s.street,
            s.city,
            s.state,
            s.zip,
            s.home_phone,
            s.fedethnicity,
            s.next_school,
            s.sched_nextyeargrade,
            s.grade_level as highest_grade_level_achieved,
            s.gender_code as gender,
            s.ethnicity_code as ethnicity,

            terms.yearid,

            x1.exit_code as exit_code_kf,
            x2.exit_code as exit_code_ts,

            coalesce(s.track, 'A') as track,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__terms") }} as terms
            on s.schoolid = terms.schoolid
            and s.entrydate between terms.firstday and terms.lastday
            and terms.isyearrec = 1
        left join
            {{ ref("stg_powerschool__u_clg_et_stu") }} as x1
            on s.dcid = x1.studentsdcid
            and s.exitdate = x1.exit_date
        left join
            {{ ref("stg_powerschool__u_clg_et_stu_alt") }} as x2
            on s.dcid = x2.studentsdcid
            and s.exitdate = x2.exit_date
        where s.enroll_status in (-1, 0, 2) and s.exitdate > s.entrydate

        union all

        /* re-enrollments */
        select
            re.studentid,

            s.dcid as students_dcid,
            s.student_number,

            re.grade_level,
            re.schoolid,
            re.entrydate,
            re.exitdate,
            re.entrycode,
            re.exitcode,
            re.exitcomment,
            re.lunchstatus,
            re.fteid,

            s.state_studentnumber,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.lastfirst,
            s.enroll_status,
            s.dob,
            s.street,
            s.city,
            s.state,
            s.zip,
            s.home_phone,
            s.fedethnicity,

            null as next_school,
            null as sched_nextyeargrade,

            s.grade_level as highest_grade_level_achieved,
            s.gender_code as gender,
            s.ethnicity_code as ethnicity,

            terms.yearid,

            x1.exit_code as exit_code_kf,
            x2.exit_code as exit_code_ts,

            coalesce(re.track, 'A') as track,
        from {{ ref("stg_powerschool__reenrollments") }} as re
        inner join {{ ref("stg_powerschool__students") }} as s on re.studentid = s.id
        inner join
            {{ ref("stg_powerschool__terms") }} as terms
            on re.schoolid = terms.schoolid
            and re.entrydate between terms.firstday and terms.lastday
            and terms.isyearrec = 1
        left join
            {{ ref("stg_powerschool__u_clg_et_stu") }} as x1
            on s.dcid = x1.studentsdcid
            and re.exitdate = x1.exit_date
        left join
            {{ ref("stg_powerschool__u_clg_et_stu_alt") }} as x2
            on s.dcid = x2.studentsdcid
            and re.exitdate = x2.exit_date
        where
            re.schoolid != 12345  /* filter out summer school */
            and re.exitdate > re.entrydate

        union all

        /* terminal (grads) */
        select
            s.id as studentid,
            s.dcid as students_dcid,
            s.student_number,
            s.grade_level,
            s.schoolid,

            null as entrydate,
            null as exitdate,
            null as entrycode,
            null as exitcode,
            null as exitcomment,
            null as lunchstatus,
            null as fteid,

            s.state_studentnumber,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.lastfirst,
            s.enroll_status,
            s.dob,
            s.street,
            s.city,
            s.state,
            s.zip,
            s.home_phone,
            s.fedethnicity,

            null as next_school,
            null as sched_nextyeargrade,

            s.grade_level as highest_grade_level_achieved,
            s.gender_code as gender,
            s.ethnicity_code as ethnicity,

            terms.yearid,

            null as exit_code_kf,
            null as exit_code_ts,
            'A' as track,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__terms") }} as terms
            on s.schoolid = terms.schoolid
            and s.entrydate <= terms.firstday
            and terms.isyearrec = 1
        where s.enroll_status = 3
    ),

    enr_order as (
        select
            *,

            yearid + 1990 as academic_year,
            yearid + 2003 + (-1 * grade_level) as cohort_primary,

            if(
                lunchstatus in unnest({{ invalid_lunch_status }}), null, lunchstatus
            ) as lunch_status,

            lag(yearid, 1) over (
                partition by studentid order by yearid asc
            ) as yearid_prev,
            lag(grade_level, 1) over (
                partition by studentid order by yearid asc
            ) as grade_level_prev,

            row_number() over (
                partition by studentid, yearid order by yearid desc, exitdate desc
            ) as rn_year,
            row_number() over (
                partition by studentid, schoolid order by yearid desc, exitdate desc
            ) as rn_school,
            row_number() over (
                partition by studentid, case when grade_level = 99 then 1 else 0 end
                order by yearid desc, exitdate desc
            ) as rn_undergrad,
            row_number() over (
                partition by studentid order by yearid desc, exitdate desc
            ) as rn_all,
        from union_relations
    ),

    enr_window as (
        select
            * except (grade_level_prev, yearid_prev),

            min(grade_level_prev) over (
                partition by studentid, yearid
            ) as grade_level_prev,
            min(yearid_prev) over (partition by studentid, yearid) as yearid_prev,

            row_number() over (
                partition by studentid, schoolid, rn_year
                order by yearid asc, exitdate asc
            ) as year_in_school,
            row_number() over (
                partition by studentid, rn_year order by yearid asc, exitdate asc
            ) as year_in_network,
        from enr_order
    ),

    enr_bools as (
        select
            enr.* except (rn_undergrad, year_in_school, year_in_network),

            if(enr.grade_level != 99, enr.rn_undergrad, null) as rn_undergrad,
            if(enr.rn_year = 1, enr.year_in_school, null) as year_in_school,
            if(enr.rn_year = 1, enr.year_in_network, null) as year_in_network,

            if(enr.exitcode = 'G1', enr.cohort_primary, null) as cohort_graduated,
            if(enr.exitdate is not null, true, false) as is_enrolled_y1,
            if(
                date(enr.academic_year, 10, 1) between enr.entrydate and enr.exitdate,
                true,
                false
            ) as is_enrolled_oct01,
            if(
                date(enr.academic_year, 10, 15) between enr.entrydate and enr.exitdate,
                true,
                false
            ) as is_enrolled_oct15,

            case
                when enr.yearid = enr.yearid_prev
                then false
                when enr.grade_level != 99 and enr.grade_level <= enr.grade_level_prev
                then true
                else false
            end as is_retained_year,

            case
                when enr.exitdate >= cr.max_calendardate
                then true
                when
                    current_date('{{ var("local_timezone") }}')
                    between enr.entrydate and enr.exitdate
                then true
                else false
            end as is_enrolled_recent,
        from enr_window as enr
        left join
            {{ ref("int_powerschool__calendar_rollup") }} as cr
            on enr.schoolid = cr.schoolid
            and enr.yearid = cr.yearid
            and enr.track = cr.track
    ),

    enr_bools_window as (
        select
            * except (
                cohort_graduated,
                year_in_school,
                year_in_network,
                is_enrolled_y1,
                is_enrolled_oct01,
                is_enrolled_oct15,
                is_enrolled_recent
            ),

            max(cohort_graduated) over (partition by studentid) as cohort_graduated,
            max(year_in_school) over (partition by studentid, yearid) as year_in_school,
            max(year_in_network) over (
                partition by studentid, yearid
            ) as year_in_network,
            max(is_enrolled_y1) over (partition by studentid, yearid) as is_enrolled_y1,
            max(is_enrolled_oct01) over (
                partition by studentid, yearid
            ) as is_enrolled_oct01,
            max(is_enrolled_oct15) over (
                partition by studentid, yearid
            ) as is_enrolled_oct15,
            max(is_enrolled_recent) over (
                partition by studentid, yearid
            ) as is_enrolled_recent,

            max(is_retained_year) over (partition by studentid) as is_retained_ever,
        from enr_bools
    ),

    with_boy_status as (
        select
            *,

            if(year_in_school = 1, cohort_primary, null) as cohort_secondary,
            if(year_in_network = 1, schoolid, null) as entry_schoolid,
            if(year_in_network = 1, grade_level, null) as entry_grade_level,

            case
                when grade_level = 99
                then 'Graduated'
                when year_in_network = 1 or grade_level_prev is null
                then 'New'
                when yearid - yearid_prev > 1
                then 'Re-Enrolled'
                when grade_level_prev < grade_level
                then 'Promoted'
                when grade_level_prev = grade_level
                then 'Retained'
                when grade_level_prev > grade_level
                then 'Demoted'
            end as boy_status,
        from enr_bools_window
    ),

    with_boy_status_window as (
        select
            * except (cohort_secondary, entry_schoolid, entry_grade_level),

            max(cohort_secondary) over (
                partition by studentid, schoolid
            ) as cohort_secondary,
            max(entry_schoolid) over (partition by studentid) as entry_schoolid,
            max(entry_grade_level) over (partition by studentid) as entry_grade_level,
        from with_boy_status
    )

select
    enr.*,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,

    scf.spedlep,
    scf.lep_status,
    scf.is_homeless,

    adv.advisory_name,
    adv.advisor_teachernumber,
    adv.advisor_lastfirst,

    scw.contact_1_address_home,
    scw.contact_1_email_current,
    scw.contact_1_name,
    scw.contact_1_phone_daytime,
    scw.contact_1_phone_home,
    scw.contact_1_phone_mobile,
    scw.contact_1_phone_primary,
    scw.contact_1_phone_work,
    scw.contact_1_relationship,
    scw.contact_2_address_home,
    scw.contact_2_email_current,
    scw.contact_2_name,
    scw.contact_2_phone_daytime,
    scw.contact_2_phone_home,
    scw.contact_2_phone_mobile,
    scw.contact_2_phone_primary,
    scw.contact_2_phone_work,
    scw.contact_2_relationship,
    scw.emergency_1_address_home,
    scw.emergency_1_email_current,
    scw.emergency_1_name,
    scw.emergency_1_phone_daytime,
    scw.emergency_1_phone_home,
    scw.emergency_1_phone_mobile,
    scw.emergency_1_phone_primary,
    scw.emergency_1_phone_work,
    scw.emergency_1_relationship,
    scw.emergency_2_address_home,
    scw.emergency_2_email_current,
    scw.emergency_2_name,
    scw.emergency_2_phone_daytime,
    scw.emergency_2_phone_home,
    scw.emergency_2_phone_mobile,
    scw.emergency_2_phone_primary,
    scw.emergency_2_phone_work,
    scw.emergency_2_relationship,
    scw.emergency_3_address_home,
    scw.emergency_3_email_current,
    scw.emergency_3_name,
    scw.emergency_3_phone_daytime,
    scw.emergency_3_phone_home,
    scw.emergency_3_phone_mobile,
    scw.emergency_3_phone_primary,
    scw.emergency_3_phone_work,
    scw.emergency_3_relationship,
    scw.pickup_1_address_home,
    scw.pickup_1_email_current,
    scw.pickup_1_name,
    scw.pickup_1_phone_daytime,
    scw.pickup_1_phone_home,
    scw.pickup_1_phone_mobile,
    scw.pickup_1_phone_primary,
    scw.pickup_1_phone_work,
    scw.pickup_1_relationship,
    scw.pickup_2_address_home,
    scw.pickup_2_email_current,
    scw.pickup_2_name,
    scw.pickup_2_phone_daytime,
    scw.pickup_2_phone_home,
    scw.pickup_2_phone_mobile,
    scw.pickup_2_phone_primary,
    scw.pickup_2_phone_work,
    scw.pickup_2_relationship,
    scw.pickup_3_address_home,
    scw.pickup_3_email_current,
    scw.pickup_3_name,
    scw.pickup_3_phone_daytime,
    scw.pickup_3_phone_home,
    scw.pickup_3_phone_mobile,
    scw.pickup_3_phone_primary,
    scw.pickup_3_phone_work,
    scw.pickup_3_relationship,

    case
        when enr.grade_level = 99
        then enr.cohort_graduated
        when enr.grade_level >= 9
        then enr.cohort_secondary
        else enr.cohort_primary
    end as cohort,

    coalesce(sp.is_self_contained, false) as is_self_contained,

    coalesce(ood.is_out_of_district, false) as is_out_of_district,

    if(ood.dcid is not null, ood.programid, enr.schoolid) as reporting_schoolid,

    if(ood.dcid is not null, ood.specprog_name, sch.name) as reporting_school_name,

    case
        when ood.dcid is not null
        then 'OD'
        when sch.high_grade = 12
        then 'HS'
        when sch.high_grade = 8
        then 'MS'
        when sch.high_grade = 4
        then 'ES'
    end as school_level,
from with_boy_status_window as enr
inner join
    {{ ref("stg_powerschool__schools") }} as sch on enr.schoolid = sch.school_number
left join
    {{ ref("stg_powerschool__studentcorefields") }} as scf
    on enr.students_dcid = scf.studentsdcid
left join
    {{ ref("int_powerschool__advisory") }} as adv
    on enr.studentid = adv.studentid
    and enr.yearid = adv.yearid
    and enr.schoolid = adv.schoolid
left join
    {{ ref("int_powerschool__student_contacts_pivot") }} as scw
    on enr.student_number = scw.student_number
left join
    {{ ref("int_powerschool__spenrollments") }} as sp
    on enr.studentid = sp.studentid
    and enr.exitdate between sp.enter_date and sp.exit_date
    and sp.is_self_contained
left join
    {{ ref("int_powerschool__spenrollments") }} as ood
    on enr.studentid = ood.studentid
    and enr.exitdate between ood.enter_date and ood.exit_date
    and ood.is_out_of_district
