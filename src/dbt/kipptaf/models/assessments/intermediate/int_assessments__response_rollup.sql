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
            s.powerschool_school_id,
            s.grade_level_id,
            s.is_internal_assessment,
            s.is_replacement,
            s.student_assessment_id,
            s.canonical_assessment_id,
            s.canonical_title,
            s.canonical_administered_at,
            s.canonical_grade_level_id,

            asr.response_type,
            asr.response_type_id,
            asr.response_type_code,
            asr.response_type_description,
            asr.response_type_root_description,
            asr.points_possible,
            asr.points,
            asr.percent_correct,

            pb.canonical_performance_band_set_id,

            if(s.date_taken < date '2000-01-01', null, s.date_taken) as date_taken,
        from {{ ref("int_assessments__scaffold") }} as s
        left join
            {{ ref("int_illuminate__agg_student_responses") }} as asr
            on s.student_assessment_id = asr.student_assessment_id
        left join
            {{ ref("int_assessments__performance_bands") }} as pb
            on s.assessment_id = pb.assessment_id
            and asr.response_type = pb.response_type
            and asr.response_type_id = pb.response_type_id
    ),

    -- Canonical-grain rollup of school/region from response-grain scaffold rows.
    -- Without this, group-by aggregates would need min() per column, and
    -- independent mins can pick from different rows in the same partition. Per
    -- src/dbt/CLAUDE.md "Canonical attributes from a partition", first_value
    -- on a deterministic ordering picks both attributes from the same row.
    -- Cross-school groups exist here because of upstream Illuminate
    -- canonicalization carrying wrong academic_year tags onto duplicated
    -- assessments — tracked in #3801. Once #3801 is resolved, the canonical
    -- school/region selection should collapse to a single value per partition
    -- and this CTE can be removed (reverting school/region to plain group-by
    -- columns or pruning them entirely if they move to a per-consumer
    -- enrollment join).
    canonical_attrs as (
        select
            *,
            first_value(powerschool_school_id) over (w) as canonical_school_id,
            first_value(region) over (w) as canonical_region,
        from scaffold_responses
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

            -- canonical_school_id / canonical_region are constant per partition
            -- (windowed in canonical_attrs). any_value() makes that explicit
            -- without independent-min() drift. See #3801.
            any_value(canonical_school_id) as powerschool_school_id,
            any_value(canonical_region) as region,

            count(distinct assessment_id) as n_assessments,

            sum(points) as points,

            array_agg(distinct assessment_id) as assessment_ids,

            round(
                safe_divide(sum(points), sum(points_possible)) * 100, 1
            ) as percent_correct,
        from canonical_attrs
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

    concat('kipp', lower(ru.region)) as _dbt_source_project,
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
