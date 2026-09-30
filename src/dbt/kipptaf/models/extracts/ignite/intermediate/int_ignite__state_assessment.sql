with
    pearson_scored as (
        select
            localstudentidentifier as student_number,
            academic_year,
            assessment_name,
            subject,
            test_grade,
            testscalescore as scale_score,
            studenttestuuid,
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

    pearson_accommodations as (
        select
            studenttestuuid, uniqueaccommodation, mlaccommodation, iepexemptfrompassing,
        from {{ ref("stg_pearson__njsla") }}
        where academic_year in ({{ var("ignite_academic_years") | join(", ") }})
    ),

    pearson as (
        select
            ps.student_number,
            ps.academic_year,
            ps.assessment_name,
            ps.subject,
            ps.test_grade,
            ps.scale_score,

            ac.uniqueaccommodation,
            ac.mlaccommodation,
            ac.iepexemptfrompassing,
        from pearson_scored as ps
        left join
            pearson_accommodations as ac on ps.studenttestuuid = ac.studenttestuuid
    ),

    /* Cambium replaced Pearson as New Jersey's vendor. Its file DOES carry
     unique_accommodation, ml_accommodation and iep_exempt_from_passing, but
     stg_cambium__njsla projects 28 of the file's 228 columns and does not
     include them, so they cannot be read here yet. Padded null rather than
     defaulted, because null is the honest value for "not available to this
     model" — see the TODO below.
     TODO(#4753): stage the three columns through the cambium package and
     int_cambium__all_assessments, then read them here. 33 IGNITE students in
     SY2025-2026 carry ml_accommodation = 'Y' and are reported null today.
     Note iep_exempt_from_passing is NOT the Pearson Y/N flag: Cambium uses
     N plus the codes B, E and M, so a '= Y' test would never fire. */
    cambium as (
        select
            student_number,
            academic_year,
            assessment_name,
            aligned_subject as subject,
            test_grade,
            scale_score,

            cast(null as string) as uniqueaccommodation,
            cast(null as string) as mlaccommodation,
            cast(null as string) as iepexemptfrompassing,
        from {{ ref("int_cambium__all_assessments") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and aligned_subject in (
                'Mathematics',
                'Algebra I',
                'Algebra II',
                'Geometry',
                'English Language Arts'
            )
            and student_number is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    classified as (
        select
            student_number,
            academic_year,
            assessment_name,
            subject,
            test_grade,
            scale_score,
            uniqueaccommodation,
            mlaccommodation,
            iepexemptfrompassing,

            case
                when subject in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'm'
                when subject = 'English Language Arts'
                then 'r'
            end as subject_family,

            case assessment_name when 'NJSLA' then 1 else 2 end as source_rank,
        from pearson

        union all

        select
            student_number,
            academic_year,
            assessment_name,
            subject,
            test_grade,
            scale_score,
            uniqueaccommodation,
            mlaccommodation,
            iepexemptfrompassing,

            case
                when subject in ('Mathematics', 'Algebra I', 'Algebra II', 'Geometry')
                then 'm'
                when subject = 'English Language Arts'
                then 'r'
            end as subject_family,

            case assessment_name when 'NJSLA' then 1 else 2 end as source_rank,
        from cambium
    ),

    /* A student can sit both an NJSLA end-of-course maths test and NJGPA in one
     year, but Mathematica's template holds a single score per subject family.
     NJSLA wins because it is the state summative assessment their request
     describes; NJGPA is a graduation proficiency test. */
    picked as (
        {{
            dbt_utils.deduplicate(
                relation="classified",
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
            scale_score,

            if(
                subject in ('Algebra I', 'Algebra II', 'Geometry'), subject, null
            ) as eoc_subject,

            case
                when uniqueaccommodation = 'Y'
                then 1
                when mlaccommodation = 'Y'
                then 1
                when uniqueaccommodation is null and mlaccommodation is null
                then null
                else 0
            end as accom,

            case
                when iepexemptfrompassing = 'Y'
                then 1
                when iepexemptfrompassing is null
                then null
                else 0
            end as exemption,
        from picked
    )

select
    student_number,
    academic_year,

    max(if(subject_family = 'm', scale_score, null)) as test_score_m,
    max(if(subject_family = 'm', test_grade, null)) as test_grd_m,
    max(if(subject_family = 'm', eoc_subject, null)) as test_subj_m_eoc,
    max(if(subject_family = 'm', assessment_name, null)) as test_name_m,
    max(if(subject_family = 'm', accom, null)) as accom_m,
    max(if(subject_family = 'm', exemption, null)) as exemption_m,

    max(if(subject_family = 'r', scale_score, null)) as test_score_r,
    max(if(subject_family = 'r', test_grade, null)) as test_grd_r,
    max(if(subject_family = 'r', eoc_subject, null)) as test_subj_r_eoc,
    max(if(subject_family = 'r', assessment_name, null)) as test_name_r,
    max(if(subject_family = 'r', accom, null)) as accom_r,
    max(if(subject_family = 'r', exemption, null)) as exemption_r,
from flagged
group by student_number, academic_year
