with
    suspension as (
        select
            ics._dbt_source_relation,
            ics.student_school_id,
            ics.create_ts_academic_year,

            count(ips.incident_penalty_id) as suspension_count,
            sum(ips.num_days) as suspension_days,
        from {{ ref("stg_deanslist__incidents") }} as ics
        inner join
            {{ ref("stg_deanslist__incidents__penalties") }} as ips
            on ips.incident_id = ics.incident_id
            and ips._dbt_source_relation = ics._dbt_source_relation
        where ips.is_suspension
        group by
            ics.student_school_id, ics.create_ts_academic_year, ics._dbt_source_relation
    )

select
    co.studentid,
    co.student_number,
    co.lastfirst,
    co.dob,
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.reporting_schoolid,
    co.school_name,
    co.grade_level,
    co.cohort,
    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.spedlep as iep_status,
    co.lep_status,
    co.is_504 as c_504_status,
    co.gender,
    co.ethnicity,
    co.enroll_status,
    co.is_retained_year,
    co.is_retained_ever,
    co.year_in_network,
    co.code_location as `db_name`,
    co.boy_status,

    dt.name as term_name,
    dt.code as reporting_term,
    dt.start_date as term_start_date,
    dt.end_date as term_end_date,
    dt.is_current as is_curterm,

    gr.course_number,
    gr.potential_credit_hours as credit_hours,
    gr.term_percent_grade_adjusted as term_grade_percent_adjusted,
    gr.term_letter_grade_adjusted as term_grade_letter_adjusted,
    gr.y1_percent_grade_adjusted as y1_grade_percent_adjusted,
    gr.y1_letter_grade as y1_grade_letter,
    gr.need_60 as need_65,

    si.courses_credittype as credittype,
    si.courses_course_name as course_name,
    si.teacher_lastfirst as teacher_name,

    gpa.gpa_y1,
    gpa.gpa_y1_unweighted,
    gpa.gpa_term,

    gpc.cumulative_y1_gpa,
    gpc.cumulative_y1_gpa_projected,
    gpc.earned_credits_cum,
    gpc.earned_credits_cum_projected,
    gpc.potential_credits_cum,

    att.`ada`,

    sus.suspension_count,
    sus.suspension_days,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_reporting__terms") }} as dt
    on co.academic_year = dt.academic_year
    and co.schoolid = dt.school_id
    and dt.type = 'RT'
    and dt.name not in ('Summer School', 'Y1')
left join
    {{ ref("base_powerschool__final_grades") }} as gr
    on co.studentid = gr.studentid
    and co.yearid = gr.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gr") }}
    and dt.name = gr.storecode
    and gr.exclude_from_gpa = 0
left join
    {{ ref("base_powerschool__sections") }} as si
    on gr.sectionid = si.sections_id
    and {{ union_dataset_join_clause(left_alias="gr", right_alias="si") }}
left join
    {{ ref("int_powerschool__gpa_term") }} as gpa
    on co.studentid = gpa.studentid
    and co.yearid = gpa.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
    and dt.name = gpa.term_name
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpc
    on co.studentid = gpc.studentid
    and co.schoolid = gpc.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpc") }}
left join
    {{ ref("int_powerschool__ada") }} as att
    on co.studentid = att.studentid
    and co.yearid = att.yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="att") }}
left join
    suspension as sus
    on co.student_number = sus.student_school_id
    and co.academic_year = sus.create_ts_academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="sus") }}
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.is_enrolled_recent
    and co.school_level = 'HS'
