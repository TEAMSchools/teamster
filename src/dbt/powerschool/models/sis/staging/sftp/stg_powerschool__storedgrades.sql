with
    storedgrades as (
        select
            * except (
                source_file_name,
                absences,
                datestored,
                dcid,
                earnedcrhrs,
                excludefromclassrank,
                excludefromgpa,
                excludefromgradesuppression,
                excludefromgraduation,
                excludefromhonorroll,
                excludefromtranscripts,
                gpa_addedvalue,
                gpa_custom2,
                gpa_points,
                grade_level,
                gradereplacementpolicy_id,
                isearnedcrhrsfromgb,
                ispotentialcrhrsfromgb,
                percent,
                potentialcrhrs,
                replaced_dcid,
                schoolid,
                sectionid,
                studentid,
                tardies,
                termid,
                transaction_date,
                whomodifiedid,
                comment
            ),

            comment as comment_value,
            gradescale_name as gradescale_name_unweighted,

            cast(dcid as int) as dcid,
            cast(excludefromclassrank as int) as excludefromclassrank,
            cast(excludefromgpa as int) as excludefromgpa,
            cast(excludefromhonorroll as int) as excludefromhonorroll,
            cast(grade_level as int) as grade_level,
            cast(gradereplacementpolicy_id as int) as gradereplacementpolicy_id,
            cast(replaced_dcid as int) as replaced_dcid,
            cast(schoolid as int) as schoolid,
            cast(sectionid as int) as sectionid,
            cast(studentid as int) as studentid,
            cast(termid as int) as termid,
            cast(whomodifiedid as int) as whomodifiedid,

            cast(absences as float64) as absences,
            cast(earnedcrhrs as float64) as earnedcrhrs,
            cast(gpa_addedvalue as float64) as gpa_addedvalue,
            cast(gpa_custom2 as float64) as gpa_custom2,
            cast(gpa_points as float64) as gpa_points,
            cast(percent as float64) as `percent`,
            cast(potentialcrhrs as float64) as potentialcrhrs,
            cast(tardies as float64) as tardies,

            cast(datestored as date) as datestored,

            cast(transaction_date as timestamp) as transaction_date,

            cast(null as string) as custom,

            cast(
                cast(excludefromgradesuppression as bool) as int
            ) as excludefromgradesuppression,
            cast(cast(excludefromgraduation as bool) as int) as excludefromgraduation,
            cast(cast(excludefromtranscripts as bool) as int) as excludefromtranscripts,
            cast(cast(isearnedcrhrsfromgb as bool) as int) as isearnedcrhrsfromgb,
            cast(cast(ispotentialcrhrsfromgb as bool) as int) as ispotentialcrhrsfromgb,

            cast(left(termid, 2) as int) as yearid,

            left(storecode, 1) as storecode_type,
        from {{ source("powerschool_sftp", "src_powerschool__storedgrades") }}
    )

select
    *,

    yearid + 1990 as academic_year,
    yearid + 1991 as fiscal_year,

    percent / 100.000 as percent_decimal,
from storedgrades
