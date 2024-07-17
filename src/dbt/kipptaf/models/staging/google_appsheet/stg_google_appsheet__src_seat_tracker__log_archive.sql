with 

source as (

    select * from {{ source('google_appsheet', 'src_seat_tracker__log_archive') }}

),

renamed as (

    select
        log_id,
        staffing_model_id,
        teammate,
        plan_status,
        staffing_status,
        status_detail,
        mid_year_hire,
        export_date,
        academic_year

    from source

)

select * from renamed
