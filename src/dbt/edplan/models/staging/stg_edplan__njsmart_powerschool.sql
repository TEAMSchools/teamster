{% set filtered_columns = dbt_utils.get_filtered_columns_in_relation(
    from=source("edplan", "src_edplan__njsmart_powerschool"),
    except=[
        "_dagster_partition_fiscal_year",
        "_dagster_partition_date",
        "_dagster_partition_hour",
        "_dagster_partition_minute",
        "dob",
        "first_name",
        "last_name",
    ],
) %}

{% set surrogate_key_field_list = ["state_studentnumber"] %}

{% for item in filtered_columns %}
    {% if item != "state_studentnumber" %}
        {{ surrogate_key_field_list.append(item) or "" }}
    {% endif %}
{% endfor %}

with
    -- trunk-ignore(sqlfluff/ST03)
    staging as (
        select
            nj_se_earlyintervention,
            nj_se_parentalconsentobtained,
            ti_serv_counseling,
            ti_serv_occup,
            ti_serv_other,
            ti_serv_physical,
            ti_serv_speech,
            _dagster_partition_date as effective_date,
            _dagster_partition_fiscal_year as fiscal_year,

            _dagster_partition_fiscal_year - 1 as academic_year,

            safe_cast(student_number as int) as student_number,
            safe_cast(nj_se_delayreason as int) as nj_se_delayreason,
            safe_cast(nj_se_placement as int) as nj_se_placement,
            safe_cast(state_studentnumber as int) as state_studentnumber,

            safe_cast(nj_timeinregularprogram as numeric) as nj_timeinregularprogram,

            parse_date('%m/%d/%Y', nj_se_eligibilityddate) as nj_se_eligibilityddate,
            parse_date(
                '%m/%d/%Y', nj_se_lastiepmeetingdate
            ) as nj_se_lastiepmeetingdate,
            parse_date(
                '%m/%d/%Y', nj_se_parentalconsentdate
            ) as nj_se_parentalconsentdate,
            parse_date('%m/%d/%Y', nj_se_reevaluationdate) as nj_se_reevaluationdate,
            parse_date('%m/%d/%Y', nj_se_referraldate) as nj_se_referraldate,
            parse_date(
                '%m/%d/%Y', nj_se_initialiepmeetingdate
            ) as nj_se_initialiepmeetingdate,
            parse_date(
                '%m/%d/%Y', nj_se_consenttoimplementdate
            ) as nj_se_consenttoimplementdate,

            right(
                concat('0', regexp_extract(special_education, r'(\d+)\.?')), 2
            ) as special_education,

            {{ dbt_utils.generate_surrogate_key(field_list=surrogate_key_field_list) }}
            as row_hash,
        from {{ source("edplan", "src_edplan__njsmart_powerschool") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="staging",
                partition_by="row_hash, fiscal_year",
                order_by="effective_date asc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    if(
        nj_se_parentalconsentobtained in ('N', 'R'),
        null,
        case
            when special_education in ('00', '99')
            then null
            when special_education = '17'
            then 'SPED SPEECH'
            when special_education is not null
            then 'SPED'
        end
    ) as spedlep,

    if(
        nj_se_parentalconsentobtained in ('N', 'R'),
        null,
        case
            special_education
            when '01'
            then 'AI'
            when '02'
            then 'AUT'
            when '03'
            then 'CMI'
            when '04'
            then 'CMO'
            when '05'
            then 'CSE'
            when '06'
            then 'CI'
            when '07'
            then 'ED'
            when '08'
            then 'MD'
            when '09'
            then 'DB'
            when '10'
            then 'OI'
            when '11'
            then 'OHI'
            when '12'
            then 'PSD'
            when '13'
            then 'SM'
            when '14'
            then 'SLD'
            when '15'
            then 'TBI'
            when '16'
            then 'VI'
            when '17'
            then 'ESLS'
            else special_education
        end
    ) as special_education_code,

    coalesce(
        date_sub(
            lead(effective_date, 1) over (
                partition by student_number, fiscal_year order by effective_date asc
            ),
            interval 1 day
        ),
        date(fiscal_year, 6, 30)
    ) as effective_end_date,
from deduplicate
