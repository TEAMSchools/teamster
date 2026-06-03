with
    candidates as (
        select
            sc.powerschool_student_number,
            sc.canonical_assessment_id,
            sc._dbt_source_project,
            sc.cc_dcid,
            sc.cc_source_project,
            sc.cc_dateenrolled,
            sc.cc_dateleft,
            sc.date_taken,

            c.administered_date as canonical_administered_date,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on sc.canonical_assessment_id = c.canonical_assessment_id
        where
            sc.is_internal_assessment
            and not sc.is_replacement
            and sc.cc_dcid is not null
            and sc.cc_source_project is not null
    ),

    anchored as (
        select
            *,
            coalesce(
                min(date_taken) over (
                    partition by
                        powerschool_student_number,
                        canonical_assessment_id,
                        _dbt_source_project
                ),
                canonical_administered_date
            ) as anchor_date,
        from candidates
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    ranked as (
        select
            *,
            coalesce(
                anchor_date between cc_dateenrolled and cc_dateleft, false
            ) as is_anchor_in_window,
        from anchored
    ),

    resolved as (
        {{
            dbt_utils.deduplicate(
                relation="ranked",
                partition_by="powerschool_student_number, canonical_assessment_id, _dbt_source_project",
                order_by="is_anchor_in_window desc, cc_dateleft desc",
            )
        }}
    )

select
    powerschool_student_number,
    canonical_assessment_id,
    cc_dcid,

    _dbt_source_project,
    cc_source_project,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,
from resolved
