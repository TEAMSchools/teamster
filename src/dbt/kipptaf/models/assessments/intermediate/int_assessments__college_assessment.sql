with
    -- any possibility we can make a new view or table where we have one master list
    -- of all the ids a student can have: student_number, studentid, contact,
    -- illuminate_id, cb_id, state_id, google email, fl_id - reasoning: as we build up
    -- our assessment data model for all the dashboards and for the incoming request
    -- of the "one dash to track all the goals", it would be useful to be able to use
    -- a simple id table to create a master table with all the data this new dashboard
    -- will need, especially since there isnt an aligned student identifier for the
    -- different assessment options unless we force it (and google classroom data
    -- incoming too)
    id_table as (
        select
            _dbt_source_relation,
            academic_year,
            student_number,
            salesforce_id,
            grade_level,
        from {{ ref("int_extracts__student_enrollments") }}
    ),

    -- this is by itself because the int_kippadb__standardized_test_unpivot view uses
    -- contact id
    test_scores as (
        select
            contact,
            test_type as scope,
            score_type,
            date as test_date,
            score as scale_score,

            'Official' as test_type,

            case
                score_type
                when 'sat_total_score'
                then 'Combined'
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

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            if(
                extract(month from date) >= 7,
                extract(year from date),
                extract(year from date) - 1

            ) as test_academic_year,

            row_number() over (
                partition by contact, test_type, score_type order by score desc
            ) as rn_highest,

        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )
            and date is not null

        union all

        -- this is by itself because the int_kippadb__standardized_test_unpivot view
        -- uses student number as local_student_id
        select
            cast(local_student_id as string) as contact,
            test_type as scope,
            score_type,
            date as test_date,
            score as scale_score,

            'Official' as test_type,

            test_subject as subject_area,

            case
                test_subject when 'EBRW' then 'ENG' when 'Math' then 'MATH' else 'NA'
            end as course_discipline,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            if(
                extract(month from date) >= 7,
                extract(year from date),
                extract(year from date) - 1

            ) as test_academic_year,

            row_number() over (
                partition by local_student_id, test_type, score_type order by score desc
            ) as rn_highest,

        from {{ ref("int_collegeboard__psat_unpivot") }}
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.student_number,
    e.salesforce_id,
    e.grade_level,

    a.course_discipline,
    a.test_type,
    a.scope,
    a.subject_area,
    a.score_type,
    a.administration_round,
    a.test_date,
    a.scale_score,
    a.rn_highest,

from id_table as e
inner join
    test_scores as a
    on e.academic_year = a.test_academic_year
    and e.salesforce_id = a.contact
    and a.scope in ('ACT', 'SAT')

union all

select
    e._dbt_source_relation,
    e.academic_year,
    e.student_number,
    e.salesforce_id,
    e.grade_level,

    a.course_discipline,
    a.test_type,
    a.scope,
    a.subject_area,
    a.score_type,
    a.administration_round,
    a.test_date,
    a.scale_score,
    a.rn_highest,

from id_table as e
inner join
    test_scores as a
    on e.academic_year = a.test_academic_year
    and e.student_number = cast(a.contact as numeric)
    and a.scope not in ('ACT', 'SAT')
