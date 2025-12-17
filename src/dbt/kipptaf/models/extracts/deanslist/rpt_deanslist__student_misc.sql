select
    co._dbt_source_relation,
    co.studentid,
    co.student_number,
    co.state_studentnumber as `SID`,
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
    co.sched_nextyeargrade,
    co.salesforce_contact_owner_name as ktc_counselor_name,
    co.salesforce_contact_owner_phone as ktc_counselor_phone,
    co.salesforce_contact_owner_email as ktc_counselor_email,
    co.student_email,
    co.school_principal as principal,
    co.school_phone as schoolphone,
    co.school_assistant_principal as culture_lead,

    gpa.`GPA_Y1`,
    gpa.gpa_term,

    concat(co.student_web_id, '.fam') as family_access_id,
    concat(co.student_web_password, 'kipp') as student_web_password,
    concat(co.street, ', ', co.city, ', ', co.state, ' ', co.zip) as home_address,

    if(
        co.schoolid = 999999,
        max(if(co.rn_undergrad = 1 and co.grade_level != 99, co.schoolid, null)) over (
            partition by co._dbt_source_relation, co.studentid, co.schoolid
        ),
        co.schoolid
    ) as schoolid,

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

    case
        when co.region = 'Camden'
        then 'kippcamden@kippnj.org'
        when co.region = 'Newark'
        then 'kippnewark@kippnj.org'
    end as regional_email,

    case
        when co.region = 'Camden'
        then '973-622-0905 ext. 31003'
        when co.region = 'Newark'
        then '973-622-0905 ex 11200'
    end as regional_phone,

    min(co.entrydate) over (
        partition by co._dbt_source_relation, co.studentid, co.schoolid
    ) as school_entrydate,

    max(co.exitdate) over (
        partition by co._dbt_source_relation, co.studentid, co.schoolid
    ) as school_exitdate,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
    and gpa.is_current
where co.academic_year = {{ var("current_academic_year") }} and co.rn_year = 1
