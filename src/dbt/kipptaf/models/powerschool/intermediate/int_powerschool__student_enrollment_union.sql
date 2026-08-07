with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    ref("int_focus__student_enrollment_conformed"),
                ]
            )
        }}
    ),

    -- The Focus branch is a kipptaf relation, so the usual relation-name regex
    -- would read 'kipptaf' from it. It carries its own _dbt_source_project
    -- instead; the four PowerSchool relations null-fill that column and fall
    -- back to the regex.
    with_project as (
        -- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
        select
            * except (_dbt_source_project),

            _dbt_source_relation like '%\\_focus%' as is_focus,

            coalesce(
                _dbt_source_project, regexp_extract(_dbt_source_relation, r'(kipp\w+)_')
            ) as _dbt_source_project,
        from unioned
    ),

    with_region as (
        select *, initcap(regexp_extract(_dbt_source_project, r'kipp(\w+)')) as region,
        from with_project
    )

-- Miami migrated to Focus for AY2026. The frozen PowerSchool archive keeps every
-- closed year: Focus dates a returning student's stint to the real first day of
-- school while PowerSchool used a July 1 administrative rollover, and entrydate
-- is an input to the student_enrollment_key hash, so re-dating history would
-- recompose 954 AY2025 keys and orphan the facts hanging off them.
--
-- The archive also keeps its alumni graduate placeholders in any year -- one row
-- per academic year, enroll_status 3 with null dates -- which KIPP Forward
-- reporting needs and Focus has no equivalent for.
select * except (is_focus),
from with_region
where
    _dbt_source_project != 'kippmiami'
    or (is_focus and academic_year >= 2026)
    or (not is_focus and academic_year <= 2025)
    or (not is_focus and enroll_status = 3 and entrydate is null)
