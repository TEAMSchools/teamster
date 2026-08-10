with
    -- The upstream student_number holds the PREFIXED Focus id, not the network
    -- student number, so it is unprefixed here with the same rule
    -- int_students__students applies to the student spine. ps_schoolid is the
    -- PowerSchool-aligned school id the upstream already resolved through the
    -- locations crosswalk -- Focus's own schoolid is a small internal integer
    -- with no relation to the network school number. Only AY2026-forward Focus
    -- rows are admitted: the network union keeps the frozen PowerSchool archive
    -- for every closed year, because Focus dates a returning student's stint to
    -- the real first day of school while PowerSchool used a July 1
    -- administrative rollover, and entrydate feeds the student_enrollment_key
    -- hash -- re-dating history would recompose every historical key and
    -- orphan the facts hanging off them.
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            academic_year,
            exitdate,
            enroll_status,
            entrycode,
            exitcode,
            grade_level,
            rn_year,
            year_in_school,
            year_in_network,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            dob,
            state,

            ps_schoolid as schoolid,
            startdate as entrydate,
            student_first_name as first_name,
            student_last_name as last_name,

            {{ unprefix_focus_student_id("student_number") }} as student_number,
        from {{ ref("int_focus__student_enrollments") }}
        where academic_year >= 2026
    ),

    powerschool_unioned as (
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
                ]
            )
        }}
    ),

    powerschool_with_project as (
        -- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from powerschool_unioned
    ),

    -- Miami migrated to Focus for AY2026. The archive contributes two things
    -- for Miami: every closed year (AY2025 and earlier), and its alumni
    -- graduate placeholders in ANY year -- one row per academic year,
    -- enroll_status 3 with null entry/exit dates -- which KIPP Forward
    -- reporting needs and Focus has no equivalent for.
    powerschool_conformed as (
        select *,
        from powerschool_with_project
        where
            _dbt_source_project != 'kippmiami'
            or academic_year <= 2025
            or (enroll_status = 3 and entrydate is null)
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
