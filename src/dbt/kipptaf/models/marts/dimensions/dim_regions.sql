with
    /* business_unit_code and legal_entity are sourced from ADP; the */
    /* remaining region / state / timezone columns are hardcoded by */
    /* business_unit_code in the final SELECT. */
    bu_xref as (
        select distinct
            organizational_unit__assigned__business_unit__code_value
            as business_unit_code,
            organizational_unit__assigned__business_unit__name as business_unit_name,
        from
            {{
                ref(
                    "int_adp_workforce_now__workers__work_assignments__organizational_units__pivot"
                )
            }}
        where organizational_unit__assigned__business_unit__code_value is not null
    )

select
    {{ dbt_utils.generate_surrogate_key(["business_unit_code"]) }} as region_key,

    business_unit_name as legal_entity,
    business_unit_code,

    /* All regions use America/New_York (Eastern) as reporting convention — */
    /* Miami observes ET in practice and FL permanent-EST has not taken effect */
    'America/New_York' as timezone,

    case
        business_unit_code
        when 'TEAM'
        then 'Newark'
        when 'KCNA'
        then 'Camden'
        when 'KIPP_MIAMI'
        then 'Miami'
        when 'KPAT'
        then 'Paterson'
        when 'KIPP_TAF'
        then 'TAF'
    end as `name`,

    case
        business_unit_code
        when 'TEAM'
        then 'kippnewark'
        when 'KCNA'
        then 'kippcamden'
        when 'KIPP_MIAMI'
        then 'kippmiami'
        when 'KPAT'
        then 'kipppaterson'
        when 'KIPP_TAF'
        then 'kipptaf'
    end as dagster_code_location,

    case business_unit_code when 'KIPP_MIAMI' then 'FL' else 'NJ' end as state,
from bu_xref
