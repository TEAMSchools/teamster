with
    transformations as (
        select
            s.* except (_dbt_source_relation),

            lc.region,
            lc.abbreviation as school,
            lc.powerschool_school_id as schoolid,

            regexp_replace(
                s._dbt_source_relation, r'kipp[a-z]+_', lc.dagster_code_location || '_'
            ) as _dbt_source_relation,

        from {{ ref("stg_amplify__mclass__sftp__pm_student_summary_aimline") }} as s
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
            on s.school_name = lc.name
    )

select *,
from transformations
