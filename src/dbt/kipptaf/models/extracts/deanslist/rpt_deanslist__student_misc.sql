with
    ug_school as (
        select studentid, schoolid, _dbt_source_relation,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_undergrad = 1 and grade_level != 99
    ),

    enroll_dates as (
        select
            studentid,
            schoolid,
            _dbt_source_relation,
            min(entrydate) as school_entrydate,
            max(exitdate) as school_exitdate,
        from {{ ref("base_powerschool__student_enrollments") }}
        group by studentid, schoolid, _dbt_source_relation
    ),

    students as (
        select
            co.studentid,
            co.student_number,
            co.state_studentnumber as sid,
            co.advisory_name as team,
            co.home_phone,
            co.contact_1_name as parent1_name,
            co.contact_2_name as parent2_name,
            co.contact_1_email_current as guardianemail,
            co.academic_year,
            co.contact_1_phone_mobile as parent1_cell,
            co.contact_2_phone_mobile as parent2_cell,
            co.advisor_lastfirst as advisor_name,
            co.advisor_email,
            co.lunch_balance,
            co.dob,
            co._dbt_source_relation,
            co.student_web_id || '.fam' as family_access_id,
            co.student_web_id || '@teamstudents.org' as student_email,
            concat(co.student_web_password, 'kipp') as student_web_password,
            concat(
                co.street, ', ', co.city, ', ', co.state, ' ', co.zip
            ) as home_address,
            case
                co.enroll_status
                when -1
                then 'Pre-Registered'
                when 0
                then 'Enrolled'
                when 1
                then 'Inactive'
                when 2
                then 'Transferred Out'
                when 3
                then 'Graduated'
            end as enroll_status,

            s.sched_nextyeargrade,

            ktc.contact_owner_name as ktc_counselor_name,
            ktc.contact_owner_phone as ktc_counselor_phone,
            ktc.contact_owner_email as ktc_counselor_email,

            gpa.gpa_y1,
            gpa.gpa_term,

            if(co.schoolid = 999999, ug.schoolid, co.schoolid) as schoolid,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on co.studentid = s.id
            and {{ union_dataset_join_clause(left_alias="co", right_alias="s") }}
        inner join
            ug_school as ug
            on co.studentid = ug.studentid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="ug") }}
        left join
            {{ ref("int_kippadb__roster") }} as ktc
            on co.student_number = ktc.student_number
        left join
            {{ ref("int_powerschool__gpa_term") }} as gpa
            on co.studentid = gpa.studentid
            and co.yearid = gpa.yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
            and gpa.is_current
        where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
    )

select co.*, ed.school_entrydate, ed.school_exitdate,
from students as co
left join
    enroll_dates as ed
    on co.studentid = ed.studentid
    and co.schoolid = ed.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ed") }}
