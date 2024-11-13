select
    c.contact_id,

    if(
        ei.ba_status = 'Graduated'
        and ei.ba_actual_end_date <= date((c.ktc_cohort + 4), 08, 31),
        1,
        0
    ) as is_4yr_ba_grad_int,

    if(
        ei.ba_status = 'Graduated'
        and ei.ba_actual_end_date <= date((c.ktc_cohort + 5), 08, 31),
        1,
        0
    ) as is_5yr_ba_grad_int,

    if(
        ei.ba_status = 'Graduated'
        and ei.ba_actual_end_date <= date((c.ktc_cohort + 6), 08, 31),
        1,
        0
    ) as is_6yr_ba_grad_int,

    if(
        ei.aa_status = 'Graduated'
        and ei.aa_actual_end_date <= date((c.ktc_cohort + 2), 08, 31),
        1,
        0
    ) as is_2yr_aa_grad_int,

    if(
        ei.aa_status = 'Graduated'
        and ei.aa_actual_end_date <= date((c.ktc_cohort + 3), 08, 31),
        1,
        0
    ) as is_3yr_aa_grad_int,

    if(
        ei.aa_status = 'Graduated'
        and ei.aa_actual_end_date <= date((c.ktc_cohort + 4), 08, 31),
        1,
        0
    ) as is_4yr_aa_grad_int,

    if(
        ei.aa_status = 'Graduated'
        and ei.aa_actual_end_date <= date((c.ktc_cohort + 5), 08, 31),
        1,
        0
    ) as is_5yr_aa_grad_int,

    if(
        ei.aa_status = 'Graduated'
        and ei.aa_actual_end_date <= date((c.ktc_cohort + 6), 08, 31),
        1,
        0
    ) as is_6yr_aa_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 1), 08, 31),
        1,
        0
    ) as is_1yr_cte_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 2), 08, 31),
        1,
        0
    ) as is_2yr_cte_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 3), 08, 31),
        1,
        0
    ) as is_3yr_cte_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 4), 08, 31),
        1,
        0
    ) as is_4yr_cte_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 5), 08, 31),
        1,
        0
    ) as is_5yr_cte_grad_int,

    if(
        ei.cte_status = 'Graduated'
        and ei.cte_actual_end_date <= date((c.ktc_cohort + 6), 08, 31),
        1,
        0
    ) as is_6yr_cte_grad_int,

    if(
        ei.ugrad_status = 'Graduated'
        and ei.ugrad_actual_end_date <= current_date('{{ var("local_timezone") }}'),
        1,
        0
    ) as is_grad_ever,

    case
        when
            ei.ugrad_status = 'Graduated'
            and ei.ugrad_actual_end_date <= date((c.ktc_cohort + 6), 08, 31)
        then 1
        when
            ei.cte_status = 'Graduated'
            and ei.cte_actual_end_date <= date((c.ktc_cohort + 6), 08, 31)
        then 1
        else 0
    end as is_6yr_ugrad_cte_grad_int,

    case
        when
            ei.ugrad_status = 'Graduated'
            and ei.ugrad_actual_end_date
            <= date_add(c.contact_birthdate, interval 25 year)
        then 1
        when
            ei.cte_status = 'Graduated'
            and ei.cte_actual_end_date
            <= date_add(c.contact_birthdate, interval 25 year)
        then 1
        else 0
    end as is_24yo_ugrad_cte_grad_int,

    case
        when
            ei.ugrad_status = 'Graduated'
            and ei.ugrad_actual_end_date <= date((c.ktc_cohort + 4), 08, 31)
        then 1
        else 0
    end as is_4yr_ugrad_grad_int,

    case
        when
            ei.ugrad_status = 'Graduated'
            and ei.ugrad_actual_end_date <= date((c.ktc_cohort + 5), 08, 31)
        then 1
        else 0
    end as is_5yr_ugrad_grad_int,

    case
        when
            ei.ugrad_status = 'Graduated'
            and ei.ugrad_actual_end_date <= date((c.ktc_cohort + 6), 08, 31)
        then 1
        else 0
    end as is_6yr_ugrad_grad_int,
from {{ ref("int_kippadb__roster") }} as c
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on c.contact_id = ei.student
