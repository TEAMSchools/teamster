select
    co.student_number,

    p.assessmentyear as academic_year,
    p.assessment_name as test_type,
    p.subject_area as subject,
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
