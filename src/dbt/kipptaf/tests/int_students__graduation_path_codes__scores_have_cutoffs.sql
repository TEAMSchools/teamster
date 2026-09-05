with
    njgpa_scores as (
        select
            e.cohort,
            e.discipline,

            n.testcode as score_type,
            n.assessment_version,

            count(distinct e.student_number) as students,
        from {{ ref("int_extracts__student_enrollments_subjects") }} as e
        inner join
            {{ ref("int_pearson__all_assessments") }} as n
            on e.student_number = n.localstudentidentifier
            and e.discipline = n.discipline
        where
            e.rn_undergrad = 1
            and e.region != 'Miami'
            and e.grade_level >= 8
            and e.enroll_status = 0
            and n.assessment_name = 'NJGPA'
            and n.testcode in ('ELAGP', 'MATGP')
        group by e.cohort, e.discipline, n.testcode, n.assessment_version
    )

select s.cohort, s.discipline, s.score_type, s.assessment_version, s.students,
from njgpa_scores as s
left join
    {{ ref("stg_google_sheets__student_graduation_path_cutoffs") }} as c
    on s.cohort = c.cohort
    and s.discipline = c.discipline
    and s.score_type = c.score_type
    and s.assessment_version = c.assessment_version
where c.cutoff is null
