with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_powerschool", "stg_powerschool__u_expectations"
                    ),
                    source(
                        "kippnewark_powerschool", "stg_powerschool__u_expectations"
                    ),
                ]
            )
        }}
    ),

    real_union as (
        select
            id,
            school_level,
            `quarter`,
            week_number,
            cnt_w,
            cnt_h,
            cnt_f,
            cnt_s,
            notes,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,

            {{ extract_source_project("union_relations") }} as _dbt_source_project,

        from union_relations
    ),

    -- TODO(#3908): remove once Paterson gets its own U_EXPECTATIONS source
    -- (native plugin support or another data path). Paterson's PowerSchool
    -- instance cannot run the KIPP NJ Gradebook Audit plugin, so
    -- U_EXPECTATIONS is never populated there. Spoof MS expectations from
    -- Newark's real plugin data until a native solution exists -- see
    -- docs/models/gradebook-audit-data-model.md "Paterson GradeBook
    -- plugin".
    paterson_spoof as (
        select
            id,
            school_level,
            `quarter`,
            week_number,
            cnt_w,
            cnt_h,
            cnt_f,
            cnt_s,
            notes,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,

            'kipppaterson' as _dbt_source_project,

        from {{ source("kippnewark_powerschool", "stg_powerschool__u_expectations") }}
        where school_level = 'MS'
    )

select *,
from real_union

union all

select *,
from paterson_spoof
