with
    scored as (
        select
            localstudentidentifier as student_number,
            academic_year,
            assessment_name,
            subject,
            test_grade,
            testscalescore,
            studenttestuuid,

            case
                when subject in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'm'
                when subject = 'English Language Arts'
                then 'r'
            end as subject_family,

            case assessment_name when 'NJSLA' then 1 else 2 end as source_rank,
        from {{ ref("int_pearson__all_assessments") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and subject in (
                'Mathematics',
                'Algebra I',
                'Algebra II',
                'Geometry',
                'English Language Arts'
            )
            and localstudentidentifier is not null
    ),

    accommodations as (
        select
            studenttestuuid, uniqueaccommodation, mlaccommodation, iepexemptfrompassing,
        from {{ ref("stg_pearson__njsla") }}
        where academic_year in ({{ var("ignite_academic_years") | join(", ") }})
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    with_accommodations as (
        select
            s.student_number,
            s.academic_year,
            s.assessment_name,
            s.subject,
            s.test_grade,
            s.testscalescore,
            s.subject_family,
            s.source_rank,

            ac.uniqueaccommodation,
            ac.mlaccommodation,
            ac.iepexemptfrompassing,
        from scored as s
        left join accommodations as ac on s.studenttestuuid = ac.studenttestuuid
        where s.subject_family is not null
    ),

    /* A student can sit both an NJSLA end-of-course maths test and NJGPA in one
     year, but Mathematica's template holds a single score per subject family.
     NJSLA wins because it is the state summative assessment their request
     describes; NJGPA is a graduation proficiency test. */
    picked as (
        {{
            dbt_utils.deduplicate(
                relation="with_accommodations",
                partition_by="student_number, academic_year, subject_family",
                order_by="source_rank asc, subject asc",
            )
        }}
    ),

    flagged as (
        select
            student_number,
            academic_year,
            subject_family,
            assessment_name,
            test_grade,
            testscalescore,

            if(
                subject in ('Algebra I', 'Algebra II', 'Geometry'), subject, null
            ) as eoc_subject,

            case
                when uniqueaccommodation = 'Y'
                then 1
                when mlaccommodation = 'Y'
                then 1
                else 0
            end as accom,

            case when iepexemptfrompassing = 'Y' then 1 else 0 end as exemption,
        from picked
    )

select
    student_number,
    academic_year,

    max(if(subject_family = 'm', testscalescore, null)) as test_score_m,
    max(if(subject_family = 'm', test_grade, null)) as test_grd_m,
    max(if(subject_family = 'm', eoc_subject, null)) as test_subj_m_eoc,
    max(if(subject_family = 'm', assessment_name, null)) as test_name_m,
    max(if(subject_family = 'm', accom, null)) as accom_m,
    max(if(subject_family = 'm', exemption, null)) as exemption_m,

    max(if(subject_family = 'r', testscalescore, null)) as test_score_r,
    max(if(subject_family = 'r', test_grade, null)) as test_grd_r,
    max(if(subject_family = 'r', eoc_subject, null)) as test_subj_r_eoc,
    max(if(subject_family = 'r', assessment_name, null)) as test_name_r,
    max(if(subject_family = 'r', accom, null)) as accom_r,
    max(if(subject_family = 'r', exemption, null)) as exemption_r,
from flagged
group by student_number, academic_year
