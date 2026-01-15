with
    note_union as (
        select
            contact as contact_id,
            `date` as contact_date,

            case
                when `subject` = 'Summer AAS'
                then 'AS'
                when `subject` = 'Housing Deposit Paid'
                then 'HD_P'
                when `subject` = 'Housing Deposit Not Required'
                then 'HD_NR'
                when `subject` = 'Tuition Deposit Paid'
                then 'TD_P'
                when `subject` = 'Tuition Deposit Not Required'
                then 'TD_NR'
                when `subject` like 'Advising Session%'
                then
                    'AS'
                    || regexp_extract(`subject`, r'Advising\s*Session\s*#?\s*(\d+)')
                when `subject` like 'Grad Plan%'
                then 'GP'
                when regexp_contains(`subject`, r'^SC\d')
                then 'SC'
                when regexp_contains(`subject`, r'^CC\d+')
                then regexp_extract(`subject`, r'^CC\d+')
                when `subject` like 'DP%'
                then replace(regexp_replace(`subject`, r'[:-]', ''), ' ', '_')
                when `subject` like 'BGP%'
                then replace(regexp_replace(`subject`, r'[:-]', ''), ' ', '_')
                when `subject` like 'Q%SM%'
                then regexp_extract(`subject`, r'Q\d\s?(SM\d)')
                when `subject` like '%HV'
                then 'HV'
                when `subject` like '%Transition AS'
                then 'TAS'
                else `subject`
            end as contact_subject,

            if(
                regexp_contains(`subject`, r'Q\d'),
                regexp_extract(`subject`, r'Q\d'),
                ''
            ) as contact_term,

            {{
                date_to_fiscal_year(
                    date_field="date", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_kippadb__contact_note") }}

        union all

        select
            contact,
            benchmark_date as contact_date,

            'BM' as contact_subject,
            '' as contact_term,

            {{
                date_to_fiscal_year(
                    date_field="benchmark_date", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ ref("stg_kippadb__college_persistence") }}
        where benchmark_status = 'Complete' and benchmark_period != 'Pre-College'
    ),

    pre_pivot as (
        select
            contact_id,
            academic_year,
            contact_date,

            contact_subject || contact_term as input_column,
        from note_union
        where contact_subject is not null
    )

select
    contact_id,
    academic_year,

    as1 as as1_date,
    as2 as as2_date,
    as3 as as3_date,
    as4 as as4_date,
    as5 as as5_date,
    as6 as as6_date,
    as7 as as7_date,
    as8 as as8_date,
    as9 as as9_date,
    as10 as as10_date,
    as11 as as11_date,
    as12 as as12_date,
    as13 as as13_date,
    as14 as as14_date,
    as15 as as15_date,
    as16 as as16_date,
    as17 as as17_date,
    as18 as as18_date,
    as19 as as19_date,
    as20 as as20_date,
    as21 as as21_date,
    as22 as as22_date,
    as23 as as23_date,
    as24 as as24_date,
    cc1 as cc1_date,
    cc2 as cc2_date,
    cc3 as cc3_date,
    cc4 as cc4_date,
    cc5 as cc5_date,
    tas as tas_date,

    if(bqutil.fn.typeof(as1) = 'DATE', 1, 0) as as1,
    if(bqutil.fn.typeof(as2) = 'DATE', 1, 0) as as2,
    if(bqutil.fn.typeof(as3) = 'DATE', 1, 0) as as3,
    if(bqutil.fn.typeof(as4) = 'DATE', 1, 0) as as4,
    if(bqutil.fn.typeof(as5) = 'DATE', 1, 0) as as5,
    if(bqutil.fn.typeof(as6) = 'DATE', 1, 0) as as6,
    if(bqutil.fn.typeof(as7) = 'DATE', 1, 0) as as7,
    if(bqutil.fn.typeof(as8) = 'DATE', 1, 0) as as8,
    if(bqutil.fn.typeof(as9) = 'DATE', 1, 0) as as9,
    if(bqutil.fn.typeof(as10) = 'DATE', 1, 0) as as10,
    if(bqutil.fn.typeof(as11) = 'DATE', 1, 0) as as11,
    if(bqutil.fn.typeof(as12) = 'DATE', 1, 0) as as12,
    if(bqutil.fn.typeof(as13) = 'DATE', 1, 0) as as13,
    if(bqutil.fn.typeof(as14) = 'DATE', 1, 0) as as14,
    if(bqutil.fn.typeof(as15) = 'DATE', 1, 0) as as15,
    if(bqutil.fn.typeof(as16) = 'DATE', 1, 0) as as16,
    if(bqutil.fn.typeof(as17) = 'DATE', 1, 0) as as17,
    if(bqutil.fn.typeof(as18) = 'DATE', 1, 0) as as18,
    if(bqutil.fn.typeof(as19) = 'DATE', 1, 0) as as19,
    if(bqutil.fn.typeof(as20) = 'DATE', 1, 0) as as20,
    if(bqutil.fn.typeof(as21) = 'DATE', 1, 0) as as21,
    if(bqutil.fn.typeof(as22) = 'DATE', 1, 0) as as22,
    if(bqutil.fn.typeof(as23) = 'DATE', 1, 0) as as23,
    if(bqutil.fn.typeof(as24) = 'DATE', 1, 0) as as24,
    if(bqutil.fn.typeof(bbb) = 'DATE', 1, 0) as bbb,
    if(bqutil.fn.typeof(bgp_2year) = 'DATE', 1, 0) as bgp_2year,
    if(bqutil.fn.typeof(bgp_4year) = 'DATE', 1, 0) as bgp_4year,
    if(bqutil.fn.typeof(bgp_cte) = 'DATE', 1, 0) as bgp_cte,
    if(bqutil.fn.typeof(bgp_military) = 'DATE', 1, 0) as bgp_military,
    if(bqutil.fn.typeof(bgp_unknown) = 'DATE', 1, 0) as bgp_unknown,
    if(bqutil.fn.typeof(bgp_workforce) = 'DATE', 1, 0) as bgp_workforce,
    if(bqutil.fn.typeof(bm) = 'DATE', 1, 0) as bm,
    if(bqutil.fn.typeof(cc1) = 'DATE', 1, 0) as cc1,
    if(bqutil.fn.typeof(cc2) = 'DATE', 1, 0) as cc2,
    if(bqutil.fn.typeof(cc3) = 'DATE', 1, 0) as cc3,
    if(bqutil.fn.typeof(cc4) = 'DATE', 1, 0) as cc4,
    if(bqutil.fn.typeof(cc5) = 'DATE', 1, 0) as cc5,
    if(bqutil.fn.typeof(ccdm) = 'DATE', 1, 0) as ccdm,
    if(bqutil.fn.typeof(dp_2year) = 'DATE', 1, 0) as dp_2year,
    if(bqutil.fn.typeof(dp_4year) = 'DATE', 1, 0) as dp_4year,
    if(bqutil.fn.typeof(dp_cte) = 'DATE', 1, 0) as dp_cte,
    if(bqutil.fn.typeof(dp_military) = 'DATE', 1, 0) as dp_military,
    if(bqutil.fn.typeof(dp_unknown) = 'DATE', 1, 0) as dp_unknown,
    if(bqutil.fn.typeof(dp_workforce) = 'DATE', 1, 0) as dp_workforce,
    if(bqutil.fn.typeof(gp) = 'DATE', 1, 0) as gp,
    if(bqutil.fn.typeof(hd_nr) = 'DATE', 1, 0) as hd_nr,
    if(bqutil.fn.typeof(hd_p) = 'DATE', 1, 0) as hd_p,
    if(bqutil.fn.typeof(hv) = 'DATE', 1, 0) as hv,
    if(bqutil.fn.typeof(mc1) = 'DATE', 1, 0) as mc1,
    if(bqutil.fn.typeof(mc2) = 'DATE', 1, 0) as mc2,
    if(bqutil.fn.typeof(psc) = 'DATE', 1, 0) as psc,
    if(bqutil.fn.typeof(sc) = 'DATE', 1, 0) as sc,
    if(bqutil.fn.typeof(td_nr) = 'DATE', 1, 0) as td_nr,
    if(bqutil.fn.typeof(td_p) = 'DATE', 1, 0) as td_p,
    if(bqutil.fn.typeof(tas) = 'DATE', 1, 0) as tas,
from
    pre_pivot pivot (
        min(contact_date) for input_column in (
            'AS1',
            'AS2',
            'AS3',
            'AS4',
            'AS5',
            'AS6',
            'AS7',
            'AS8',
            'AS9',
            'AS10',
            'AS11',
            'AS12',
            'AS13',
            'AS14',
            'AS15',
            'AS16',
            'AS17',
            'AS18',
            'AS19',
            'AS20',
            'AS21',
            'AS22',
            'AS23',
            'AS24',
            'BBB',
            'BGP_2year',
            'BGP_4year',
            'BGP_CTE',
            'BGP_Military',
            'BGP_Unknown',
            'BGP_Workforce',
            'BM',
            'CC1',
            'CC2',
            'CC3',
            'CC4',
            'CC5',
            'CCDM',
            'DP_2year',
            'DP_4year',
            'DP_CTE',
            'DP_Military',
            'DP_Unknown',
            'DP_Workforce',
            'GP',
            'HD_NR',
            'HD_P',
            'HV',
            'MC1',
            'MC2',
            'PSC',
            'SC',
            'TD_NR',
            'TD_P',
            'TAS'
        )
    )
