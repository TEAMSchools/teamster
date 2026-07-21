with
    staging as (
        select
            storecode,
            grade,
            behavior,
            comment_value,
            course_name,
            course_number,
            credit_type,
            `log`,
            course_equiv,
            schoolname,
            gradescale_name,
            teacher_name,
            gpa_custom1,
            custom,
            ab_course_cmp_fun_flg,
            ab_course_cmp_ext_crd,
            ab_course_cmp_fun_sch,
            ab_course_cmp_met_cd,
            ab_course_eva_pro_cd,
            ab_course_cmp_sta_cd,
            ab_pri_del_met_cd,
            ab_lng_cd,
            ab_dipl_exam_mark,
            ab_final_mark,
            termbinsname,
            psguid,
            replaced_grade,
            replaced_equivalent_course,
            ip_address,
            whomodifiedtype,
            transaction_date,
            executionid,

            cast(dcid as int) as dcid,
            cast(studentid as int) as studentid,
            cast(sectionid as int) as sectionid,
            cast(termid as int) as termid,
            cast(`percent` as float64) as `percent`,
            cast(absences as float64) as absences,
            cast(tardies as float64) as tardies,
            cast(potentialcrhrs as float64) as potentialcrhrs,
            cast(earnedcrhrs as float64) as earnedcrhrs,
            cast(grade_level as int) as grade_level,
            cast(schoolid as int) as schoolid,
            cast(excludefromgpa as int) as excludefromgpa,
            cast(gpa_points as float64) as gpa_points,
            cast(gpa_addedvalue as float64) as gpa_addedvalue,
            cast(gpa_custom2 as float64) as gpa_custom2,
            cast(excludefromclassrank as int) as excludefromclassrank,
            cast(excludefromhonorroll as int) as excludefromhonorroll,
            cast(isearnedcrhrsfromgb as int) as isearnedcrhrsfromgb,
            cast(ispotentialcrhrsfromgb as int) as ispotentialcrhrsfromgb,
            cast(excludefromtranscripts as int) as excludefromtranscripts,
            cast(replaced_dcid as int) as replaced_dcid,
            cast(excludefromgraduation as int) as excludefromgraduation,
            cast(excludefromgradesuppression as int) as excludefromgradesuppression,
            cast(gradereplacementpolicy_id as int) as gradereplacementpolicy_id,
            cast(whomodifiedid as int) as whomodifiedid,
            cast(datestored as date) as datestored,
        from {{ source("powerschool_dlt", "storedgrades") }}
    ),

    calcs as (
        select
            *,

            `percent` / 100.000 as percent_decimal,

            left(storecode, 1) as storecode_type,

            safe_cast(left(safe_cast(termid as string), 2) as int) as yearid,
        from staging
    ),

    with_years as (
        select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
        from calcs
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
        /* unweighted 2024 honors */
        when gradescale_name = 'KIPP NJ 2024 (5-12) Weighted - Honors'
        then 'KIPP NJ 2019 (5-12) Unweighted'
        /* MISSING GRADESCALE - default pre-2016 */
        when
            academic_year < 2016
            and (coalesce(gradescale_name, '') = '' or gradescale_name = 'NULL')
        then 'NCA 2011'
        /* MISSING GRADESCALE - default 2016+ */
        when
            academic_year >= 2016
            and (coalesce(gradescale_name, '') = '' or gradescale_name = 'NULL')
        then 'KIPP NJ 2016 (5-12)'
        /* return original grade scale */
        else gradescale_name
    end as gradescale_name_unweighted,
from with_years
