with
    scores as (
        select
            r.region,
            r.schoolid,
            r.school,
            r.assessment_edition,
            r.benchmark_period,

            r.composite_score,
            r.composite_level,
            r.composite_tested_out,
            r.composite_discontinued,

            r.letter_names_lnf_score,
            r.letter_names_lnf_level,
            r.letter_names_lnf_tested_out,
            r.letter_names_lnf_discontinued,

            r.phonemic_awareness_psf_score,
            r.phonemic_awareness_psf_level,
            r.phonemic_awareness_psf_tested_out,
            r.phonemic_awareness_psf_discontinued,

            r.decoding_nwf_wrc_score,
            r.decoding_nwf_wrc_level,
            r.decoding_nwf_wrc_tested_out,
            r.decoding_nwf_wrc_discontinued,

            r.reading_fluency_orf_score,
            r.reading_fluency_orf_level,
            r.reading_fluency_orf_tested_out,
            r.reading_fluency_orf_discontinued,

            r.basic_comprehension_maze_score,
            r.basic_comprehension_maze_level,
            r.basic_comprehension_maze_tested_out,
            r.basic_comprehension_maze_discontinued,

            e.state_studentnumber,

            case
                r.region
                when 'Newark'
                then '7325'
                when 'Camden'
                then '1799'
                when 'Paterson'
                then '7899'
            end as district_code,

            case
                r.region
                when 'Newark'
                then '965'
                when 'Camden'
                then '111'
                when 'Paterson'
                then '925'
            end as school_code,

        from {{ ref("int_amplify__mclass__benchmark_student_summary") }} as r
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on r.academic_year = e.academic_year
            and r.student_primary_id = e.student_number
            and e.rn_year = 1
        where
            r.state = 'NJ'
            and r.enrollment_grade in ('K', '1', '2', '3')
            and r.enrollment_grade = r.assessment_grade
            and r.academic_year = {{ var("current_academic_year") }}
    ),

    unpivoted_scores as (
        select
            region,
            schoolid,
            school,
            benchmark_period,

            district_code,
            school_code,
            state_studentnumber,
            assessment_edition,

            measure,
            `level`,

            cast(score as string) as score,

            case
                when tested_out
                then 'Tested Out'
                when discontinued
                then 'Discontinued'
                else `level`
            end as level_mod,

        from
            -- trunk-ignore(sqlfluff/LT01)
            scores unpivot include nulls(
                (`level`, score, tested_out, discontinued) for measure in (
                    (
                        decoding_nwf_wrc_level,
                        decoding_nwf_wrc_score,
                        decoding_nwf_wrc_tested_out,
                        decoding_nwf_wrc_discontinued
                    ) as 'phonics_and_decoding',
                    (
                        letter_names_lnf_level,
                        letter_names_lnf_score,
                        letter_names_lnf_tested_out,
                        letter_names_lnf_discontinued
                    ) as 'letter_naming',
                    (
                        phonemic_awareness_psf_level,
                        phonemic_awareness_psf_score,
                        phonemic_awareness_psf_tested_out,
                        phonemic_awareness_psf_discontinued
                    ) as 'phonemic_awareness',
                    (
                        basic_comprehension_maze_level,
                        basic_comprehension_maze_score,
                        basic_comprehension_maze_tested_out,
                        basic_comprehension_maze_discontinued
                    ) as 'comprehension',
                    (
                        reading_fluency_orf_level,
                        reading_fluency_orf_score,
                        reading_fluency_orf_tested_out,
                        reading_fluency_orf_discontinued
                    ) as 'oral_reading_fluency',
                    (
                        composite_level,
                        composite_score,
                        composite_tested_out,
                        composite_discontinued
                    ) as 'composite'
                )
            )
    ),

    cleaned_scores as (
        select
            region,
            schoolid,
            school,
            benchmark_period,

            district_code,
            school_code,
            state_studentnumber,
            assessment_edition,

            measure,
            score,
            `level`,
            level_mod,

            case
                when level_mod = 'Tested Out'
                then 'TO'
                when level_mod = 'Discontinued'
                then 'D'
                when level_mod = 'Above Benchmark'
                then 'Above Grade Level'
                when level_mod = 'At Benchmark'
                then 'At Grade Level'
                when level_mod in ('Well Below Benchmark', 'Below Benchmark')
                then 'Below Grade Level'
                else level_mod
            end as level_mod_coded,

        from unpivoted_scores
    ),

    score_pivot as (
        select *,
        from
            cleaned_scores pivot (
                any_value(score) as score for
                measure in (
                    'phonics_and_decoding',
                    'letter_naming',
                    'phonemic_awareness',
                    'comprehension',
                    'oral_reading_fluency',
                    'composite'
                )
            )
    ),

    level_pivot as (
        select *,
        from
            cleaned_scores pivot (
                any_value(level_mod_coded) as level_mod_coded for
                measure in (
                    'phonics_and_decoding',
                    'letter_naming',
                    'phonemic_awareness',
                    'comprehension',
                    'oral_reading_fluency',
                    'composite'
                )
            )
    )

select
    s.region,
    s.schoolid,
    s.school,
    s.benchmark_period,
    s.district_code,
    s.school_code,
    s.state_studentnumber as sid,
    s.assessment_edition as assessment_name,

    max(s.score_phonics_and_decoding) as phonics_and_decoding_score,
    max(s.score_letter_naming) as letter_naming_score,
    max(s.score_phonemic_awareness) as phonemic_awareness_score,
    max(s.score_comprehension) as comprehension_score,
    max(s.score_oral_reading_fluency) as oral_reading_fluency_score,
    max(s.score_composite) as composite_score,

    max(l.level_mod_coded_phonics_and_decoding) as phonics_and_decoding_level,
    max(l.level_mod_coded_letter_naming) as letter_naming_level,
    max(l.level_mod_coded_phonemic_awareness) as phonemic_awareness_level,
    max(l.level_mod_coded_comprehension) as comprehension_level,
    max(l.level_mod_coded_oral_reading_fluency) as oral_reading_fluency_level,
    max(l.level_mod_coded_composite) as composite_level,

from score_pivot as s
left join
    level_pivot as l
    on s.region = l.region
    and s.schoolid = l.schoolid
    and s.school = l.school
    and s.benchmark_period = l.benchmark_period
    and s.district_code = l.district_code
    and s.school_code = l.school_code
    and s.state_studentnumber = l.state_studentnumber
    and s.assessment_edition = l.assessment_edition
group by
    s.region,
    s.schoolid,
    s.school,
    s.benchmark_period,
    s.district_code,
    s.school_code,
    s.state_studentnumber,
    s.assessment_edition
