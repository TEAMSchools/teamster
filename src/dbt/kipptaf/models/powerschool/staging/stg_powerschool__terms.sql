with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__terms"),
                    source("kippcamden_powerschool", "stg_powerschool__terms"),
                    source("kippmiami_powerschool", "stg_powerschool__terms"),
                    source("kipppaterson_powerschool", "stg_powerschool__terms"),
                    ref("int_focus__terms_conformed"),
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
        from union_relations
    )

-- Miami cuts over to Focus at AY2026, matching the enrollment union.
--
-- Focus marking periods carry a continuous run of template rows back to syear
-- 1980 -- 20 rows a year for exactly two schools, decades before any KIPP Miami
-- school existed. Admitting every Focus year injects 766 fabricated term rows
-- into this model. The archive already covers Miami's real closed years
-- correctly, so only AY2026 is actually missing.
select * except (is_focus),
from with_project
where
    _dbt_source_project != 'kippmiami'
    or (is_focus and academic_year >= 2026)
    or (not is_focus and academic_year <= 2025)
