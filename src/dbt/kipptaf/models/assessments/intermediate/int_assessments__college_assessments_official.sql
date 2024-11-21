with
    student_id_crosswalk as (
        select distinct
            e._dbt_source_relation,
            e.studentid,
            e.students_dcid,
            e.student_number,
            e.state_studentnumber,
            e.fleid,
            e.infosnap_id,

            a.contact_id,

            i.student_id as illuminate_id,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("int_kippadb__roster") }} as a on e.student_number = a.student_number
        left join
            {{ ref("stg_illuminate__students") }} as i
            on e.student_number = i.local_student_id
        where e.grade_level between 9 and 12 and e.rn_year = 1
    ),

    int_college_assessments as (
        select
            contact,
            test_type as scope,
            date as test_date,
            score as scale_score,
            score_type,

            'Official' as test_type,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            case
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                else test_subject
            end as subject_area,
            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ENG'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            {{
                date_to_fiscal_year(
                    date_field="date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'act_english',
                'act_science',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )

        union all

        select
            safe_cast(local_student_id as string) as contact,

            'PSAT' as scope,

            test_date,
            score as scale_score,
            score_type,

            'Official' as test_type,

            concat(
                format_date('%b', test_date), ' ', format_date('%g', test_date)
            ) as administration_round,

            case
                score_type
                when 'psat_total_score'
                then 'Composite'
                when 'psat_reading_test_score'
                then 'Reading'
                when 'psat_math_test_score'
                then 'Math Test'
                when 'psat_math_section_score'
                then 'Math'
                when 'psat_eb_read_write_section_score'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when
                    score_type
                    in ('psat_eb_read_write_section_score', 'psat_reading_test_score')
                then 'ENG'
                when score_type in ('psat_math_test_score', 'psat_math_section_score')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            academic_year as test_academic_year,
        from {{ ref("int_illuminate__psat_unpivot") }}
        where
            score_type in (
                'psat_eb_read_write_section_score',
                'psat_math_section_score',
                'psat_math_test_score',
                'psat_reading_test_score',
                'psat_total_score'
            )
    )

select
    c.test_academic_year,
    c.contact,
    c.test_type,
    c.scope,
    c.score_type,
    c.subject_area,
    c.course_discipline,
    c.administration_round,
    c.test_date,
    c.scale_score,

    s.student_number,
from int_college_assessments as c
left join student_id_crosswalk as s on c.contact = s.contact_id
where c.scope != 'PSAT'
