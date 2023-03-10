{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentsdcid",
        transform_cols=[
            {
                "name": "studentsdcid",
                "extract": "int_value",
            },
            {
                "name": "lep_completion_date_refused",
                "extract": "int_value",
            },
            {
                "name": "military_connected_indicator",
                "extract": "int_value",
            },
            {
                "name": "asmt_exclude_ela",
                "extract": "int_value",
            },
            {
                "name": "asmt_exclude_math",
                "extract": "int_value",
            },
            {
                "name": "iep_exemptpassinglal_tf",
                "extract": "int_value",
            },
            {
                "name": "iep_exemptpassingmath_tf",
                "extract": "int_value",
            },
            {
                "name": "iep_exempttakinglal_tf",
                "extract": "int_value",
            },
            {
                "name": "iep_exempttakingmath_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_title1langartslit_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_title1math_tf",
                "extract": "int_value",
            },
            {
                "name": "ctecollegecredits",
                "extract": "int_value",
            },
            {"name": "pid_504_tf", "extract": "int_value"},
            {
                "name": "pid_accommodations_a_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_accommodations_b_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_accommodations_c_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_accommodations_d_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_apascience_tf",
                "extract": "int_value",
            },
            {
                "name": "adulths_nb_credits",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "pid_lepexemptlal_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_apalangartsliteracy_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_apamath_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_madetape_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_outofdistplacement_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_outresidenceplacement_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_shortsegmenttestadmin_tf",
                "extract": "int_value",
            },
            {
                "name": "pid_title1science_tf",
                "extract": "int_value",
            },
            {
                "name": "title1_status_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_aide_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_assist_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_extyear_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_ind_instr_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_indnursing_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_intensive_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_interpreter_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_pupil_tf",
                "extract": "int_value",
            },
            {
                "name": "tiv_serv_resplacement_tf",
                "extract": "int_value",
            },
            {"name": "lep_tf", "extract": "int_value"},
            {"name": "retained_tf", "extract": "int_value"},
            {
                "name": "cumdaysinmembershipaddto_tf",
                "extract": "int_value",
            },
            {
                "name": "cumdayspresentaddto_tf",
                "extract": "int_value",
            },
            {
                "name": "cumdaystowardtruancyaddto_tf",
                "extract": "int_value",
            },
            {
                "name": "cumulativedaysinmembership",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "cumulativedayspresent",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "cumulativedaystowardtruancy",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "homelessprimarynighttimeres",
                "extract": "int_value",
            },
            {"name": "migrant_tf", "extract": "int_value"},
            {
                "name": "includeinctereport_tf",
                "extract": "int_value",
            },
            {
                "name": "includeinnjsmart_tf",
                "extract": "int_value",
            },
            {
                "name": "includeinstucourse_tf",
                "extract": "int_value",
            },
            {
                "name": "eoc_title1biology_tf",
                "extract": "int_value",
            },
            {
                "name": "iep_exemptpassingbiology_tf",
                "extract": "int_value",
            },
            {
                "name": "iep_exempttakingbiology_tf",
                "extract": "int_value",
            },
            {
                "name": "sla_alt_rep_paper",
                "extract": "int_value",
            },
            {
                "name": "sla_alternate_location",
                "extract": "int_value",
            },
            {
                "name": "sla_answer_masking",
                "extract": "int_value",
            },
            {
                "name": "sla_answers_recorded_paper",
                "extract": "int_value",
            },
            {
                "name": "sla_asl_video",
                "extract": "int_value",
            },
            {
                "name": "sla_closed_caption",
                "extract": "int_value",
            },
            {
                "name": "sla_dictionary",
                "extract": "int_value",
            },
            {
                "name": "sla_directions_clarified",
                "extract": "int_value",
            },
            {
                "name": "sla_exclude_tf",
                "extract": "int_value",
            },
            {
                "name": "sla_frequent_breaks",
                "extract": "int_value",
            },
            {
                "name": "sla_human_signer",
                "extract": "int_value",
            },
            {
                "name": "sla_large_print_paper",
                "extract": "int_value",
            },
            {
                "name": "sla_monitor_response",
                "extract": "int_value",
            },
            {
                "name": "sla_non_screen_reader",
                "extract": "int_value",
            },
            {
                "name": "sla_read_aloud",
                "extract": "int_value",
            },
            {
                "name": "sla_refresh_braille",
                "extract": "int_value",
            },
            {
                "name": "sla_screen_reader",
                "extract": "int_value",
            },
            {
                "name": "sla_small_group",
                "extract": "int_value",
            },
            {
                "name": "sla_special_equip",
                "extract": "int_value",
            },
            {
                "name": "sla_specified_area",
                "extract": "int_value",
            },
            {
                "name": "sla_time_of_day",
                "extract": "int_value",
            },
            {
                "name": "sla_unique_accommodation",
                "extract": "int_value",
            },
            {
                "name": "sla_word_prediction",
                "extract": "int_value",
            },
            {
                "name": "includeinassareport_tf",
                "extract": "int_value",
            },
            {
                "name": "caresactfunds",
                "extract": "int_value",
            },
            {"name": "deviceowner", "extract": "int_value"},
            {"name": "devicetype", "extract": "int_value"},
            {
                "name": "internetconnectivity",
                "extract": "int_value",
            },
            {
                "name": "learningenvironment",
                "extract": "int_value",
            },
            {
                "name": "remotedaysmembership",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "remotedayspresent",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "remotepercentageofday",
                "extract": "int_value",
            },
            {
                "name": "cumulativedaysabsent",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "cumulativestateabs",
                "extract": "int_value",
            },
            {"name": "daysopen", "extract": "int_value"},
            {
                "name": "remotedaysabsent",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "languageacquisition",
                "extract": "int_value",
            },
            {
                "name": "collegecreditsearned",
                "extract": "int_value",
            },
            {
                "name": "cteworkbasedlearning",
                "extract": "int_value",
            },
            {
                "name": "sid_excludeenrollment",
                "extract": "int_value",
            },
        ],
    )
}}
