with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("illuminate", "psat_2023"),
                    source("illuminate", "psat_2024"),
                ],
                where="not _fivetran_deleted",
            )
        }}
    )

select
    student_id,

    psat_2023_cbstudentid as cb_student_id,
    psat_2023_districtstudentid as district_student_id,
    psat_2023_localstudentid as local_student_id,
    psat_2023_statestudentid as state_student_id,

    psat_2023_id as id,
    psat_2023_formcode as form_code,

    psat_2023_testdate as test_date,
    psat_2023_reportdate as report_date,
    psat_2023_selfassessmentdate as self_assessment_date,

    psat_2023_latestpsataccesscode as latest_psat_access_code,
    psat_2023_notvalidnationalmerit as not_valid_national_merit,
    psat_2023_selectionindex as selection_index,

    psat_2023_studentfirstname as student_first_name,
    psat_2023_studentlastname as student_last_name,
    psat_2023_cohortyear as cohort_year,
    psat_2023_birthdate as birth_date,
    psat_2023_hsstudent as hs_student,

    psat_2023_totalreppercentile as total_rep_percentile,
    psat_2023_totalusrpercentile as total_usr_percentile,

    psat_2023_advancedmathreppercentile as advanced_math_rep_percentile,
    psat_2023_advancedmathusrpercentile as advanced_math_usr_percentile,

    psat_2023_algebrareppercentile as algebra_rep_percentile,
    psat_2023_algebrausrpercentile as algebra_usr_percentile,

    psat_2023_commandreppercentile as command_rep_percentile,
    psat_2023_commandusrpercentile as command_usr_percentile,

    psat_2023_ebrwreppercentile as ebrw_rep_percentile,
    psat_2023_ebrwusrpercentile as ebrw_usr_percentile,
    psat_2023_ebrwccrbenchmark as ebrw_ccr_benchmark,

    psat_2023_engconventionsreppercentile as eng_conventions_rep_percentile,
    psat_2023_engconventionsusrpercentile as eng_conventions_usr_percentile,

    psat_2023_expressionideareppercentile as expression_idea_rep_percentile,
    psat_2023_expressionideausrpercentile as expression_idea_usr_percentile,

    psat_2023_histreppercentile as hist_rep_percentile,
    psat_2023_histusrpercentile as hist_usr_percentile,

    psat_2023_mathreppercentile as math_rep_percentile,
    psat_2023_mathusrpercentile as math_usr_percentile,
    psat_2023_mathccrbenchmark as math_ccr_benchmark,

    psat_2023_mathsectreppercentile as math_sect_rep_percentile,
    psat_2023_mathsectusrpercentile as math_sect_usr_percentile,

    psat_2023_problemsolvereppercentile as problem_solve_rep_percentile,
    psat_2023_problemsolveusrpercentile as problem_solve_usr_percentile,

    psat_2023_readingreppercentile as reading_rep_percentile,
    psat_2023_readingusrpercentile as reading_usr_percentile,

    psat_2023_scireppercentile as sci_rep_percentile,
    psat_2023_sciusrpercentile as sci_usr_percentile,

    psat_2023_wordscontextreppercentile as words_context_rep_percentile,
    psat_2023_wordscontextusrpercentile as words_context_usr_percentile,

    psat_2023_writinglangreppercentile as writing_lang_rep_percentile,
    psat_2023_writinglangusrpercentile as writing_lang_usr_percentile,

    psat_2023_apseminar as ap_seminar,

    safe_cast(psat_2023_totalscore as numeric) as total_score,
    safe_cast(psat_2023_advancedmathsubscore as numeric) as advanced_math_subscore,
    safe_cast(
        psat_2023_commandevidencesubscore as numeric
    ) as command_evidence_subscore,
    safe_cast(
        psat_2023_ebreadwritesectionscore as numeric
    ) as eb_read_write_section_score,
    safe_cast(psat_2023_englishconvsubscore as numeric) as english_conv_subscore,
    safe_cast(
        psat_2023_expressionideassubscore as numeric
    ) as expression_ideas_subscore,
    safe_cast(psat_2023_heartalgebrasubscore as numeric) as heart_algebra_subscore,
    safe_cast(psat_2023_historycrosstestscore as numeric) as history_cross_test_score,
    safe_cast(psat_2023_mathtestscore as numeric) as math_test_score,
    safe_cast(psat_2023_mathsectionscore as numeric) as math_section_score,
    safe_cast(psat_2023_probsolvedatasubscore as numeric) as prob_solve_data_subscore,
    safe_cast(psat_2023_readingtestscore as numeric) as reading_test_score,
    safe_cast(psat_2023_relevantwordssubscore as numeric) as relevant_words_subscore,
    safe_cast(psat_2023_sciencecrosstestscore as numeric) as science_cross_test_score,
    safe_cast(psat_2023_writingtestscore as numeric) as writing_test_score,

    nullif(psat_2023_newdistrictid, '') as new_district_id,
    nullif(psat_2023_newssid, '') as new_ssid,
    nullif(psat_2023_gradeassessed, '') as grade_assessed,
    nullif(psat_2023_firstchoicemajor, '') as first_choice_major,
    nullif(psat_2023_gpa, '') as gpa,
    nullif(psat_2023_numyearsgrade912, '') as num_years_grade_9_12,
    nullif(psat_2023_studentmiddleinitial, '') as student_middle_initial,
    nullif(psat_2023_aparthist, '') as ap_arthist,
    nullif(psat_2023_apbio, '') as ap_bio,
    nullif(psat_2023_apcalc, '') as ap_calc,
    nullif(psat_2023_apchem, '') as ap_chem,
    nullif(psat_2023_apcompgovpol, '') as ap_compgovpol,
    nullif(psat_2023_apcompsci, '') as ap_compsci,
    nullif(psat_2023_apenglang, '') as ap_englang,
    nullif(psat_2023_apenglit, '') as ap_englit,
    nullif(psat_2023_apenvsci, '') as ap_envsci,
    nullif(psat_2023_apeurohist, '') as ap_eurohist,
    nullif(psat_2023_aphumgeo, '') as ap_humgeo,
    nullif(psat_2023_apmacecon, '') as ap_macecon,
    nullif(psat_2023_apmicecon, '') as ap_micecon,
    nullif(psat_2023_apmusic, '') as ap_music,
    nullif(psat_2023_apphysi, '') as ap_physi,
    nullif(psat_2023_apphysii, '') as ap_physii,
    nullif(psat_2023_apphysmag, '') as ap_physmag,
    nullif(psat_2023_apphysmech, '') as ap_physmech,
    nullif(psat_2023_appsych, '') as ap_psych,
    nullif(psat_2023_apstat, '') as ap_stat,
    nullif(psat_2023_apusgovpol, '') as ap_usgovpol,
    nullif(psat_2023_apushist, '') as ap_ushist,
    nullif(psat_2023_apworldhist, '') as ap_worldhist,
from union_relations
