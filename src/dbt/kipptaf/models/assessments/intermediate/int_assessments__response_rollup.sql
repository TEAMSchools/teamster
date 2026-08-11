with
    scaffold_responses as (
        select
            s.illuminate_student_id,
            s.powerschool_student_number,
            s.assessment_id,
            s.title,
            s.scope,
            s.subject_area,
            s.discipline,
            s.academic_year,
            s.administered_at,
            s.module_type,
            s.module_code,
            s.region,
            s._dbt_source_project,
            s.powerschool_school_id,
            s.grade_level_id,
            s.is_internal_assessment,
            s.is_replacement,
            s.student_assessment_id,
            s.canonical_assessment_id,
            s.date_taken,

            asr.response_type,
            asr.response_type_id,
            asr.response_type_code,
            asr.response_type_description,
            asr.response_type_root_description,
            asr.points_possible,
            asr.points,
            asr.percent_correct,

            pb.canonical_performance_band_set_id,

            if(s.is_internal_assessment, c.title, s.title) as canonical_title,
            if(
                s.is_internal_assessment, c.administered_date, s.administered_at
            ) as canonical_administered_at,
            if(
                s.is_internal_assessment, c.grade_level_id, s.grade_level_id
            ) as canonical_grade_level_id,

        from {{ ref("int_assessments__scaffold") }} as s
        left join
            {{ ref("int_illuminate__agg_student_responses") }} as asr
            on s.student_assessment_id = asr.student_assessment_id
        left join
            {{ ref("int_assessments__performance_bands") }} as pb
            on s.assessment_id = pb.assessment_id
            and asr.response_type = pb.response_type
            and asr.response_type_id = pb.response_type_id
        left join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on s.canonical_assessment_id = c.canonical_assessment_id
    ),

    -- Illuminate `date_taken` is unreliable for a small share of rows, in BOTH
    -- directions: the raw column spans 0001-01-01 to 4024-12-04. Every row is
    -- judged against a date it should sit near, never against a calendar
    -- constant — an absolute floor is arbitrary, and being one-sided it can
    -- never reject a future date.
    --
    -- Preferred anchor is the row's own administration (+/-365 days). ~296k
    -- rows have none, so those fall back to their `academic_year`, which is
    -- always populated; the +/-1 year window is wide enough to absorb the
    -- academic-year tagging drift of #3801. Together they null 11,455 rows
    -- (0.34% of dated rows) and bring the range to 2013-06-03 .. 2026-12-27.
    --
    -- The fallback is what earns its keep: an earlier version of this guard
    -- used a 2000-01-01 floor for unanchored rows, which caught exactly 1 row
    -- and let a ~1,300-row cluster of 2001-01-01 sittings through, because
    -- they cleared the constant while sitting a decade from their academic
    -- year.
    --
    -- Rows inside their window pass through untouched, so a legitimately
    -- future-dated sitting within its administration window is preserved, and
    -- `assessment_date_key` (`coalesce(administration, date_taken)`) keeps a
    -- real administration date where one exists — the invariant #4546 rests on.
    --
    -- This matters more than the row counts suggest: the final select takes
    -- `min(date_taken)` per canonical group, so one junk row poisons its whole
    -- group's date. Nulling before the aggregate is what actually fixes it.
    sanitized_responses as (
        select
            * except (date_taken),

            case
                when date_taken is null
                then null
                when
                    canonical_administered_at is not null
                    and date_diff(date_taken, canonical_administered_at, day)
                    between -365 and 365
                then date_taken
                when
                    canonical_administered_at is null
                    and extract(year from date_taken)
                    between academic_year - 1 and academic_year + 1
                then date_taken
            end as date_taken,
        from scaffold_responses
    ),

    -- Per-partition tiebreak for location columns. NOT a canonical attribute —
    -- school / _dbt_source_project are per-response location data that vary
    -- across rows in the same (student, canonical_assessment, is_replacement)
    -- partition because of upstream Illuminate canonicalization defects
    -- (#3801) carrying wrong academic_year tags onto duplicated assessments.
    -- first_value on a deterministic ordering picks both columns from the
    -- same row so independent min() drift can't split them. Once #3801 is
    -- resolved, the partition becomes pure and this CTE can be removed.
    tiebroken_attrs as (
        select
            *,
            first_value(powerschool_school_id) over (w) as selected_school_id,
            first_value(region) over (w) as selected_region,
            first_value(_dbt_source_project) over (w) as selected_dbt_source_project,
        from sanitized_responses
        window
            w as (
                partition by
                    illuminate_student_id, canonical_assessment_id, is_replacement
                -- powerschool_school_id is the final tiebreaker so that
                -- partitions where every row has null date_taken and null
                -- student_assessment_id (students rostered to canonical members
                -- but with no responses recorded) still pick deterministically
                -- across rebuilds.
                order by
                    (date_taken is null) asc,
                    date_taken asc,
                    student_assessment_id asc,
                    powerschool_school_id asc
            )
    ),

    internal_assessment_rollup as (
        select
            illuminate_student_id,
            powerschool_student_number,
            canonical_assessment_id as assessment_id,
            canonical_title as title,
            canonical_administered_at as administered_at,
            canonical_grade_level_id as grade_level_id,
            canonical_performance_band_set_id as performance_band_set_id,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,

            min(date_taken) as date_taken,

            -- selected_* values are constant per partition (windowed in
            -- tiebroken_attrs). any_value() makes that explicit without
            -- independent-min() drift. See #3801.
            any_value(selected_school_id) as powerschool_school_id,
            any_value(selected_region) as region,
            any_value(selected_dbt_source_project) as _dbt_source_project,

            count(distinct assessment_id) as n_assessments,

            sum(points) as points,

            array_agg(distinct assessment_id) as assessment_ids,

            round(
                safe_divide(sum(points), sum(points_possible)) * 100, 1
            ) as percent_correct,
        from tiebroken_attrs
        where is_internal_assessment
        group by
            illuminate_student_id,
            powerschool_student_number,
            canonical_assessment_id,
            canonical_title,
            canonical_administered_at,
            canonical_grade_level_id,
            canonical_performance_band_set_id,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description
    ),

    response_union as (
        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            region,
            _dbt_source_project,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            date_taken,
            points,
            percent_correct,
            n_assessments,
            assessment_ids,
            powerschool_school_id,
            title,
            assessment_id,
            administered_at,
            grade_level_id,
            performance_band_set_id,

            if(n_assessments > 1, true, false) as is_multipart_assessment,
        from internal_assessment_rollup

        union all

        select
            illuminate_student_id,
            powerschool_student_number,
            academic_year,
            scope,
            subject_area,
            discipline,
            module_type,
            module_code,
            region,
            _dbt_source_project,
            is_internal_assessment,
            is_replacement,
            response_type,
            response_type_id,
            response_type_code,
            response_type_description,
            response_type_root_description,
            date_taken,
            points,
            percent_correct,

            1 as n_assessments,

            [canonical_assessment_id] as assessment_ids,

            powerschool_school_id,
            canonical_title as title,
            canonical_assessment_id as assessment_id,
            canonical_administered_at as administered_at,
            canonical_grade_level_id as grade_level_id,
            canonical_performance_band_set_id as performance_band_set_id,

            false as is_multipart_assessment,
        from scaffold_responses
        where not is_internal_assessment
    )

select
    ru.illuminate_student_id,
    ru.powerschool_student_number,
    ru.academic_year,
    ru.scope,
    ru.subject_area,
    ru.discipline,
    ru.module_type,
    ru.module_code,
    ru.region,
    ru._dbt_source_project,
    ru.powerschool_school_id,
    ru.is_internal_assessment,
    ru.is_replacement,
    ru.response_type,
    ru.response_type_id,
    ru.response_type_code,
    ru.response_type_description,
    ru.response_type_root_description,
    ru.date_taken,
    ru.points,
    ru.percent_correct,
    ru.title,
    ru.assessment_id,
    ru.administered_at,
    ru.grade_level_id,
    ru.performance_band_set_id,
    ru.n_assessments,
    ru.is_multipart_assessment,
    ru.assessment_ids,

    pbl.label as performance_band_label,
    pbl.label_number as performance_band_label_number,
    pbl.is_mastery,

    rta.name as term_administered,

    rtt.name as term_taken,
from response_union as ru
left join
    {{ ref("int_illuminate__performance_band_sets") }} as pbl
    on ru.performance_band_set_id = pbl.performance_band_set_id
    and ru.percent_correct between pbl.minimum_value and pbl.maximum_value
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rta
    on ru.administered_at between rta.start_date and rta.end_date
    and ru.powerschool_school_id = rta.school_id
    and rta.type = 'RT'
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rtt
    on ru.date_taken between rtt.start_date and rtt.end_date
    and ru.powerschool_school_id = rtt.school_id
    and rtt.type = 'RT'
