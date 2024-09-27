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
                then 'AS' || regexp_extract(subject, r'Advising\s*Session\s*#?\s*(\d+)')
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
                else `subject`
            end as contact_subject,

            if(
                regexp_contains(`subject`, r'Q\d'),
                regexp_extract(`subject`, r'Q\d'),
                ''
            ) as contact_term,

            {{
                teamster_utils.date_to_fiscal_year(
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
                teamster_utils.date_to_fiscal_year(
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

    `AS1` as as1_date,
    `AS2` as as2_date,
    `AS3` as as3_date,
    `AS4` as as4_date,
    `AS5` as as5_date,
    `AS6` as as6_date,
    `AS7` as as7_date,
    `AS8` as as8_date,
    `AS9` as as9_date,
    `AS10` as as10_date,
    `AS11` as as11_date,
    `AS12` as as12_date,
    `AS13` as as13_date,
    `AS14` as as14_date,
    `AS15` as as15_date,
    `AS16` as as16_date,
    `AS17` as as17_date,
    `AS18` as as18_date,
    `AS19` as as19_date,
    `AS20` as as20_date,
    `AS21` as as21_date,
    `AS22` as as22_date,
    `AS23` as as23_date,
    `AS24` as as24_date,
    `CC1` as cc1_date,
    `CC2` as cc2_date,
    `CC3` as cc3_date,
    `CC4` as cc4_date,
    `CC5` as cc5_date,

    if(bqutil.fn.typeof(`AS1`) = 'DATE', 1, 0) as as1,
    if(bqutil.fn.typeof(`AS2`) = 'DATE', 1, 0) as as2,
    if(bqutil.fn.typeof(`AS3`) = 'DATE', 1, 0) as as3,
    if(bqutil.fn.typeof(`AS4`) = 'DATE', 1, 0) as as4,
    if(bqutil.fn.typeof(`AS5`) = 'DATE', 1, 0) as as5,
    if(bqutil.fn.typeof(`AS6`) = 'DATE', 1, 0) as as6,
    if(bqutil.fn.typeof(`AS7`) = 'DATE', 1, 0) as as7,
    if(bqutil.fn.typeof(`AS8`) = 'DATE', 1, 0) as as8,
    if(bqutil.fn.typeof(`AS9`) = 'DATE', 1, 0) as as9,
    if(bqutil.fn.typeof(`AS10`) = 'DATE', 1, 0) as as10,
    if(bqutil.fn.typeof(`AS11`) = 'DATE', 1, 0) as as11,
    if(bqutil.fn.typeof(`AS12`) = 'DATE', 1, 0) as as12,
    if(bqutil.fn.typeof(`AS13`) = 'DATE', 1, 0) as as13,
    if(bqutil.fn.typeof(`AS14`) = 'DATE', 1, 0) as as14,
    if(bqutil.fn.typeof(`AS15`) = 'DATE', 1, 0) as as15,
    if(bqutil.fn.typeof(`AS16`) = 'DATE', 1, 0) as as16,
    if(bqutil.fn.typeof(`AS17`) = 'DATE', 1, 0) as as17,
    if(bqutil.fn.typeof(`AS18`) = 'DATE', 1, 0) as as18,
    if(bqutil.fn.typeof(`AS19`) = 'DATE', 1, 0) as as19,
    if(bqutil.fn.typeof(`AS20`) = 'DATE', 1, 0) as as20,
    if(bqutil.fn.typeof(`AS21`) = 'DATE', 1, 0) as as21,
    if(bqutil.fn.typeof(`AS22`) = 'DATE', 1, 0) as as22,
    if(bqutil.fn.typeof(`AS23`) = 'DATE', 1, 0) as as23,
    if(bqutil.fn.typeof(`AS24`) = 'DATE', 1, 0) as as24,
    if(bqutil.fn.typeof(`BBB`) = 'DATE', 1, 0) as bbb,
    if(bqutil.fn.typeof(`BGP_2year`) = 'DATE', 1, 0) as bgp_2year,
    if(bqutil.fn.typeof(`BGP_4year`) = 'DATE', 1, 0) as bgp_4year,
    if(bqutil.fn.typeof(`BGP_CTE`) = 'DATE', 1, 0) as bgp_cte,
    if(bqutil.fn.typeof(`BGP_Military`) = 'DATE', 1, 0) as bgp_military,
    if(bqutil.fn.typeof(`BGP_Unknown`) = 'DATE', 1, 0) as bgp_unknown,
    if(bqutil.fn.typeof(`BGP_Workforce`) = 'DATE', 1, 0) as bgp_workforce,
    if(bqutil.fn.typeof(`BM`) = 'DATE', 1, 0) as bm,
    if(bqutil.fn.typeof(`CC1`) = 'DATE', 1, 0) as cc1,
    if(bqutil.fn.typeof(`CC2`) = 'DATE', 1, 0) as cc2,
    if(bqutil.fn.typeof(`CC3`) = 'DATE', 1, 0) as cc3,
    if(bqutil.fn.typeof(`CC4`) = 'DATE', 1, 0) as cc4,
    if(bqutil.fn.typeof(`CC5`) = 'DATE', 1, 0) as cc5,
    if(bqutil.fn.typeof(`CCDM`) = 'DATE', 1, 0) as ccdm,
    if(bqutil.fn.typeof(`DP_2year`) = 'DATE', 1, 0) as dp_2year,
    if(bqutil.fn.typeof(`DP_4year`) = 'DATE', 1, 0) as dp_4year,
    if(bqutil.fn.typeof(`DP_CTE`) = 'DATE', 1, 0) as dp_cte,
    if(bqutil.fn.typeof(`DP_Military`) = 'DATE', 1, 0) as dp_military,
    if(bqutil.fn.typeof(`DP_Unknown`) = 'DATE', 1, 0) as dp_unknown,
    if(bqutil.fn.typeof(`DP_Workforce`) = 'DATE', 1, 0) as dp_workforce,
    if(bqutil.fn.typeof(`GP`) = 'DATE', 1, 0) as gp,
    if(bqutil.fn.typeof(`HD_NR`) = 'DATE', 1, 0) as hd_nr,
    if(bqutil.fn.typeof(`HD_P`) = 'DATE', 1, 0) as hd_p,
    if(bqutil.fn.typeof(`HV`) = 'DATE', 1, 0) as hv,
    if(bqutil.fn.typeof(`MC1`) = 'DATE', 1, 0) as mc1,
    if(bqutil.fn.typeof(`MC2`) = 'DATE', 1, 0) as mc2,
    if(bqutil.fn.typeof(`PSC`) = 'DATE', 1, 0) as psc,
    if(bqutil.fn.typeof(`SC`) = 'DATE', 1, 0) as sc,
    if(bqutil.fn.typeof(`TD_NR`) = 'DATE', 1, 0) as td_nr,
    if(bqutil.fn.typeof(`TD_P`) = 'DATE', 1, 0) as td_p,
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
            'TD_P'
        )
    )
