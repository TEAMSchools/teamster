select
    cw.student_number,
    cw.state_studentnumber,
    cw.student_name,
    cw.academic_year,
    cw.iready_subject,
    cw.discipline,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
    cw.region,
    cw.school_level,
    cw.schoolid,
    cw.school,
    cw.grade_level,
    cw.gender,
    cw.ethnicity,
    cw.iep_status,
    cw.is_504,
    cw.lep_status,
    cw.gifted_and_talented,
    cw.entrydate,
    cw.exitdate,
    cw.enroll_status,

    rt.name as test_round,

    ir.subject,

    case
        when ir.is_proficient then 1 when not ir.is_proficient then 0
    end as is_proficient,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'IREX'
left join
    {{ ref("base_iready__diagnostic_results") }} as ir
    on cw.student_number = ir.student_id
    and cw.academic_year = ir.academic_year_int
    and cw.iready_subject = ir.subject
    and {{ union_dataset_join_clause(left_alias="cw", right_alias="ir") }}
    and rt.region = ir.region
    and rt.name = ir.test_round
    and ir.rn_subj_round = 1
