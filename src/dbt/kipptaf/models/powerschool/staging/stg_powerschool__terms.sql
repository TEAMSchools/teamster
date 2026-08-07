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
    ),

    -- Any (schoolid, academic_year) Focus carries supersedes the archive's
    -- rows for that school-year entirely -- both cover the same 1 year + 2
    -- semester + 4 quarter row set, and keeping both would double the term
    -- count. The archive still holds terms Focus never received: the
    -- district-level schoolid = 0 year record every year (Focus has no
    -- district-wide marking period), the 999999 graduated-students sentinel,
    -- and two schools (Sunrise, Liberty) for the years before their
    -- PowerSchool-to-Focus cutover. Those archive rows survive via the
    -- anti-join below.
    focus_terms as (
        select distinct schoolid, academic_year,
        from {{ ref("int_focus__terms_conformed") }}
    )

select p.* except (is_focus),
from with_project as p
left join
    focus_terms as f on p.schoolid = f.schoolid and p.academic_year = f.academic_year
where p._dbt_source_project != 'kippmiami' or p.is_focus or f.schoolid is null
