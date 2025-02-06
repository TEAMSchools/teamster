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

    act_sat as (  -- this is by itself because the int_kippadb__standardized_test_unpivot view uses contact id
        select
            contact,
            test_type as scope,
            score_type,
            date as test_date,
            score as scale_score,
            rn_highest,

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

            if(
                extract(month from date) >= 7,
                extract(year from date),
                extract(year from date) - 1

            ) as test_academic_year,
            -- this window calc my way to track a bigger problem: we have poor
            -- salesforce data entry that is causing abtou 600 or so dups on this
            -- table. i would like to later discuss a way to check the unpivot table
            -- for dups before it even makes it to the data model and align with casey
            -- on what the process will be for her to remove these dups from
            -- salesforce. for now,  i just need a way to track them to show walters
            count(*) over (
                partition by contact, score_type, extract(month from date)
            ) as duplicate_check,

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

    ),

    psat as (  -- this is by itself because the int_kippadb__standardized_test_unpivot view uses student number as local_student_id
        select
            local_student_id,
            test_type as scope,
            score_type,
            date as test_date,
            score as scale_score,
            rn_highest,

            'Official' as test_type,

            test_subject as subject_area,

            case
                test_subject when 'EBRW' then 'ENG' when 'Math' then 'MATH' else 'NA'
            end as course_discipline,

            if(
                extract(month from date) >= 7,
                extract(year from date),
                extract(year from date) - 1

            ) as test_academic_year,
            -- the chances of dups happening here is very very very low, but you never
            -- know, i guess
            count(*) over (
                partition by local_student_id, score_type, extract(month from date)
            ) as duplicate_check,

        from {{ ref("int_collegeboard__psat_unpivot") }}
    ),

    -- the group bys below are a workaround for now for all of those dups due to bad
    -- or null dates. trying my best to keep this moving forward while i figure out
    -- someting with casey
    college_assesement_scores as (
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
            max(a.test_date) as test_date,
            max(a.scale_score) as scale_score,

        from id_table as e
        inner join
            act_sat as a
            on e.academic_year = a.test_academic_year
            and e.salesforce_id = a.contact
        group by all
        union all

        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,
            e.salesforce_id,
            e.grade_level,

            p.course_discipline,
            p.test_type,
            p.scope,
            p.subject_area,
            p.score_type,
            max(p.test_date) as test_date,
            max(p.scale_score) as scale_score,

        from id_table as e
        inner join
            psat as p
            on e.academic_year = p.test_academic_year
            and e.student_number = p.local_student_id
        group by all
    )

select
    *,

    concat(
        format_date('%b', test_date), ' ', format_date('%g', test_date)
    ) as administration_round,

    -- im doing the rn_highest here because of the dups im trying to sort workaround
    -- for now by the group by above
    row_number() over (
        partition by student_number, test_type, score_type order by scale_score desc
    ) as rn_highest,

from college_assesement_scores
