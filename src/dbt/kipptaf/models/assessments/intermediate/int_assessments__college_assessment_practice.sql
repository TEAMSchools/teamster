with
    -- grain projection: every column is functionally determined by
    -- assessment_id + raw_score_low. The distinct collapses the two AY2023 SAT
    -- scaffold rows that differ only in expected_grade_level.
    conversion as (
        select distinct
            c.assessment_id,
            c.academic_year,
            c.test_type,
            c.scope_round,
            c.subject,
            c.grade_level,
            c.raw_score_low,
            c.raw_score_high,
            c.scale_score,
            c.aligned_scale_score,
            c.score_type,
            c.expected_total_subjects_tested,

            s.expected_subject_area as subject_area,
            s.expected_aligned_subject_area as aligned_subject_area,
            s.expected_grouping as `grouping`,
            s.expected_course_discipline as course_discipline,

        from
            {{ ref("stg_google_sheets__kippfwd__practice_scale_score_conversion") }}
            as c
        inner join
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} as s
            on c.academic_year = s.academic_year
            and c.test_type = s.expected_scope
            and c.score_type = s.expected_score_type
        where s.expected_test_type = 'Practice'
    ),

    responses as (
        select
            a.academic_year,
            a.illuminate_student_id,
            a.powerschool_student_number,
            a.scope,
            a.assessment_id,
            a.title as assessment_title,
            a.date_taken as test_date,
            a.response_type,  -- Group or overall
            a.response_type_description,  -- Group name
            /* Points earned... looks to be # of questions correct on Illuminate */
            a.points,

            ssk.scope_round,
            ssk.grade_level,
            ssk.test_type,
            ssk.subject,
            ssk.subject_area,
            ssk.aligned_subject_area,
            ssk.score_type,
            ssk.expected_total_subjects_tested,
            ssk.course_discipline,

            format_date('%B', a.date_taken) as test_month,

            round(a.percent_correct / 100, 2) as percent_correct,

            concat(
                format_date('%b', a.administered_at),
                ' ',
                format_date('%g', a.administered_at)
            ) as administration_round,

            max(if(a.response_type = 'overall', a.points, null)) over (
                partition by
                    a.academic_year, a.powerschool_student_number, a.assessment_id
            ) as raw_score,

            max(if(a.response_type = 'overall', ssk.aligned_scale_score, null)) over (
                partition by
                    a.academic_year, a.powerschool_student_number, a.assessment_id
            ) as scale_score,

            count(distinct ssk.subject_area) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    ssk.test_type,
                    ssk.scope_round,
                    ssk.grade_level
            ) as actual_total_subjects_tested,

        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            -- `a.assessment_id` is canonical_assessment_id (response_rollup
            -- output is canonical-grain). Sheet's assessment_id values
            -- currently align to canonical (12/12 sheet ids = canonical) since
            -- Practice SAT/ACT haven't been canonicalized into multi-member
            -- groups. If multipart Practice administrations are added later,
            -- the sheet must reference the canonical (lowest) assessment_id.
            conversion as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where a.response_type in ('group', 'overall')
    )

-- group scores
select
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    grade_level,
    assessment_id,
    assessment_title,
    administration_round,
    course_discipline,
    test_date,
    test_month,
    initcap(response_type) as response_type,
    response_type_description,
    `subject`,
    subject_area,
    aligned_subject_area,
    score_type,
    points,
    percent_correct,
    actual_total_subjects_tested,
    expected_total_subjects_tested,
    raw_score,
    scale_score,

from responses
where response_type = 'group'

union all

-- subject scores
-- grain projection: one row per student per assessment. Every projected column
-- is functionally determined by powerschool_student_number + assessment_id --
-- the ssk.* columns because the sheet holds one metadata combination per
-- assessment_id, and raw_score/scale_score because both read the single
-- 'overall' sibling row through a window. The distinct drops only the
-- per-response-group columns (response_type, response_type_description, points,
-- percent_correct); it is not a mask for upstream duplicates.
select distinct
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    grade_level,
    assessment_id,
    assessment_title,
    administration_round,
    course_discipline,
    test_date,
    test_month,

    'Subject' as response_type,
    'Subject Score' as response_type_description,

    `subject`,
    subject_area,
    aligned_subject_area,
    score_type,

    null as points,
    null as percent_correct,

    actual_total_subjects_tested,
    expected_total_subjects_tested,
    raw_score,
    scale_score,

from responses
where response_type = 'group'

union all

-- total scores
select
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    grade_level,

    null as assessment_id,
    'NA' as assessment_title,

    administration_round,

    'NA' as course_discipline,

    max(test_date) as test_date,

    format_date('%B', max(test_date)) as test_month,

    'Total' as response_type,
    'Total Score' as response_type_description,
    null as subject,

    if(test_type = 'ACT', 'Composite', 'Combined') as subject_area,

    'Total' as aligned_subject_area,

    case
        test_type
        when 'ACT'
        then 'act_composite'
        when 'SAT'
        then 'sat_total_score'
        when 'PSAT 8/9'
        then 'psat89_total'
        when 'PSAT10'
        then 'psat10_total'
        when 'PSAT NMSQT'
        then 'psatnmsqt_total'
    end as score_type,

    sum(points) as points,

    null as percent_correct,

    actual_total_subjects_tested,
    expected_total_subjects_tested,

    sum(points) as raw_score,

    round(
        case
            when actual_total_subjects_tested != expected_total_subjects_tested
            then null
            when test_type = 'ACT'
            then avg(scale_score)
            else sum(scale_score)
        end,
        0
    ) as scale_score,

from responses
where response_type = 'overall'
group by
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    grade_level,
    administration_round,
    actual_total_subjects_tested,
    expected_total_subjects_tested
