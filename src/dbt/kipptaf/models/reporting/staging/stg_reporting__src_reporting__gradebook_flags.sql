with

    source as (

        select * from {{ source("reporting", "src_reporting__gradebook_flags") }}

    ),

    renamed as (

        select
            region,
            school_level,
            audit_category,
            audit_flag_name,
            grade_level,
            code,
            cte_grouping,

        from source

    )

select *
from renamed
