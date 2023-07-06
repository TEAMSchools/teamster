{% set invalid_lunch_status = ["", "NoD", "1", "2"] %}
{%- set self_contained_specprog_names = [
    "Self-Contained Special Education",
    "Pathways ES",
    "Pathways MS",
] -%}

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
            s.track,

            terms.yearid,

            x1.exit_code as exit_code_kf,
            x2.exit_code as exit_code_ts,
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
            re.studentid as studentid,

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
            re.track,

            terms.yearid,

            x1.exit_code as exit_code_kf,
            x2.exit_code as exit_code_ts,
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
            null as track,

            terms.yearid,

            null as exit_code_kf,
            null as exit_code_ts,
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
            studentid,
            students_dcid,
            student_number,
            schoolid,
            grade_level,
            entrydate,
            exitdate,
            entrycode,
            exitcode,
            exit_code_kf,
            exit_code_ts,
            exitcomment,
            fteid,
            yearid,
            (yearid + 1990) as academic_year,
            ifnull(track, 'A') as track,
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

    enr_order_window as (
        select
            studentid,
            students_dcid,
            student_number,
            yearid,
            academic_year,
            schoolid,
            grade_level,
            entrydate,
            exitdate,
            entrycode,
            exitcode,
            exit_code_kf,
            exit_code_ts,
            exitcomment,
            fteid,
            track,
            lunch_status,
            rn_year,
            rn_school,
            rn_all,
            if(grade_level != 99, rn_undergrad, null) as rn_undergrad,

            min(grade_level_prev) over (
                partition by studentid, yearid
            ) as grade_level_prev,

            if(
                rn_year > 1,
                null,
                row_number() over (
                    partition by studentid, schoolid, rn_year
                    order by yearid asc, exitdate asc
                )
            ) as year_in_school,
            if(
                rn_year > 1,
                null,
                row_number() over (
                    partition by studentid, rn_year order by yearid asc, exitdate asc
                )
            ) as year_in_network,

            case
                when yearid = min(yearid_prev) over (partition by studentid, yearid)
                then false
                when
                    grade_level != 99
                    and grade_level
                    <= min(grade_level_prev) over (partition by studentid, yearid)
                then true
                else false
            end as is_retained_year
        from enr_order
    )

select
    enr.studentid,
    enr.students_dcid,
    enr.student_number,
    enr.yearid,
    enr.academic_year,
    enr.schoolid,
    enr.grade_level,
    enr.grade_level_prev,
    enr.entrydate,
    enr.exitdate,
    enr.entrycode,
    enr.exitcode,
    enr.exit_code_kf,
    enr.exit_code_ts,
    enr.exitcomment,
    enr.track,
    enr.lunch_status,
    enr.fteid,
    enr.is_retained_year,
    enr.rn_year,
    enr.rn_school,
    enr.rn_all,
    enr.rn_undergrad,
    max(enr.is_retained_year) over (partition by enr.studentid) as is_retained_ever,
    max(enr.year_in_school) over (
        partition by enr.studentid, enr.academic_year
    ) as year_in_school,
    max(enr.year_in_network) over (
        partition by enr.studentid, enr.academic_year
    ) as year_in_network,
    min(if(enr.year_in_network = 1, enr.schoolid, null)) over (
        partition by enr.studentid
    ) as entry_schoolid,
    min(if(enr.year_in_network = 1, enr.grade_level, null)) over (
        partition by enr.studentid
    ) as entry_grade_level,
    case
        when enr.grade_level = 99
        then
            max(
                if(
                    enr.exitcode = 'G1',
                    enr.yearid + 2003 + (-1 * enr.grade_level),
                    null
                )
            ) over (partition by enr.studentid)
        when enr.grade_level >= 9
        then
            max(
                if(
                    enr.year_in_school = 1,
                    enr.yearid + 2003 + (-1 * enr.grade_level),
                    null
                )
            ) over (partition by enr.studentid, enr.schoolid)
        else enr.yearid + 2003 + (-1 * enr.grade_level)
    end as cohort,

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
    s.grade_level as highest_grade_level_achieved,
    left(upper(s.gender), 1) as gender,
    left(upper(s.ethnicity), 1) as ethnicity,

    sch.name as school_name,
    sch.abbreviation as school_abbreviation,

    adv.advisory_name,
    adv.advisor_teachernumber,
    adv.advisor_lastfirst,

    scw.contact_1_name,
    scw.contact_1_phone_home,
    scw.contact_1_phone_mobile,
    scw.contact_1_phone_daytime,
    scw.contact_1_email_current,
    scw.contact_2_name,
    scw.contact_2_phone_home,
    scw.contact_2_phone_mobile,
    scw.contact_2_phone_daytime,
    scw.contact_2_email_current,

    if(
        sp.specprog_name in unnest({{ self_contained_specprog_names }}), true, false
    ) as is_self_contained,

    if(ood.dcid is not null, true, false) as is_out_of_district,

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

    max(if(enr.exitdate is not null, true, false)) over (
        partition by enr.studentid, enr.yearid
    ) as is_enrolled_y1,
    max(
        if(
            date(enr.academic_year, 10, 1) between enr.entrydate and enr.exitdate,
            true,
            false
        )
    ) over (partition by enr.studentid, enr.yearid) as is_enrolled_oct01,
    max(
        if(
            date(enr.academic_year, 10, 15) between enr.entrydate and enr.exitdate,
            true,
            false
        )
    ) over (partition by enr.studentid, enr.yearid) as is_enrolled_oct15,
    max(
        case
            when enr.exitdate >= cr.max_calendardate
            then true
            when current_date('America/New_York') between enr.entrydate and enr.exitdate
            then true
            else false
        end
    ) over (partition by enr.studentid, enr.yearid) as is_enrolled_recent,
from enr_order_window as enr
inner join {{ ref("stg_powerschool__students") }} as s on enr.studentid = s.id
inner join
    {{ ref("stg_powerschool__schools") }} as sch on enr.schoolid = sch.school_number
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
    and sp.specprog_name in unnest({{ self_contained_specprog_names }})
left join
    {{ ref("int_powerschool__spenrollments") }} as ood
    on enr.studentid = ood.studentid
    and enr.exitdate between ood.enter_date and ood.exit_date
    and ood.specprog_name = 'Out of District'
left join
    {{ ref("int_powerschool__calendar_rollup") }} as cr
    on enr.schoolid = cr.schoolid
    and enr.yearid = cr.yearid
    and enr.track = cr.track
