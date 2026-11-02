-- KIPP Forward early-application goals by GPA band (#6190)
select
    'ed_80_full_need' as criterion_code,
    1 as criterion_sort,
    '3.75+' as gpa_band,
    '1 ED, full need, 80%+ URM' as criterion_label,
    'ED' as required_type,
    'ED' as type_label,
    80 as urm_bar,
    1 as required_count,
    true as requires_full_need,
    false as sets_aside_full_need,

union all

select
    'ea_78' as criterion_code,
    2 as criterion_sort,
    '3.75+' as gpa_band,
    '2 EA, 78%+ URM' as criterion_label,
    'EA' as required_type,
    'EA' as type_label,
    78 as urm_bar,
    2 as required_count,
    false as requires_full_need,
    false as sets_aside_full_need,

union all

select
    'early_80_full_need' as criterion_code,
    3 as criterion_sort,
    '3.50-3.74' as gpa_band,
    '1 ED/EA, full need, 80%+ URM' as criterion_label,
    'any' as required_type,
    'ED or EA' as type_label,
    80 as urm_bar,
    1 as required_count,
    true as requires_full_need,
    false as sets_aside_full_need,

union all

select
    'additional_68' as criterion_code,
    4 as criterion_sort,
    '3.50-3.74' as gpa_band,
    '2 additional early, 68%+ URM' as criterion_label,
    'any' as required_type,
    'early' as type_label,
    68 as urm_bar,
    2 as required_count,
    false as requires_full_need,
    true as sets_aside_full_need,

union all

select
    'early_68' as criterion_code,
    5 as criterion_sort,
    '3.00-3.49' as gpa_band,
    '3 early, 68%+ URM' as criterion_label,
    'any' as required_type,
    'early' as type_label,
    68 as urm_bar,
    3 as required_count,
    false as requires_full_need,
    false as sets_aside_full_need,
