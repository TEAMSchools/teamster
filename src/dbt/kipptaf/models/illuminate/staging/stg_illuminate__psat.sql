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
    ),

    combined_years as (
        select
            student_id,

            coalesce(psat_2023_id, psat_2024_id) as id,
            coalesce(psat_2023_formcode, psat_2024_formcode) as form_code,
            coalesce(psat_2023_cbstudentid, psat_2024_cbstudentid) as cb_student_id,
            coalesce(
                psat_2023_districtstudentid, psat_2024_districtstudentid
            ) as district_student_id,
            coalesce(
                psat_2023_localstudentid, psat_2024_localstudentid
            ) as local_student_id,
            coalesce(
                psat_2023_statestudentid, psat_2024_statestudentid
            ) as state_student_id,
            coalesce(psat_2023_testdate, psat_2024_testdate) as test_date,
            coalesce(psat_2023_reportdate, psat_2024_reportdate) as report_date,
            coalesce(
                psat_2023_selfassessmentdate, psat_2024_selfassessmentdate
            ) as self_assessment_date,
            coalesce(
                psat_2023_studentfirstname, psat_2024_studentfirstname
            ) as student_first_name,
            coalesce(
                psat_2023_studentlastname, psat_2024_studentlastname
            ) as student_last_name,
            coalesce(psat_2023_cohortyear, psat_2024_cohortyear) as cohort_year,
            coalesce(psat_2023_birthdate, psat_2024_birthdate) as birth_date,
            coalesce(
                psat_2023_latestpsataccesscode, psat_2024_latestpsataccesscode
            ) as latest_psat_access_code,
            coalesce(
                psat_2023_selectionindex, psat_2024_selectionindex
            ) as selection_index,
            coalesce(psat_2023_hsstudent, psat_2024_hsstudent) as hs_student,
            coalesce(
                psat_2023_notvalidnationalmerit, psat_2024_notvalidnationalmerit
            ) as not_valid_national_merit,
            coalesce(
                psat_2023_ebrwccrbenchmark, psat_2024_ebrwccrbenchmark
            ) as ebrw_ccr_benchmark,
            coalesce(
                psat_2023_mathccrbenchmark, psat_2024_mathccrbenchmark
            ) as math_ccr_benchmark,
            coalesce(psat_2023_totalscore, psat_2024_totalscore) as total_score,
            coalesce(
                psat_2023_historycrosstestscore, psat_2024_historycrosstestscore
            ) as history_cross_test_score,
            coalesce(
                psat_2023_mathtestscore, psat_2024_mathtestscore
            ) as math_test_score,
            coalesce(
                psat_2023_readingtestscore, psat_2024_readingtestscore
            ) as reading_test_score,
            coalesce(
                psat_2023_sciencecrosstestscore, psat_2024_sciencecrosstestscore
            ) as science_cross_test_score,
            coalesce(
                psat_2023_writingtestscore, psat_2024_writingtestscore
            ) as writing_test_score,
            coalesce(
                psat_2023_ebreadwritesectionscore, psat_2024_ebreadwritesectionscore
            ) as eb_read_write_section_score,
            coalesce(
                psat_2023_mathsectionscore, psat_2024_mathsectionscore
            ) as math_section_score,
            coalesce(
                psat_2023_advancedmathsubscore, psat_2024_advancedmathsubscore
            ) as advanced_math_subscore,
            coalesce(
                psat_2023_commandevidencesubscore, psat_2024_commandevidencesubscore
            ) as command_evidence_subscore,
            coalesce(
                psat_2023_englishconvsubscore, psat_2024_englishconvsubscore
            ) as english_conv_subscore,
            coalesce(
                psat_2023_expressionideassubscore, psat_2024_expressionideassubscore
            ) as expression_ideas_subscore,
            coalesce(
                psat_2023_heartalgebrasubscore, psat_2024_heartalgebrasubscore
            ) as heart_algebra_subscore,
            coalesce(
                psat_2023_probsolvedatasubscore, psat_2024_probsolvedatasubscore
            ) as prob_solve_data_subscore,
            coalesce(
                psat_2023_relevantwordssubscore, psat_2024_relevantwordssubscore
            ) as relevant_words_subscore,
            coalesce(
                psat_2023_advancedmathreppercentile, psat_2024_advancedmathreppercentile
            ) as advanced_math_rep_percentile,
            coalesce(
                psat_2023_algebrareppercentile, psat_2024_algebrareppercentile
            ) as algebra_rep_percentile,
            coalesce(
                psat_2023_commandreppercentile, psat_2024_commandreppercentile
            ) as command_rep_percentile,
            coalesce(
                psat_2023_ebrwreppercentile, psat_2024_ebrwreppercentile
            ) as ebrw_rep_percentile,
            coalesce(
                psat_2023_engconventionsreppercentile,
                psat_2024_engconventionsreppercentile
            ) as eng_conventions_rep_percentile,
            coalesce(
                psat_2023_expressionideareppercentile,
                psat_2024_expressionideareppercentile
            ) as expression_idea_rep_percentile,
            coalesce(
                psat_2023_histreppercentile, psat_2024_histreppercentile
            ) as hist_rep_percentile,
            coalesce(
                psat_2023_mathreppercentile, psat_2024_mathreppercentile
            ) as math_rep_percentile,
            coalesce(
                psat_2023_mathsectreppercentile, psat_2024_mathsectreppercentile
            ) as math_sect_rep_percentile,
            coalesce(
                psat_2023_problemsolvereppercentile, psat_2024_problemsolvereppercentile
            ) as problem_solve_rep_percentile,
            coalesce(
                psat_2023_readingreppercentile, psat_2024_readingreppercentile
            ) as reading_rep_percentile,
            coalesce(
                psat_2023_scireppercentile, psat_2024_scireppercentile
            ) as sci_rep_percentile,
            coalesce(
                psat_2023_totalreppercentile, psat_2024_totalreppercentile
            ) as total_rep_percentile,
            coalesce(
                psat_2023_wordscontextreppercentile, psat_2024_wordscontextreppercentile
            ) as words_context_rep_percentile,
            coalesce(
                psat_2023_writinglangreppercentile, psat_2024_writinglangreppercentile
            ) as writing_lang_rep_percentile,
            coalesce(
                psat_2023_advancedmathusrpercentile, psat_2024_advancedmathusrpercentile
            ) as advanced_math_usr_percentile,
            coalesce(
                psat_2023_algebrausrpercentile, psat_2024_algebrausrpercentile
            ) as algebra_usr_percentile,
            coalesce(
                psat_2023_commandusrpercentile, psat_2024_commandusrpercentile
            ) as command_usr_percentile,
            coalesce(
                psat_2023_ebrwusrpercentile, psat_2024_ebrwusrpercentile
            ) as ebrw_usr_percentile,
            coalesce(
                psat_2023_engconventionsusrpercentile,
                psat_2024_engconventionsusrpercentile
            ) as eng_conventions_usr_percentile,
            coalesce(
                psat_2023_expressionideausrpercentile,
                psat_2024_expressionideausrpercentile
            ) as expression_idea_usr_percentile,
            coalesce(
                psat_2023_histusrpercentile, psat_2024_histusrpercentile
            ) as hist_usr_percentile,
            coalesce(
                psat_2023_mathsectusrpercentile, psat_2024_mathsectusrpercentile
            ) as math_sect_usr_percentile,
            coalesce(
                psat_2023_mathusrpercentile, psat_2024_mathusrpercentile
            ) as math_usr_percentile,
            coalesce(
                psat_2023_problemsolveusrpercentile, psat_2024_problemsolveusrpercentile
            ) as problem_solve_usr_percentile,
            coalesce(
                psat_2023_readingusrpercentile, psat_2024_readingusrpercentile
            ) as reading_usr_percentile,
            coalesce(
                psat_2023_sciusrpercentile, psat_2024_sciusrpercentile
            ) as sci_usr_percentile,
            coalesce(
                psat_2023_totalusrpercentile, psat_2024_totalusrpercentile
            ) as total_usr_percentile,
            coalesce(
                psat_2023_wordscontextusrpercentile, psat_2024_wordscontextusrpercentile
            ) as words_context_usr_percentile,
            coalesce(
                psat_2023_writinglangusrpercentile, psat_2024_writinglangusrpercentile
            ) as writing_lang_usr_percentile,

            /* null out blank strings */
            nullif(psat_2023_newdistrictid, '') as psat_2023_newdistrictid,
            nullif(psat_2023_newssid, '') as psat_2023_newssid,
            nullif(psat_2023_gradeassessed, '') as psat_2023_gradeassessed,
            nullif(psat_2023_firstchoicemajor, '') as psat_2023_firstchoicemajor,
            nullif(psat_2023_gpa, '') as psat_2023_gpa,
            nullif(psat_2023_numyearsgrade912, '') as psat_2023_numyearsgrade912,
            nullif(
                psat_2023_studentmiddleinitial, ''
            ) as psat_2023_studentmiddleinitial,
            nullif(psat_2023_aparthist, '') as psat_2023_aparthist,
            nullif(psat_2023_apbio, '') as psat_2023_apbio,
            nullif(psat_2023_apcalc, '') as psat_2023_apcalc,
            nullif(psat_2023_apchem, '') as psat_2023_apchem,
            nullif(psat_2023_apcompgovpol, '') as psat_2023_apcompgovpol,
            nullif(psat_2023_apcompsci, '') as psat_2023_apcompsci,
            nullif(psat_2023_apenglang, '') as psat_2023_apenglang,
            nullif(psat_2023_apenglit, '') as psat_2023_apenglit,
            nullif(psat_2023_apenvsci, '') as psat_2023_apenvsci,
            nullif(psat_2023_apeurohist, '') as psat_2023_apeurohist,
            nullif(psat_2023_aphumgeo, '') as psat_2023_aphumgeo,
            nullif(psat_2023_apmacecon, '') as psat_2023_apmacecon,
            nullif(psat_2023_apmicecon, '') as psat_2023_apmicecon,
            nullif(psat_2023_apmusic, '') as psat_2023_apmusic,
            nullif(psat_2023_apphysi, '') as psat_2023_apphysi,
            nullif(psat_2023_apphysii, '') as psat_2023_apphysii,
            nullif(psat_2023_apphysmag, '') as psat_2023_apphysmag,
            nullif(psat_2023_apphysmech, '') as psat_2023_apphysmech,
            nullif(psat_2023_appsych, '') as psat_2023_appsych,
            nullif(psat_2023_apseminar, '') as psat_2023_apseminar,
            nullif(psat_2023_apstat, '') as psat_2023_apstat,
            nullif(psat_2023_apusgovpol, '') as psat_2023_apusgovpol,
            nullif(psat_2023_apushist, '') as psat_2023_apushist,
            nullif(psat_2023_apworldhist, '') as psat_2023_apworldhist,
            nullif(psat_2024_newdistrictid, '') as psat_2024_newdistrictid,
            nullif(psat_2024_newssid, '') as psat_2024_newssid,
            nullif(psat_2024_gradeassessed, '') as psat_2024_gradeassessed,
            nullif(psat_2024_firstchoicemajor, '') as psat_2024_firstchoicemajor,
            nullif(psat_2024_gpa, '') as psat_2024_gpa,
            nullif(psat_2024_numyearsgrade912, '') as psat_2024_numyearsgrade912,
            nullif(
                psat_2024_studentmiddleinitial, ''
            ) as psat_2024_studentmiddleinitial,
            nullif(psat_2024_aparthist, '') as psat_2024_aparthist,
            nullif(psat_2024_apbio, '') as psat_2024_apbio,
            nullif(psat_2024_apcalc, '') as psat_2024_apcalc,
            nullif(psat_2024_apchem, '') as psat_2024_apchem,
            nullif(psat_2024_apcompgovpol, '') as psat_2024_apcompgovpol,
            nullif(psat_2024_apcompsci, '') as psat_2024_apcompsci,
            nullif(psat_2024_apenglang, '') as psat_2024_apenglang,
            nullif(psat_2024_apenglit, '') as psat_2024_apenglit,
            nullif(psat_2024_apenvsci, '') as psat_2024_apenvsci,
            nullif(psat_2024_apeurohist, '') as psat_2024_apeurohist,
            nullif(psat_2024_aphumgeo, '') as psat_2024_aphumgeo,
            nullif(psat_2024_apmacecon, '') as psat_2024_apmacecon,
            nullif(psat_2024_apmicecon, '') as psat_2024_apmicecon,
            nullif(psat_2024_apmusic, '') as psat_2024_apmusic,
            nullif(psat_2024_apphysi, '') as psat_2024_apphysi,
            nullif(psat_2024_apphysii, '') as psat_2024_apphysii,
            nullif(psat_2024_apphysmag, '') as psat_2024_apphysmag,
            nullif(psat_2024_apphysmech, '') as psat_2024_apphysmech,
            nullif(psat_2024_appsych, '') as psat_2024_appsych,
            nullif(psat_2024_apseminar, '') as psat_2024_apseminar,
            nullif(psat_2024_apstat, '') as psat_2024_apstat,
            nullif(psat_2024_apusgovpol, '') as psat_2024_apusgovpol,
            nullif(psat_2024_apushist, '') as psat_2024_apushist,
            nullif(psat_2024_apworldhist, '') as psat_2024_apworldhist,
        from union_relations
    )

select
    id,
    form_code,

    cb_student_id,
    district_student_id,
    local_student_id,
    state_student_id,

    test_date,
    report_date,
    self_assessment_date,

    student_first_name,
    student_last_name,
    cohort_year,
    birth_date,

    latest_psat_access_code,
    selection_index,

    hs_student,
    not_valid_national_merit,
    ebrw_ccr_benchmark,
    math_ccr_benchmark,

    advanced_math_rep_percentile,
    algebra_rep_percentile,
    command_rep_percentile,
    ebrw_rep_percentile,
    eng_conventions_rep_percentile,
    expression_idea_rep_percentile,
    hist_rep_percentile,
    math_rep_percentile,
    math_sect_rep_percentile,
    problem_solve_rep_percentile,
    reading_rep_percentile,
    sci_rep_percentile,
    total_rep_percentile,
    words_context_rep_percentile,
    writing_lang_rep_percentile,

    advanced_math_usr_percentile,
    algebra_usr_percentile,
    command_usr_percentile,
    ebrw_usr_percentile,
    eng_conventions_usr_percentile,
    expression_idea_usr_percentile,
    hist_usr_percentile,
    math_sect_usr_percentile,
    math_usr_percentile,
    problem_solve_usr_percentile,
    reading_usr_percentile,
    sci_usr_percentile,
    total_usr_percentile,
    words_context_usr_percentile,
    writing_lang_usr_percentile,

    safe_cast(total_score as numeric) as total_score,
    safe_cast(math_test_score as numeric) as math_test_score,
    safe_cast(history_cross_test_score as numeric) as history_cross_test_score,
    safe_cast(reading_test_score as numeric) as reading_test_score,
    safe_cast(science_cross_test_score as numeric) as science_cross_test_score,
    safe_cast(writing_test_score as numeric) as writing_test_score,
    safe_cast(eb_read_write_section_score as numeric) as eb_read_write_section_score,
    safe_cast(math_section_score as numeric) as math_section_score,
    safe_cast(advanced_math_subscore as numeric) as advanced_math_subscore,
    safe_cast(command_evidence_subscore as numeric) as command_evidence_subscore,
    safe_cast(english_conv_subscore as numeric) as english_conv_subscore,
    safe_cast(expression_ideas_subscore as numeric) as expression_ideas_subscore,
    safe_cast(heart_algebra_subscore as numeric) as heart_algebra_subscore,
    safe_cast(prob_solve_data_subscore as numeric) as prob_solve_data_subscore,
    safe_cast(relevant_words_subscore as numeric) as relevant_words_subscore,

    coalesce(psat_2023_newdistrictid, psat_2024_newdistrictid) as new_district_id,
    coalesce(psat_2023_newssid, psat_2024_newssid) as new_ssid,
    coalesce(psat_2023_gradeassessed, psat_2024_gradeassessed) as grade_assessed,
    coalesce(
        psat_2023_firstchoicemajor, psat_2024_firstchoicemajor
    ) as first_choic_emajor,
    coalesce(psat_2023_gpa, psat_2024_gpa) as gpa,
    coalesce(
        psat_2023_numyearsgrade912, psat_2024_numyearsgrade912
    ) as num_years_grade_9_12,
    coalesce(
        psat_2023_studentmiddleinitial, psat_2024_studentmiddleinitial
    ) as student_middle_initial,
    coalesce(psat_2023_aparthist, psat_2024_aparthist) as ap_art_hist,
    coalesce(psat_2023_apbio, psat_2024_apbio) as ap_bio,
    coalesce(psat_2023_apcalc, psat_2024_apcalc) as ap_calc,
    coalesce(psat_2023_apchem, psat_2024_apchem) as ap_chem,
    coalesce(psat_2023_apcompgovpol, psat_2024_apcompgovpol) as ap_comp_gov_pol,
    coalesce(psat_2023_apcompsci, psat_2024_apcompsci) as ap_comp_sci,
    coalesce(psat_2023_apenglang, psat_2024_apenglang) as ap_eng_lang,
    coalesce(psat_2023_apenglit, psat_2024_apenglit) as ap_eng_lit,
    coalesce(psat_2023_apenvsci, psat_2024_apenvsci) as ap_env_sci,
    coalesce(psat_2023_apeurohist, psat_2024_apeurohist) as ap_euro_hist,
    coalesce(psat_2023_aphumgeo, psat_2024_aphumgeo) as ap_hum_geo,
    coalesce(psat_2023_apmacecon, psat_2024_apmacecon) as ap_mac_econ,
    coalesce(psat_2023_apmicecon, psat_2024_apmicecon) as ap_mic_econ,
    coalesce(psat_2023_apmusic, psat_2024_apmusic) as ap_music,
    coalesce(psat_2023_apphysi, psat_2024_apphysi) as ap_phys_i,
    coalesce(psat_2023_apphysii, psat_2024_apphysii) as ap_phys_ii,
    coalesce(psat_2023_apphysmag, psat_2024_apphysmag) as ap_phys_mag,
    coalesce(psat_2023_apphysmech, psat_2024_apphysmech) as ap_phys_mech,
    coalesce(psat_2023_appsych, psat_2024_appsych) as ap_psych,
    coalesce(psat_2023_apseminar, psat_2024_apseminar) as ap_seminar,
    coalesce(psat_2023_apstat, psat_2024_apstat) as ap_stat,
    coalesce(psat_2023_apusgovpol, psat_2024_apusgovpol) as ap_us_gov_pol,
    coalesce(psat_2023_apushist, psat_2024_apushist) as ap_us_hist,
    coalesce(psat_2023_apworldhist, psat_2024_apworldhist) as ap_world_hist,
from combined_years
