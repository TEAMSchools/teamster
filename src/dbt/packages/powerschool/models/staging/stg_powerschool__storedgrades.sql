{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {"name": "percent", "extract": "double_value"},
            {"name": "absences", "extract": "double_value"},
            {"name": "tardies", "extract": "double_value"},
            {"name": "potentialcrhrs", "extract": "double_value"},
            {"name": "earnedcrhrs", "extract": "double_value"},
            {"name": "grade_level", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "excludefromgpa", "extract": "int_value"},
            {"name": "gpa_points", "extract": "double_value"},
            {"name": "gpa_addedvalue", "extract": "double_value"},
            {"name": "gpa_custom2", "extract": "double_value"},
            {"name": "excludefromclassrank", "extract": "int_value"},
            {"name": "excludefromhonorroll", "extract": "int_value"},
            {"name": "isearnedcrhrsfromgb", "extract": "int_value"},
            {"name": "ispotentialcrhrsfromgb", "extract": "int_value"},
            {"name": "excludefromtranscripts", "extract": "int_value"},
            {"name": "replaced_dcid", "extract": "int_value"},
            {"name": "excludefromgraduation", "extract": "int_value"},
            {"name": "excludefromgradesuppression", "extract": "int_value"},
            {"name": "gradereplacementpolicy_id", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}},

with_yearid as (
    select
        *,
        left(storecode, 2) as storecode_type,
        cast(left(cast(termid as string), 2) as int) as yearid,
    from staging
),

with_years as (
    select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
    from with_yearid
)

select
    *,
    case
        /* unweighted pre-2016 */
        when academic_year < 2016 and gradescale_name = 'NCA Honors'
        then 'NCA 2011'
        /* unweighted 2016-2018 */
        when academic_year >= 2016 and gradescale_name = 'NCA Honors'
        then 'KIPP NJ 2016 (5-12)'
        /* unweighted 2019+ */
        when academic_year >= 0 and gradescale_name = 'KIPP NJ 2019 (5-12) Weighted'
        then 'KIPP NJ 2019 (5-12) Unweighted'
        /* MISSING GRADESCALE - default pre-2016 */
        when
            academic_year < 2016
            and (ifnull(gradescale_name, '') = '' or gradescale_name = 'NULL')
        then 'NCA 2011'
        /* MISSING GRADESCALE - default 2016+ */
        when
            academic_year >= 2016
            and (ifnull(gradescale_name, '') = '' or gradescale_name = 'NULL')
        then 'KIPP NJ 2016 (5-12)'
        /* return original grade scale */
        else gradescale_name
    end as gradescale_name_unweighted,
from with_years
