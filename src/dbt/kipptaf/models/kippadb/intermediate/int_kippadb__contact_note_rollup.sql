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
                then 'AS'
                when `subject` like 'Grad Plan%'
                then 'GP'
                when regexp_contains(`subject`, r'SC\d')
                then 'SC'
                when `subject` like 'DP%'
                then replace(regexp_replace(`subject`, r'[:-]', ''), ' ', '_')
                when `subject` like 'BGP%'
                then replace(regexp_replace(`subject`, r'[:-]', ''), ' ', '_')
                when `subject` like 'Q%SM%'
                then regexp_extract(`subject`, r'Q\d\s?(SM\d)')
                when `subject` like '%HV'
                then 'HV'
            end as contact_subject,
            case
                when regexp_contains(`subject`, r'Q\d')
                then regexp_extract(`subject`, r'Q\d')
                else ''
            end as contact_term,
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
    `AS1` as `AS1_date`,
    `AS2` as `AS2_date`,
    `AS3` as `AS3_date`,
    `AS4` as `AS4_date`,
    `AS5` as `AS5_date`,
    `AS6` as `AS6_date`,
    `AS7` as `AS7_date`,
    `AS8` as `AS8_date`,
    `AS9` as `AS9_date`,
    `AS10` as `AS10_date`,
    `AS11` as `AS11_date`,
    `AS12` as `AS12_date`,
    `AS13` as `AS13_date`,
    `AS14` as `AS14_date`,
    `AS15` as `AS15_date`,
    `AS16` as `AS16_date`,
    `AS17` as `AS17_date`,
    `AS18` as `AS18_date`,
    `AS19` as `AS19_date`,
    `AS20` as `AS20_date`,
    `AS21` as `AS21_date`,
    `AS22` as `AS22_date`,
    `AS23` as `AS23_date`,
    `AS24` as `AS24_date`,
    if(bqutil.fn.typeof(`AS1`) = 'DATE', 1, 0) as `AS1`,
    if(bqutil.fn.typeof(`AS2`) = 'DATE', 1, 0) as `AS2`,
    if(bqutil.fn.typeof(`AS3`) = 'DATE', 1, 0) as `AS3`,
    if(bqutil.fn.typeof(`AS4`) = 'DATE', 1, 0) as `AS4`,
    if(bqutil.fn.typeof(`AS5`) = 'DATE', 1, 0) as `AS5`,
    if(bqutil.fn.typeof(`AS6`) = 'DATE', 1, 0) as `AS6`,
    if(bqutil.fn.typeof(`AS7`) = 'DATE', 1, 0) as `AS7`,
    if(bqutil.fn.typeof(`AS8`) = 'DATE', 1, 0) as `AS8`,
    if(bqutil.fn.typeof(`AS9`) = 'DATE', 1, 0) as `AS9`,
    if(bqutil.fn.typeof(`AS10`) = 'DATE', 1, 0) as `AS10`,
    if(bqutil.fn.typeof(`AS11`) = 'DATE', 1, 0) as `AS11`,
    if(bqutil.fn.typeof(`AS12`) = 'DATE', 1, 0) as `AS12`,
    if(bqutil.fn.typeof(`AS13`) = 'DATE', 1, 0) as `AS13`,
    if(bqutil.fn.typeof(`AS14`) = 'DATE', 1, 0) as `AS14`,
    if(bqutil.fn.typeof(`AS15`) = 'DATE', 1, 0) as `AS15`,
    if(bqutil.fn.typeof(`AS16`) = 'DATE', 1, 0) as `AS16`,
    if(bqutil.fn.typeof(`AS17`) = 'DATE', 1, 0) as `AS17`,
    if(bqutil.fn.typeof(`AS18`) = 'DATE', 1, 0) as `AS18`,
    if(bqutil.fn.typeof(`AS19`) = 'DATE', 1, 0) as `AS19`,
    if(bqutil.fn.typeof(`AS20`) = 'DATE', 1, 0) as `AS20`,
    if(bqutil.fn.typeof(`AS21`) = 'DATE', 1, 0) as `AS21`,
    if(bqutil.fn.typeof(`AS22`) = 'DATE', 1, 0) as `AS22`,
    if(bqutil.fn.typeof(`AS23`) = 'DATE', 1, 0) as `AS23`,
    if(bqutil.fn.typeof(`AS24`) = 'DATE', 1, 0) as `AS24`,
    if(bqutil.fn.typeof(`SC`) = 'DATE', 1, 0) as `SC`,
    if(bqutil.fn.typeof(`CCDM`) = 'DATE', 1, 0) as `CCDM`,
    if(bqutil.fn.typeof(`PSC`) = 'DATE', 1, 0) as `PSC`,
    if(bqutil.fn.typeof(`BBB`) = 'DATE', 1, 0) as `BBB`,
    if(bqutil.fn.typeof(`BM`) = 'DATE', 1, 0) as `BM`,
    if(bqutil.fn.typeof(`GP`) = 'DATE', 1, 0) as `GP`,
    if(bqutil.fn.typeof(`HV`) = 'DATE', 1, 0) as `HV`,
    if(bqutil.fn.typeof(`MC1`) = 'DATE', 1, 0) as `MC1`,
    if(bqutil.fn.typeof(`MC2`) = 'DATE', 1, 0) as `MC2`,
    if(bqutil.fn.typeof(`DP_4year`) = 'DATE', 1, 0) as `DP_4year`,
    if(bqutil.fn.typeof(`DP_2year`) = 'DATE', 1, 0) as `DP_2year`,
    if(bqutil.fn.typeof(`DP_CTE`) = 'DATE', 1, 0) as `DP_CTE`,
    if(bqutil.fn.typeof(`DP_Military`) = 'DATE', 1, 0) as `DP_Military`,
    if(bqutil.fn.typeof(`DP_Workforce`) = 'DATE', 1, 0) as `DP_Workforce`,
    if(bqutil.fn.typeof(`DP_Unknown`) = 'DATE', 1, 0) as `DP_Unknown`,
    if(bqutil.fn.typeof(`BGP_4year`) = 'DATE', 1, 0) as `BGP_4year`,
    if(bqutil.fn.typeof(`BGP_2year`) = 'DATE', 1, 0) as `BGP_2year`,
    if(bqutil.fn.typeof(`BGP_CTE`) = 'DATE', 1, 0) as `BGP_CTE`,
    if(bqutil.fn.typeof(`BGP_Military`) = 'DATE', 1, 0) as `BGP_Military`,
    if(bqutil.fn.typeof(`BGP_Workforce`) = 'DATE', 1, 0) as `BGP_Workforce`,
    if(bqutil.fn.typeof(`BGP_Unknown`) = 'DATE', 1, 0) as `BGP_Unknown`,
    if(bqutil.fn.typeof(`HD_P`) = 'DATE', 1, 0) as `HD_P`,
    if(bqutil.fn.typeof(`HD_NR`) = 'DATE', 1, 0) as `HD_NR`,
    if(bqutil.fn.typeof(`TD_P`) = 'DATE', 1, 0) as `TD_P`,
    if(bqutil.fn.typeof(`TD_NR`) = 'DATE', 1, 0) as `TD_NR`,
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
            'SC',
            'CCDM',
            'HV',
            'PSC',
            'BBB',
            'BM',
            'GP',
            'MC1',
            'MC2',
            'DP_4year',
            'DP_2year',
            'DP_CTE',
            'DP_Military',
            'DP_Workforce',
            'DP_Unknown',
            'BGP_4year',
            'BGP_2year',
            'BGP_CTE',
            'BGP_Military',
            'BGP_Workforce',
            'BGP_Unknown',
            'HD_P',
            'HD_NR',
            'TD_P',
            'TD_NR'
        )
    )
