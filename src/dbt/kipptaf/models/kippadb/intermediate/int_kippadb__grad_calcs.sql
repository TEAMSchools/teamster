select
    student,

    if(
        ba_status = 'Graduated'
        and ba_actual_end_date <= date((contact_kipp_hs_class + 4), 08, 31),
        1,
        0
    ) as is_4yr_ba_grad_int,

    if(
        ba_status = 'Graduated'
        and ba_actual_end_date <= date((contact_kipp_hs_class + 5), 08, 31),
        1,
        0
    ) as is_5yr_ba_grad_int,

    if(
        ba_status = 'Graduated'
        and ba_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31),
        1,
        0
    ) as is_6yr_ba_grad_int,

    if(
        ba_status = 'Graduated'
        and ba_actual_end_date <= date((contact_kipp_hs_class + 7), 08, 31),
        1,
        0
    ) as is_7yr_ba_grad_int,

    if(
        aa_status = 'Graduated'
        and aa_actual_end_date <= date((contact_kipp_hs_class + 2), 08, 31),
        1,
        0
    ) as is_2yr_aa_grad_int,

    if(
        aa_status = 'Graduated'
        and aa_actual_end_date <= date((contact_kipp_hs_class + 3), 08, 31),
        1,
        0
    ) as is_3yr_aa_grad_int,

    if(
        aa_status = 'Graduated'
        and aa_actual_end_date <= date((contact_kipp_hs_class + 4), 08, 31),
        1,
        0
    ) as is_4yr_aa_grad_int,

    if(
        aa_status = 'Graduated'
        and aa_actual_end_date <= date((contact_kipp_hs_class + 5), 08, 31),
        1,
        0
    ) as is_5yr_aa_grad_int,

    if(
        aa_status = 'Graduated'
        and aa_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31),
        1,
        0
    ) as is_6yr_aa_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 1), 08, 31),
        1,
        0
    ) as is_1yr_cte_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 2), 08, 31),
        1,
        0
    ) as is_2yr_cte_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 3), 08, 31),
        1,
        0
    ) as is_3yr_cte_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 4), 08, 31),
        1,
        0
    ) as is_4yr_cte_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 5), 08, 31),
        1,
        0
    ) as is_5yr_cte_grad_int,

    if(
        cte_status = 'Graduated'
        and cte_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31),
        1,
        0
    ) as is_6yr_cte_grad_int,

    if(
        ugrad_status = 'Graduated'
        and ugrad_actual_end_date <= current_date('{{ var("local_timezone") }}'),
        1,
        0
    ) as is_grad_ever,

    case
        when
            ugrad_status = 'Graduated'
            and ugrad_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31)
        then 1
        when
            cte_status = 'Graduated'
            and cte_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31)
        then 1
        else 0
    end as is_6yr_ugrad_cte_grad_int,

    case
        when
            ugrad_status = 'Graduated'
            and ugrad_actual_end_date <= date_add(contact_birthdate, interval 25 year)
        then 1
        when
            cte_status = 'Graduated'
            and cte_actual_end_date <= date_add(contact_birthdate, interval 25 year)
        then 1
        else 0
    end as is_24yo_ugrad_cte_grad_int,

    case
        when
            ugrad_status = 'Graduated'
            and ugrad_actual_end_date <= date((contact_kipp_hs_class + 4), 08, 31)
        then 1
        else 0
    end as is_4yr_ugrad_grad_int,

    case
        when
            ugrad_status = 'Graduated'
            and ugrad_actual_end_date <= date((contact_kipp_hs_class + 5), 08, 31)
        then 1
        else 0
    end as is_5yr_ugrad_grad_int,

    case
        when
            ugrad_status = 'Graduated'
            and ugrad_actual_end_date <= date((contact_kipp_hs_class + 6), 08, 31)
        then 1
        else 0
    end as is_6yr_ugrad_grad_int,
from {{ ref("int_kippadb__enrollment_pivot") }}
