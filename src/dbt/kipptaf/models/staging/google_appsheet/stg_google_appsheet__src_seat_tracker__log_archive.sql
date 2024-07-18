with

    source as (

        select *, from {{ source("google_appsheet", "src_seat_tracker__log_archive") }}

    ),

    renamed as (

        select
            log_id,
            staffing_model_id as snapshot_staffing_model_id,
            teammate as snapshot_teammate,
            plan_status as snapshot_plan_status,
            staffing_status as snapshot_staffing_status,
            status_detail as snapshot_status_detail,
            mid_year_hire as snapshot_mid_year_hire,
            export_date,
            academic_year as snapshot_academic_year,

        from source

    )

select *,
from renamed
