with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "int_powerschool__terms"),
                    source("kippcamden_powerschool", "int_powerschool__terms"),
                    source("kippmiami_powerschool", "int_powerschool__terms"),
                    source("kipppaterson_powerschool", "int_powerschool__terms"),
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
    ),

    -- Any (schoolid, academic_year) Focus carries a quarter for supersedes the
    -- archive's rows for that school-year. The archive still holds the
    -- district-level schoolid = 0 year record (Focus has no per-quarter
    -- equivalent for it) and two schools (Sunrise, Liberty) for the years
    -- before their PowerSchool-to-Focus cutover -- kept via the anti-join
    -- below.
    focus_terms as (
        select distinct schoolid, academic_year,
        from {{ ref("int_focus__terms_conformed") }}
        where term is not null
    )

-- int_powerschool__terms is quarter-grain only. The Focus branch also carries
-- year and semester rows (needed by stg_powerschool__terms); term is null on
-- those, so this filter drops them here without a second conform model.
select p.* except (is_focus),
from with_project as p
left join
    focus_terms as f on p.schoolid = f.schoolid and p.academic_year = f.academic_year
where
    p._dbt_source_project != 'kippmiami'
    or (p.is_focus and p.term is not null)
    or (not p.is_focus and f.schoolid is null)
