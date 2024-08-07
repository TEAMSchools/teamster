with
    -- trunk-ignore(sqlfluff/ST03)
    workers as (
        select
            associateoid as associate_oid,
            _dagster_partition_date as effective_date_start,

            workerid as worker_id,
            workerdates as worker_dates,
            workerstatus as worker_status,
            _languagecode as language_code,
            person,
            photos,
            workassignments as work_assignments,
            businesscommunication as business_communication,
            customfieldgroup as custom_field_group,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "to_json_string(workerid)",
                        "to_json_string(workerdates)",
                        "to_json_string(workerstatus)",
                        "to_json_string(_languagecode)",
                        "to_json_string(person)",
                        "to_json_string(customfieldgroup)",
                        "to_json_string(workassignments)",
                        "to_json_string(businesscommunication)",
                        "to_json_string(photos)",
                    ]
                )
            }} as surrogate_key,
        from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="workers",
                partition_by="associate_oid, surrogate_key",
                order_by="effective_date_start asc",
            )
        }}
    ),

    flattened as (
        select
            associate_oid,
            effective_date_start,

            worker_id.idvalue as worker_id__id_value,

            worker_id.schemecode.codevalue as worker_id__scheme_code__code_value,
            worker_id.schemecode.longname as worker_id__scheme_code__long_name,
            worker_id.schemecode.shortname as worker_id__scheme_code__short_name,

            worker_status.statuscode.codevalue
            as worker_status__status_code__code_value,
            worker_status.statuscode.longname as worker_status__status_code__long_name,
            worker_status.statuscode.shortname
            as worker_status__status_code__short_name,

            language_code.codevalue as language_code__code_value,
            language_code.longname as language_code__long_name,
            language_code.shortname as language_code__short_name,

            person.disabledindicator as person__disabled_indicator,
            person.militarydischargedate as person__military_discharge_date,
            person.tobaccouserindicator as person__tobacco_user_indicator,

            person.birthname.formattedname as person__birth_name__formatted_name,
            person.birthname.givenname as person__birth_name__given_name,
            person.birthname.middlename as person__birth_name__middle_name,
            person.birthname.familyname1 as person__birth_name__family_name_1,
            person.birthname.nickname as person__birth_name__nick_name,

            person.birthname.generationaffixcode.codevalue
            as person__birth_name__generation_affix_code__code_value,
            person.birthname.generationaffixcode.longname
            as person__birth_name__generation_affix_code__long_name,
            person.birthname.generationaffixcode.shortname
            as person__birth_name__generation_affix_code__short_name,

            person.birthname.qualificationaffixcode.codevalue
            as person__birth_name__qualification_affix_code__code_value,
            person.birthname.qualificationaffixcode.longname
            as person__birth_name__qualification_affix_code__long_name,
            person.birthname.qualificationaffixcode.shortname
            as person__birth_name__qualification_affix_code__short_name,

            person.legalname.familyname1 as person__legal_name__family_name_1,
            person.legalname.formattedname as person__legal_name__formatted_name,
            person.legalname.givenname as person__legal_name__given_name,
            person.legalname.middlename as person__legal_name__middle_name,
            person.legalname.nickname as person__legal_name__nick_name,

            person.legalname.generationaffixcode.codevalue
            as person__legal_name__generation_affix_code__code_value,
            person.legalname.generationaffixcode.longname
            as person__legal_name__generation_affix_code__long_name,
            person.legalname.generationaffixcode.shortname
            as person__legal_name__generation_affix_code__short_name,

            person.legalname.qualificationaffixcode.codevalue
            as person__legal_name__qualification_affix_code__code_value,
            person.legalname.qualificationaffixcode.longname
            as person__legal_name__qualification_affix_code__long_name,
            person.legalname.qualificationaffixcode.shortname
            as person__legal_name__qualification_affix_code__short_name,

            person.preferredname.formattedname
            as person__preferred_name__formatted_name,
            person.preferredname.givenname as person__preferred_name__given_name,
            person.preferredname.middlename as person__preferred_name__middle_name,
            person.preferredname.familyname1 as person__preferred_name__family_name_1,
            person.preferredname.nickname as person__preferred_name__nick_name,

            person.preferredname.generationaffixcode.codevalue
            as person__preferred_name__generation_affix_code__code_value,
            person.preferredname.generationaffixcode.longname
            as person__preferred_name__generation_affix_code__long_name,
            person.preferredname.generationaffixcode.shortname
            as person__preferred_name__generation_affix_code__short_name,

            person.preferredname.qualificationaffixcode.codevalue
            as person__preferred_name__qualification_affix_code__code_value,
            person.preferredname.qualificationaffixcode.longname
            as person__preferred_name__qualification_affix_code__long_name,
            person.preferredname.qualificationaffixcode.shortname
            as person__preferred_name__qualification_affix_code__short_name,

            person.ethnicitycode.codevalue as person__ethnicity_code__code_value,
            person.ethnicitycode.longname as person__ethnicity_code__long_name,
            person.ethnicitycode.shortname as person__ethnicity_code__short_name,

            person.gendercode.codevalue as person__gender_code__code_value,
            person.gendercode.longname as person__gender_code__long_name,
            person.gendercode.shortname as person__gender_code__short_name,

            person.genderselfidentitycode.codevalue
            as person__gender_self_identity_code__code_value,
            person.genderselfidentitycode.longname
            as person__gender_self_identity_code__long_name,
            person.genderselfidentitycode.shortname
            as person__gender_self_identity_code__short_name,

            person.highesteducationlevelcode.codevalue
            as person__highest_education_level_code__code_value,
            person.highesteducationlevelcode.longname
            as person__highest_education_level_code__long_name,
            person.highesteducationlevelcode.shortname
            as person__highest_education_level_code__short_name,

            person.legaladdress.itemid as person__legal_address__item_id,
            person.legaladdress.lineone as person__legal_address__line_one,
            person.legaladdress.linetwo as person__legal_address__line_two,
            person.legaladdress.linethree as person__legal_address__line_three,
            person.legaladdress.cityname as person__legal_address__city_name,
            person.legaladdress.postalcode as person__legal_address__postal_code,
            person.legaladdress.countrycode as person__legal_address__country_code,

            person.legaladdress.countrysubdivisionlevel1.subdivisiontype
            as person__legal_address__country_subdivision_level_1__subdivision_type,
            person.legaladdress.countrysubdivisionlevel1.codevalue
            as person__legal_address__country_subdivision_level_1__code_value,
            person.legaladdress.countrysubdivisionlevel1.longname
            as person__legal_address__country_subdivision_level_1__long_name,
            person.legaladdress.countrysubdivisionlevel1.shortname
            as person__legal_address__country_subdivision_level_1__short_name,

            person.legaladdress.countrysubdivisionlevel2.subdivisiontype
            as person__legal_address__country_subdivision_level_2__subdivision_type,
            person.legaladdress.countrysubdivisionlevel2.codevalue
            as person__legal_address__country_subdivision_level_2__code_value,
            person.legaladdress.countrysubdivisionlevel2.longname
            as person__legal_address__country_subdivision_level_2__long_name,
            person.legaladdress.countrysubdivisionlevel2.shortname
            as person__legal_address__country_subdivision_level_2__short_name,

            person.legaladdress.namecode.codevalue
            as person__legal_address__name_code__code_value,
            person.legaladdress.namecode.longname
            as person__legal_address__name_code__long_name,
            person.legaladdress.namecode.shortname
            as person__legal_address__name_code__short_name,

            person.legaladdress.typecode.codevalue
            as person__legal_address__type_code__code_value,
            person.legaladdress.typecode.longname
            as person__legal_address__type_code__long_name,
            person.legaladdress.typecode.shortname
            as person__legal_address__type_code__short_name,

            person.maritalstatuscode.codevalue
            as person__marital_status_code__code_value,
            person.maritalstatuscode.longname as person__marital_status_code__long_name,
            person.maritalstatuscode.shortname
            as person__marital_status_code__short_name,

            person.militarystatuscode.codevalue
            as person__military_status_code__code_value,
            person.militarystatuscode.longname
            as person__military_status_code__long_name,
            person.militarystatuscode.shortname
            as person__military_status_code__short_name,

            person.preferredgenderpronouncode.codevalue
            as person__preferred_gender_pronoun_code__code_value,
            person.preferredgenderpronouncode.longname
            as person__preferred_gender_pronoun_code__long_name,
            person.preferredgenderpronouncode.shortname
            as person__preferred_gender_pronoun_code__short_name,

            person.racecode.codevalue as person__race_code__code_value,
            person.racecode.longname as person__race_code__long_name,
            person.racecode.shortname as person__race_code__short_name,

            person.racecode.identificationmethodcode.codevalue
            as person__race_code__identification_method_code__code_value,
            person.racecode.identificationmethodcode.longname
            as person__race_code__identification_method_code__long_name,
            person.racecode.identificationmethodcode.shortname
            as person__race_code__identification_method_code__short_name,

            /* repeated records */
            photos,
            work_assignments,

            business_communication.emails as business_communication__emails,
            business_communication.landlines as business_communication__landlines,
            business_communication.mobiles as business_communication__mobiles,

            custom_field_group.codefields as custom_field_group__code_fields,
            custom_field_group.datefields as custom_field_group__date_fields,
            custom_field_group.indicatorfields as custom_field_group__indicator_fields,
            custom_field_group.multicodefields as custom_field_group__multi_code_fields,
            custom_field_group.numberfields as custom_field_group__number_fields,
            custom_field_group.stringfields as custom_field_group__string_fields,

            person.disabilitytypecodes as person__disability_type_codes,
            person.militaryclassificationcodes as person__military_classification_codes,
            person.otherpersonaladdresses as person__other_personal_addresses,
            person.socialinsuranceprograms as person__social_insurance_programs,
            person.birthname.preferredsalutations
            as person__birth_name__preferred_salutations,
            person.communication.emails as person__communication__emails,
            person.communication.landlines as person__communication__landlines,
            person.communication.mobiles as person__communication__mobiles,
            person.customfieldgroup.codefields
            as person__custom_field_group__code_fields,
            person.customfieldgroup.datefields
            as person__custom_field_group__date_fields,
            person.customfieldgroup.indicatorfields
            as person__custom_field_group__indicator_fields,
            person.customfieldgroup.multicodefields
            as person__custom_field_group__multi_code_fields,
            person.customfieldgroup.numberfields
            as person__custom_field_group__number_fields,
            person.customfieldgroup.stringfields
            as person__custom_field_group__string_fields,
            person.legalname.preferredsalutations
            as person__legal_name__preferred_salutations,
            person.preferredname.preferredsalutations
            as person__preferred_name__preferred_salutations,

            /* transformations */
            date(worker_dates.originalhiredate) as worker_dates__original_hire_date,
            date(worker_dates.rehiredate) as worker_dates__rehire_date,
            date(worker_dates.terminationdate) as worker_dates__termination_date,

            date(
                worker_id.schemecode.effectivedate
            ) as worker_id__scheme_code__effective_date,

            date(
                worker_status.statuscode.effectivedate
            ) as worker_status__status_code__effective_date,

            date(language_code.effectivedate) as language_code__effective_date,

            date(
                person.birthname.generationaffixcode.effectivedate
            ) as person__birth_name__generation_affix_code__effective_date,
            date(
                person.birthname.qualificationaffixcode.effectivedate
            ) as person__birth_name__qualification_affix_code__effective_date,

            date(
                person.legalname.generationaffixcode.effectivedate
            ) as person__legal_name__generation_affix_code__effective_date,
            date(
                person.legalname.qualificationaffixcode.effectivedate
            ) as person__legal_name__qualification_affix_code__effective_date,

            date(
                person.preferredname.generationaffixcode.effectivedate
            ) as person__preferred_name__generation_affix_code__effective_date,
            date(
                person.preferredname.qualificationaffixcode.effectivedate
            ) as person__preferred_name__qualification_affix_code__effective_date,

            date(
                person.ethnicitycode.effectivedate
            ) as person__ethnicity_code__effective_date,

            date(
                person.gendercode.effectivedate
            ) as person__gender_code__effective_date,

            date(
                person.genderselfidentitycode.effectivedate
            ) as person__gender_self_identity_code__effective_date,

            date(
                person.highesteducationlevelcode.effectivedate
            ) as person__highest_education_level_code__effective_date,

            date(
                person.legaladdress.countrysubdivisionlevel1.effectivedate
            ) as person__legal_address__country_subdivision_level_1__effective_date,
            date(
                person.legaladdress.countrysubdivisionlevel2.effectivedate
            ) as person__legal_address__country_subdivision_level_2__effective_date,
            date(
                person.legaladdress.namecode.effectivedate
            ) as person__legal_address__name_code__effective_date,
            date(
                person.legaladdress.typecode.effectivedate
            ) as person__legal_address__type_code__effective_date,

            date(
                person.maritalstatuscode.effectivedate
            ) as person__marital_status_code__effective_date,

            date(
                person.militarystatuscode.effectivedate
            ) as person__military_status_code__effective_date,

            date(
                person.preferredgenderpronouncode.effectivedate
            ) as person__preferred_gender_pronoun_code__effective_date,

            date(person.racecode.effectivedate) as person__race_code__effective_date,
            date(
                person.racecode.identificationmethodcode.effectivedate
            ) as person__race_code__identification_method_code__effective_date,

            /* year can be masked as 0000 */
            safe_cast(person.birthdate as date) as person__birth_date,

            timestamp_sub(
                timestamp_add(timestamp(effective_date_start), interval 1 day),
                interval 1 millisecond
            ) as effective_date_timestamp,

            lag(effective_date_start, 1) over (
                partition by associate_oid order by effective_date_start asc
            ) as effective_date_start_lag,

            coalesce(
                date_sub(
                    lead(effective_date_start, 1) over (
                        partition by associate_oid order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                '9999-12-31'
            ) as effective_date_end,
        from deduplicate
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date_start and effective_date_end,
        true,
        false
    ) as is_current_record,
from flattened
