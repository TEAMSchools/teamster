{# The KIPP Forward early-application goals by GPA band (#6190), as an array of
   structs for unnest(). The criteria scaffold scores seniors against these and
   the tracker's Summary tab labels its rows from them, so a band, bar, count, or
   label changes here and nowhere else. required_type is ED, EA, or any;
   sets_aside_full_need marks the goal that does not count the band's full-need
   college again. #}
{% macro early_application_criteria() %}
    [
        struct(
            'ed_80_full_need' as criterion_code,
            1 as criterion_sort,
            '3.75+' as gpa_band,
            '1 ED, full need, 80%+ URM' as criterion_label,
            'ED' as required_type,
            'ED' as type_label,
            80 as urm_bar,
            1 as required_count,
            true as requires_full_need,
            false as sets_aside_full_need
        ),
        struct('ea_78', 2, '3.75+', '2 EA, 78%+ URM', 'EA', 'EA', 78, 2, false, false),
        struct(
            'early_80_full_need',
            3,
            '3.50-3.74',
            '1 ED/EA, full need, 80%+ URM',
            'any',
            'ED or EA',
            80,
            1,
            true,
            false
        ),
        struct(
            'additional_68',
            4,
            '3.50-3.74',
            '2 additional early, 68%+ URM',
            'any',
            'early',
            68,
            2,
            false,
            true
        ),
        struct(
            'early_68',
            5,
            '3.00-3.49',
            '3 early, 68%+ URM',
            'any',
            'early',
            68,
            3,
            false,
            false
        )
    ]
{% endmacro %}
