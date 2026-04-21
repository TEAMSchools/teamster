with
    transformations as (
        select
            sa.* except (_dbt_source_relation),

            lc.region,
            lc.abbreviation as school,
            lc.powerschool_school_id as schoolid,

            regexp_replace(
                sa._dbt_source_relation, r'kipp[a-z]+_', lc.dagster_code_location || '_'
            ) as _dbt_source_relation,

        from {{ ref("stg_amplify__mclass__sftp__pm_student_summary_aimline") }} as sa
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on sa.school_name = lc.name
    )

select *,
from transformations
