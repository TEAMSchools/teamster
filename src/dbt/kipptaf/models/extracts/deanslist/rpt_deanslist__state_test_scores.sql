select
    co.student_number,

    p.assessmentyear as academic_year,
    p.academic_year as academic_year_int,
    p.period as test_round,
    p.assessment_name as test_type,
    p.discipline as `subject`,
    p.subject as test_name,
    p.testscalescore as scale_score,
    p.testperformancelevel_text as proficiency_level,

    if(p.is_proficient, 1, 0) as is_proficient,

    row_number() over (
        partition by co.student_number, p.subject order by p.assessmentyear asc
    ) as test_index,
from {{ ref("stg_powerschool__students") }} as co
inner join
    {{ ref("int_pearson__all_assessments") }} as p
    on co.state_studentnumber = p.statestudentidentifier

union all

select
    co.student_number,

    concat(
        cast(fl.academic_year as string), '-', cast(fl.academic_year + 1 as string)
    ) as academic_year,
    fl.academic_year as academic_year_int,
    fl.administration_window as test_round,
    'FAST' as test_type,
    fl.discipline as `subject`,
    fl.assessment_subject as test_name,
    fl.scale_score,
    fl.achievement_level as proficiency_level,

    if(fl.is_proficient, 1, 0) as is_proficient,

    row_number() over (
        partition by co.student_number, fl.assessment_subject
        order by fl.academic_year asc, fl.administration_window asc
    ) as test_index,
from {{ ref("stg_powerschool__students") }} as co
inner join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on co.dcid = suf.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="suf") }}
inner join {{ ref("stg_fldoe__fast") }} as fl on suf.fleid = fl.student_id
