select
    id,
    `name`,
    contact__c as contact,
    date__c as `date`,
    test_type__c as test_type,
    subject__c as `subject`,
    scoring_irregularity__c as scoring_irregularity,
    physical_training_requirement_passed__c as physical_training_requirement_passed,
    qualified_air_force__c as qualified_air_force,
    qualified_army__c as qualified_army,
    qualified_coast_guard__c as qualified_coast_guard,
    qualified_marine_corps__c as qualified_marine_corps,
    qualified_navy__c as qualified_navy,
    total_qualified_military_branches__c as total_qualified_military_branches,

    concat(
        format_date('%b', date__c), ' ', format_date('%g', date__c)
    ) as administration_round,

    if(act_composite__c = 0, null, act_composite__c) as act_composite,
    if(act_ela__c = 0, null, act_ela__c) as act_ela,
    if(act_english__c = 0, null, act_english__c) as act_english,
    if(act_math__c = 0, null, act_math__c) as act_math,
    if(act_reading__c = 0, null, act_reading__c) as act_reading,
    if(act_science__c = 0, null, act_science__c) as act_science,
    if(act_stem__c = 0, null, act_stem__c) as act_stem,
    if(act_writing__c = 0, null, act_writing__c) as act_writing,

    if(sat_total_score__c = 0, null, sat_total_score__c) as sat_total_score,
    if(sat_ebrw__c = 0, null, sat_ebrw__c) as sat_ebrw,
    if(sat_essay_analysis__c = 0, null, sat_essay_analysis__c) as sat_essay_analysis,
    if(sat_essay_reading__c = 0, null, sat_essay_reading__c) as sat_essay_reading,
    if(sat_essay_writing__c = 0, null, sat_essay_writing__c) as sat_essay_writing,
    if(sat_math__c = 0, null, sat_math__c) as sat_math,
    if(sat_math_test_score__c = 0, null, sat_math_test_score__c) as sat_math_test_score,
    if(
        sat_reading_test_score__c = 0, null, sat_reading_test_score__c
    ) as sat_reading_test_score,
    if(sat_verbal__c = 0, null, sat_verbal__c) as sat_verbal,
    if(sat_writing__c = 0, null, sat_writing__c) as sat_writing,
    if(
        sat_critical_reading_pre_2016__c = 0, null, sat_critical_reading_pre_2016__c
    ) as sat_critical_reading_pre_2016,
    if(sat_math_pre_2016__c = 0, null, sat_math_pre_2016__c) as sat_math_pre_2016,
    if(
        sat_writing_and_language_test_score__c = 0,
        null,
        sat_writing_and_language_test_score__c
    ) as sat_writing_and_language_test_score,
    if(
        sat_writing_pre_2016__c = 0, null, sat_writing_pre_2016__c
    ) as sat_writing_pre_2016,

    if(ap__c = 0, null, ap__c) as ap,

    if(psat_total_score__c = 0, null, psat_total_score__c) as psat_total_score,
    if(psat_ebrw__c = 0, null, psat_ebrw__c) as psat_ebrw,
    if(psat_math__c = 0, null, psat_math__c) as psat_math,
    if(
        psat_math_test_score__c = 0, null, psat_math_test_score__c
    ) as psat_math_test_score,
    if(
        psat_reading_test_score__c = 0, null, psat_reading_test_score__c
    ) as psat_reading_test_score,
    if(psat_verbal__c = 0, null, psat_verbal__c) as psat_verbal,
    if(psat_writing__c = 0, null, psat_writing__c) as psat_writing,
    if(
        psat_writing_and_language_test_score__c = 0,
        null,
        psat_writing_and_language_test_score__c
    ) as psat_writing_and_language_test_score,
    if(
        psat_critical_reading_pre_2016__c = 0, null, psat_critical_reading_pre_2016__c
    ) as psat_critical_reading_pre_2016,
    if(psat_math_pre_2016__c = 0, null, psat_math_pre_2016__c) as psat_math_pre_2016,
    if(
        psat_writing_pre_2016__c = 0, null, psat_writing_pre_2016__c
    ) as psat_writing_pre_2016,
    if(afqt_score__c = 0, null, afqt_score__c) as afqt_score,

    {{ date_to_fiscal_year(date_field="date__c", start_month=7, year_source="start") }}
    as academic_year,
from {{ source("kippadb", "standardized_test") }}
where not isdeleted
