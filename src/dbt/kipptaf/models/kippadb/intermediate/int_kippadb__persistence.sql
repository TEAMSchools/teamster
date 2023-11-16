with
    roster_scaffold as (
        select
            r.student_number,
            r.contact_id,
            r.lastfirst,
            r.ktc_cohort,
            r.ktc_status,
            r.contact_kipp_region_name,
            r.contact_current_kipp_student,
            r.contact_dep_post_hs_simple_admin,
            r.contact_college_match_display_gpa,
            r.contact_current_college_cumulative_gpa,
            r.contact_current_college_semester_gpa,
            r.contact_highest_act_score,
            r.contact_middle_school_attended,

            r.ktc_cohort + n as academic_year,
        from {{ ref("int_kippadb__roster") }} as r
        cross join unnest([0, 1, 2, 3, 4, 5]) as n
    )

select
    r.student_number,
    r.contact_id as sf_contact_id,
    r.lastfirst,
    r.ktc_cohort,
    r.ktc_status,
    r.academic_year,
    r.contact_kipp_region_name as kipp_region_name,
    r.contact_current_kipp_student as current_kipp_student,
    r.contact_dep_post_hs_simple_admin as post_hs_simple_admin,
    r.contact_college_match_display_gpa as college_match_display_gpa,
    r.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
    r.contact_current_college_semester_gpa as current_college_semester_gpa,
    r.contact_highest_act_score as highest_act_score,
    r.contact_middle_school_attended as middle_school_attended,

    e.id as enrollment_id,
    e.pursuing_degree_type as pursuing_degree_type,
    e.status as enrollment_status,
    e.start_date as start_date,
    e.actual_end_date as actual_end_date,

    a.name as account_name,
    a.type as account_type,

    case
        when date(r.academic_year, 10, 31) > current_date('{{ var("local_timezone") }}')
        then null
        when e.actual_end_date >= date(r.academic_year, 10, 31)
        then 1
        when
            e.actual_end_date < date(r.academic_year, 10, 31) and e.status = 'Graduated'
        then 1
        when
            e.actual_end_date is null and eis.ugrad_status in ('Graduated', 'Attending')
        then 1
        else 0
    end as is_persisting_fall,

    case
        when
            date(r.academic_year + 1, 3, 31)
            > current_date('{{ var("local_timezone") }}')
        then null
        when e.actual_end_date >= date(r.academic_year + 1, 3, 31)
        then 1
        when
            e.actual_end_date < date(r.academic_year + 1, 3, 31)
            and e.status = 'Graduated'
        then 1
        when
            e.actual_end_date is null and eis.ugrad_status in ('Graduated', 'Attending')
        then 1
        else 0
    end as is_persisting_spring,

from roster_scaffold as r
left join
    {{ ref("stg_kippadb__enrollment") }} as e
    on r.contact_id = e.student
    and date(r.academic_year, 10, 31) between e.start_date and coalesce(
        e.actual_end_date, date(({{ var("current_academic_year") }} + 1), 6, 30)
    )
    and e.pursuing_degree_type in ("Bachelor's (4-year)", "Associate's (2 year)")
    and e.status not in ('Did Not Enroll', 'Deferred')
left join {{ ref("stg_kippadb__account") }} as a on e.school = a.id
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as eis on r.contact_id = eis.student
