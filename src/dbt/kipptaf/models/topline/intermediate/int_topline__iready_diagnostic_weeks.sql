select
    ir.student_id as student_number,
    ir.schoolid,
    ir.test_round,
    ir.is_proficient,

    subj as subject,

    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
from {{ ref("int_powerschool__calendar_week") }} as cw
cross join unnest(['Reading', 'Math']) as subj
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region_expanded = rt.region
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'IREX'
left join
    {{ ref("base_iready__diagnostic_results") }} as ir
    on rt.academic_year = ir.academic_year_int
    and rt.name = ir.test_round
    and rt.region = ir.region
    and subj = ir.subject
    and ir.rn_subj_round = 1
