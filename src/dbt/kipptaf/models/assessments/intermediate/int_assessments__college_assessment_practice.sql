with
    sheet_assessments as (
        /*
            Designation and metadata, one row per assessment.

            The sheet holds 45-54 conversion rows per assessment, so joining it
            on `assessment_id` alone fans every response row out ~50x. The
            `distinct` collapses that to one row. Those five attributes are
            constant within an assessment in the sheet today, so the collapse is
            lossless -- a data-entry error that varied any of them would
            reintroduce the fan-out, which is why the staging model needs a key
            test.
        */
        select distinct
            assessment_id,
            academic_year,
            test_type,
            administration_round,
            subject,
            grade_level,
        from {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }}
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

            sa.administration_round as scope_round,

            'Practice' as test_type,

            format_date('%B', a.date_taken) as test_month,

            round(a.percent_correct / 100, 2) as percent_correct,

            /*
                Illuminate leaves `administered_at` null on externally created
                assessments, so the date-derived round is null for those. Fall
                back to the sheet's round rather than emitting null. Historical
                rows keep their existing date-derived value untouched.
            */
            coalesce(
                concat(
                    format_date('%b', a.administered_at),
                    ' ',
                    format_date('%g', a.administered_at)
                ),
                sa.administration_round
            ) as administration_round,

            /*
                Subject comes from the sheet, not Illuminate: `subject_area` is
                null on every Reading and Writing assessment, which would drop
                those rows out of `count(distinct)` below and undercount the
                sections tested. Verified the two agree wherever Illuminate is
                non-null, so this is behavior-preserving for historical rows.
            */
            if(sa.subject = 'Mathematics', 'Math', sa.subject) as subject_area,

            case
                when sa.subject in ('Reading', 'Writing', 'English')
                then 'ENG'
                when sa.subject in ('Math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            /*
                Uses the approx raw score to bring a scale score
                Convert the scale scores to be ready to add
                for sat composite score from the gsheet
            */
            if(
                a.response_type = 'overall',
                case
                    when
                        a.scope = 'SAT'
                        and sa.subject in ('Reading', 'Writing')
                        and sa.grade_level in (9, 10)
                    then (ssk.scale_score * 10)
                    else ssk.scale_score
                end,
                null
            ) as scale_score,

            count(distinct sa.subject) over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    sa.administration_round
            ) as total_subjects_tested,

            /*
                Discriminates the two-section digital SAT from a partial sitting
                of the legacy three-section form. Both report
                `total_subjects_tested = 2`, but only the digital form carries a
                single combined `Reading and Writing` section; the legacy form
                carries `Reading` and `Writing` separately. Gating the total on
                the subject count alone would manufacture a full-SAT score out
                of two of three legacy sections.
            */
            countif(sa.subject = 'Reading and Writing') over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    sa.administration_round
            ) as reading_writing_sections,

        from {{ ref("int_assessments__response_rollup") }} as a
        inner join
            -- `a.assessment_id` is canonical_assessment_id (response_rollup
            -- output is canonical-grain). Sheet's assessment_id values
            -- currently align to canonical (16/16 sheet ids = canonical) since
            -- Practice SAT/ACT haven't been canonicalized into multi-member
            -- groups. If multipart Practice administrations are added later,
            -- the sheet must reference the canonical (lowest) assessment_id.
            sheet_assessments as sa on a.assessment_id = sa.assessment_id
        /*
            Conversion is a LEFT join so a response whose `points` falls outside
            every band -- or an assessment whose conversions have not been
            entered yet -- reports a null scale score instead of disappearing.
            Membership in the sheet is what designates an assessment; `scope` is
            deliberately not filtered, because the SY26-27 practice assessments
            carry `scope = 'Benchmark'`.
        */
        left join
            {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }} as ssk
            on a.assessment_id = ssk.assessment_id
            and a.points between ssk.raw_score_low and ssk.raw_score_high
        where a.response_type in ('group', 'overall')
    ),

    practice_scale_score_by_subject as (
        select
            r.academic_year,
            r.powerschool_student_number,
            r.assessment_id,
            r.points as raw_score,

            case
                when
                    r.scope = 'SAT'
                    and r.subject_area in ('Reading', 'Writing')
                    and ssk.grade_level in (9, 10)
                then (ssk.scale_score * 10)
                else ssk.scale_score
            end as scale_score,

        from responses as r
        inner join
            {{ ref("stg_google_sheets__kippfwd__act_scale_score_key") }} as ssk
            on r.assessment_id = ssk.assessment_id
            and r.points between ssk.raw_score_low and ssk.raw_score_high
        where r.response_type = 'overall'
    ),

    two_section_totals as (
        /*
            The 400-1600 total for the two-section digital SAT.

            Aggregated with GROUP BY rather than the `select distinct` + window
            pattern the two older composite branches use. Those branches project
            `course_discipline`, `test_date`, and `test_month`, which vary within
            the partition, so their `distinct` emits one row per distinct value
            -- `Combined` currently holds 1,437 rows for 715 student-rounds. This
            branch must not reproduce that.

            `scale_score` is null unless both sections converted, so a partial
            conversion reports no total rather than a total that silently counts
            one section.
        */
        select
            academic_year,
            powerschool_student_number,
            scope,
            scope_round,
            test_type,
            administration_round,
            total_subjects_tested,

            max(test_date) as test_date,

            sum(points) as points,

            if(count(scale_score) = 2, round(sum(scale_score), 0), null) as scale_score,

        from responses
        where
            response_type = 'overall'
            and total_subjects_tested = 2
            and reading_writing_sections > 0
        group by
            academic_year,
            powerschool_student_number,
            scope,
            scope_round,
            test_type,
            administration_round,
            total_subjects_tested
    )

select
    r.academic_year,
    r.powerschool_student_number,
    r.scope,
    r.scope_round,
    r.test_type,
    r.assessment_id,
    r.assessment_title,
    r.administration_round,
    r.course_discipline,
    r.subject_area,
    r.test_date,
    r.test_month,
    r.response_type,
    r.response_type_description,
    r.points,
    r.percent_correct,
    r.total_subjects_tested,
    s.raw_score,
    s.scale_score,
from responses as r
left join
    practice_scale_score_by_subject as s
    on r.academic_year = s.academic_year
    and r.powerschool_student_number = s.powerschool_student_number
    and r.assessment_id = s.assessment_id
where r.response_type = 'group'

union all

select distinct
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    course_discipline,
    'Composite' as subject_area,
    test_date,
    test_month,
    'NA' as response_type,
    'NA' as response_type_description,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as points,

    null as percent_correct,
    total_subjects_tested,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as raw_score,

    round(
        avg(scale_score) over (
            partition by
                academic_year,
                powerschool_student_number,
                scope_round,
                administration_round
        ),
        0
    ) as scale_score,

from responses
where scope = 'ACT' and response_type = 'overall' and total_subjects_tested = 4

union all

select distinct
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    course_discipline,
    'Combined' as subject_area,
    test_date,
    test_month,
    'NA' as response_type,
    'NA' as response_type_description,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as points,

    null as percent_correct,
    total_subjects_tested,

    sum(points) over (
        partition by
            academic_year, powerschool_student_number, scope_round, administration_round
    ) as raw_score,

    round(
        sum(scale_score) over (
            partition by
                academic_year,
                powerschool_student_number,
                scope_round,
                administration_round
        ),
        0
    ) as scale_score,

from responses
where scope = 'SAT' and response_type = 'overall' and total_subjects_tested = 3

union all

select
    academic_year,
    powerschool_student_number,
    scope,
    scope_round,
    test_type,
    null as assessment_id,
    'NA' as assessment_title,
    administration_round,
    /*
        Stamped constant rather than selected through, so this branch yields one
        row per student per administration instead of one per discipline.
    */
    'NA' as course_discipline,
    'Combined' as subject_area,
    test_date,
    format_date('%B', test_date) as test_month,
    'NA' as response_type,
    'NA' as response_type_description,
    points,
    null as percent_correct,
    total_subjects_tested,
    points as raw_score,
    scale_score,
from two_section_totals
