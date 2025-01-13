with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("illuminate", "psat89_2025"),
                ],
                where="not _fivetran_deleted",
            )
        }}
    )

select *
from
    union_relations
    /*
    combined_years as (
        select
            student_id,

            psat89_2025_id as id,
            psat89_2025_formcode as form_code,
            psat89_2025_cbstudentid as cb_student_id,
            psat89_2025_districtstudentid as district_student_id,
            psat89_2025_localstudentid as local_student_id,
            psat89_2025_statestudentid as state_student_id,
            psat89_2025_statestudentid as test_date,
            psat89_2025_reportdate as report_date,
            psat89_2025_selfassessmentdate as self_assessment_date,
            psat89_2025_studentfirstname as student_first_name,
            psat89_2025_studentlastname as student_last_name,
            psat89_2025_cohortyear as cohort_year,
            psat89_2025_birthdate as birth_date,
            psat89_2025_latestpsataccesscode as latest_psat_access_code,
            psat89_2025_sectionindex as selection_index,
            psat89_2025_hsstudent as hs_student,
            psat89_2025_ebrwccrbenchmark as ebrw_ccr_benchmark,
            psat89_2025_mathccrbenchmark as math_ccr_benchmark,
            psat89_2025_totalscore as total_score,
            psat89_2025_historycrosstestscore as history_cross_test_score,
            psat89_2025_mathtestscore as math_test_score,
            psat89_2025_readingtestscore as reading_test_score,
            psat89_2025_sciencecrosstestscore as science_cross_test_score,
            psat89_2025_writingtestscore as writing_test_score,
            psat89_2025_ebreadwritesectionscoreas eb_read_write_section_score,
            psat89_2025_mathsectionscore as math_section_score,
            psat89_2025_mathtestscore as advanced_math_subscore,
            psat89_2025_commandevidencesubscore as command_evidence_subscore,
            psat89_2025_englishconvsubscore as english_conv_subscore,
            psat89_2025_expressionideassubscore as expression_ideas_subscore,
            psat89_2025_heartalgebrasubscore as heart_algebra_subscore,
            psat89_2025_probsolvedatasubscore as prob_solve_data_subscore,
            psat89_2025_relevantwordssubscore as relevant_words_subscore,
            psat89_2025_algebrareppercentile as algebra_rep_percentile,
            psat89_2025_commandreppercentile as command_rep_percentile,
            psat89_2025_ebrwreppercentile as ebrw_rep_percentile,
            psat89_2025_engconventionsreppercentile as eng_conventions_rep_percentile,
            psat89_2025_expressionideareppercentile as expression_idea_rep_percentile,
            psat89_2025_histreppercentile as hist_rep_percentile,
            psat89_2025_mathreppercentile as math_rep_percentile,
            psat89_2025_mathsectreppercentile as math_sect_rep_percentile,
            psat89_2025_problemsolvereppercentile as problem_solve_rep_percentile,
            psat89_2025_readingreppercentile as reading_rep_percentile,
            psat89_2025_scireppercentile as sci_rep_percentile,
            psat89_2025_totalreppercentile as total_rep_percentile,
            psat89_2025_wordscontextreppercentile as words_context_rep_percentile,
            psat89_2025_writinglangreppercentile as writing_lang_rep_percentile,
            psat89_2025_ksmathadvancedscore as advanced_math_usr_percentile,
            psat89_2025_algebrausrpercentile as algebra_usr_percentile,
            psat89_2025_commandusrpercentile as command_usr_percentile,
            psat89_2025_ebrwusrpercentile as ebrw_usr_percentile,
            psat89_2025_engconventionsusrpercentile as eng_conventions_usr_percentile,
            psat89_2025_expressionideausrpercentile as expression_idea_usr_percentile,
            psat89_2025_histusrpercentile as hist_usr_percentile,
            psat89_2025_mathsectusrpercentile as math_sect_usr_percentile,
            psat89_2025_mathusrpercentile as math_usr_percentile,
            psat89_2025_problemsolveusrpercentile as problem_solve_usr_percentile,
            psat89_2025_readingusrpercentile as reading_usr_percentile,
            psat89_2025_sciusrpercentile as sci_usr_percentile,
            psat89_2025_totalusrpercentile as total_usr_percentile,
            psat89_2025_wordscontextusrpercentile as words_context_usr_percentile,
            psat89_2025_writinglangusrpercentile as writing_lang_usr_percentile,
            psat89_2025_newdistrictid as psat_2023_newdistrictid,
            psat89_2025_newssid as psat_2023_newssid,
            psat89_2025_gradeassessed as psat_2023_gradeassessed,
            psat89_2025_gpa as psat_2023_gpa,
            psat89_2025_studentmiddleinitial as psat_2023_studentmiddleinitial,
            psat89_2025_aparthist as psat_2023_aparthist,
            psat89_2025_apeurohist as psat_2023_apeurohist,
            psat89_2025_aphumgeo as psat_2024_aphumgeo,
            psat89_2025_apphysii as psat_2024_apphysii,
            psat89_2025_apseminar as psat_2024_apseminar,
            psat89_2025_apworldhist as psat_2024_apworldhist,
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
    ) as first_choice_major,
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

    {{
        date_to_fiscal_year(
            date_field="test_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from combined_years

*/
    
