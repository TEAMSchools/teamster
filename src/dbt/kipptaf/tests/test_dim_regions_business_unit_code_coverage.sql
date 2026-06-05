with
    expected as (
        select bu_code,
        from unnest(['TEAM', 'KCNA', 'KIPP_MIAMI', 'KPAT', 'KIPP_TAF']) as bu_code
    )

select e.bu_code,
from expected as e
left join {{ ref("dim_regions") }} as r on e.bu_code = r.business_unit_code
where r.business_unit_code is null
