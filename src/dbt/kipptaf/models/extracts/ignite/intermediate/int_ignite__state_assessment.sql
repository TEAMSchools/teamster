{#-
 Discretionary testing accommodations. text_to_speech is deliberately absent:
 New Jersey grants it universally to any student testing on a computer without
 a conflicting accommodation, so it records the test delivery mode rather than
 a decision made about a student, and counting it would mark most of the cohort
 accommodated. Confirmed by KTAF on 2026-09-30.
-#}
{%- set pearson_accommodation_columns = [
    "extendedtime",
    "frequentbreaks",
    "smallgrouptesting",
    "uniqueaccommodation",
    "mlaccommodation",
    "elaccommodation",
    "administrationdirectionsreadaloudinstudentsnativelanguage",
    "braillewithtactilegraphics",
    "electronicbrailleresponse",
    "refreshablebrailledisplay",
    "multilinguallearneraccommodatedresponse",
] -%}

{#-
 The same file types three accommodation fields as numbers rather than the
 Y/N strings its other accommodation fields use, so they need their own test.
-#}
{%- set pearson_accommodation_columns_numeric = [
    "emergencyaccommodation",
    "englishlearneraccommodatedresponses",
    "mathematicsscienceaccommodatedresponse",
] -%}

{#-
 Mathematica defines exemption_* as exemption from TAKING a test or a test
 found invalid, which is what the void-score and exempt-from-taking fields
 record. iepexemptfrompassing is a different concept -- exemption from the
 graduation passing requirement -- and is deliberately not read here.
-#}
{%- set pearson_exemption_columns = [
    "voidscorecode",
    "mlexemptfromtakingela",
    "elexemptfromtakingela",
] -%}

with
    pearson_scored as (
        select
            pa.assessment_name,
            pa.subject,
            pa.test_grade,
            pa.testscalescore as scale_score,
            pa.studenttestuuid,

            sy.student_number,
            sy.academic_year,
        from {{ ref("int_pearson__all_assessments") }} as pa
        inner join
            {{ ref("int_ignite__student_years") }} as sy
            on pa.localstudentidentifier = sy.student_number
            and pa.academic_year = sy.academic_year
        where
            pa.subject in (
                'Mathematics',
                'Algebra I',
                'Algebra II',
                'Geometry',
                'English Language Arts'
            )
    ),

    pearson_accommodations as (
        select
            nj.studenttestuuid,

            case
                when
                    {%- for col in pearson_accommodation_columns %}
                        coalesce(nj.{{ col }}, 'N') != 'N' or
                    {%- endfor %}
                    {%- for col in pearson_accommodation_columns_numeric %}
                        coalesce(nj.{{ col }}, 0) != 0
                        {%- if not loop.last %} or {% endif %}
                    {%- endfor %}
                then 1
                else 0
            end as accom,

            case
                when
                    {%- for col in pearson_exemption_columns %}
                        coalesce(nj.{{ col }}, 'N') != 'N'
                        {%- if not loop.last %} or {% endif %}
                    {%- endfor %}
                then 1
                else 0
            end as exemption,
        from {{ ref("stg_pearson__njsla") }} as nj
        inner join pearson_scored as ps on nj.studenttestuuid = ps.studenttestuuid
    ),

    pearson as (
        select
            ps.student_number,
            ps.academic_year,
            ps.assessment_name,
            ps.subject,
            ps.test_grade,
            ps.scale_score,

            ac.accom,
            ac.exemption,
        from pearson_scored as ps
        left join
            pearson_accommodations as ac on ps.studenttestuuid = ac.studenttestuuid
    ),

    /* The Cambium file DOES carry accommodation columns -- roughly thirty of
     them, individually named -- but stg_cambium__njsla projects 28 of the
     file's 228 and does not include any, so they cannot be read here. Padded
     null rather than zero, because null says "not available to this model"
     where zero would assert the student had no accommodation.
     TODO(#4753): stage them through the cambium package and
     int_cambium__all_assessments, then read them here. Excluding text-to-speech
     as universal, 144 of the 901 IGNITE students on the SY2025-2026 NJSLA carry
     at least one accommodation and are reported null today. Three traps when
     wiring it: the columns do not share value semantics, so a blanket not-null
     test is wrong (speech_to_text_and_word_prediction is 'N' or 'S' on every
     row while its neighbours are null-or-set); iep_exempt_from_passing is about
     the graduation passing requirement, not exemption from sitting the test, so
     not_tested_code and void_score_code are the fields Mathematica's exemption_*
     describes; and math accommodations for this cohort live in the EOC file,
     not this one. This affects phase 2 only -- phase 1 is the Pearson year. */
    cambium as (
        select
            ca.student_number,
            ca.academic_year,
            ca.assessment_name,
            ca.aligned_subject as subject,
            ca.test_grade,
            ca.scale_score,

            cast(null as int64) as accom,
            cast(null as int64) as exemption,
        from {{ ref("int_cambium__all_assessments") }} as ca
        inner join
            {{ ref("int_ignite__student_years") }} as sy
            on ca.student_number = sy.student_number
            and ca.academic_year = sy.academic_year
        where
            ca.aligned_subject in (
                'Mathematics',
                'Algebra I',
                'Algebra II',
                'Geometry',
                'English Language Arts'
            )
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
            accom,
            exemption,

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
            accom,
            exemption,

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
            accom,
            exemption,

            if(
                subject in ('Algebra I', 'Algebra II', 'Geometry'), subject, null
            ) as eoc_subject,
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
