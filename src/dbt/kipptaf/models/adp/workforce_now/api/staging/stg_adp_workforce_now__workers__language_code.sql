with
    workers as (
        select
            associate_oid,
            effective_date_start,
            language_code_surrogate_key,
            language_code,
        from {{ ref("stg_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        select
            *,

            lag(language_code_surrogate_key, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as language_code_surrogate_key_lag,
        from workers
    )

select
    associate_oid,
    effective_date_start,
    language_code_surrogate_key,

    language_code.codevalue as language_code__code_value,
    language_code.longname as language_code__long_name,
    language_code.shortname as language_code__short_name,

    cast(language_code.effectivedate as date) as language_code__effective_date,
from deduplicate
where language_code_surrogate_key != language_code_surrogate_key_lag
