select
    localstudentidentifier,
    assessmentyear as academic_year,
    academic_year as academic_year_int,
    `period` as test_round,
    assessment_name as test_type,
    discipline as `subject`,
    `subject` as test_name,
    testscalescore as scale_score,
    testperformancelevel_text as proficiency_level,

    if(is_proficient, 1, 0) as is_proficient,

    concat(testperformancelevel_text, ' (', testscalescore, ')') as score_display,

    row_number() over (
        partition by localstudentidentifier, `subject` order by assessmentyear asc
    ) as test_index,
from {{ ref("int_pearson__all_assessments") }}

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

    concat(fl.achievement_level, ' (', fl.scale_score, ')') as score_display,

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
