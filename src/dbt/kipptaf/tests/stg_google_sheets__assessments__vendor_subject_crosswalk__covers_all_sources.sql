with
    raw_subjects as (
        select distinct 'iready' as source_system, `subject` as raw_subject,
        from {{ ref("int_iready__diagnostic_results") }}

        union all

        select distinct 'pearson' as source_system, `subject` as raw_subject,
        from {{ ref("int_pearson__all_assessments") }}

        union all

        select distinct 'fldoe' as source_system, assessment_subject as raw_subject,
        from {{ ref("int_fldoe__all_assessments") }}

        union all

        select distinct
            'renlearn' as source_system, _dagster_partition_subject as raw_subject,
        from {{ ref("stg_renlearn__star") }}

        union all

        -- amplify has no raw subject column; the blended layer supplies this
        -- literal, so the pair is checked against the sheet rather than data.
        select 'amplify' as source_system, 'DIBELS' as raw_subject,
    )

select r.source_system, r.raw_subject,
from raw_subjects as r
left join
    {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
    on r.source_system = x.source_system
    and r.raw_subject = x.raw_subject
where r.raw_subject is not null and x.raw_subject is null
