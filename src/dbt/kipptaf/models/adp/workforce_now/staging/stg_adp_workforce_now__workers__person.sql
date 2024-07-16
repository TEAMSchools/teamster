with
    person as (
        select
            associate_oid,
            as_of_date_timestamp,

            person.birthdate as birth_date,
            person.disabledindicator as disabled_indicator,
            person.militarydischargedate as military_discharge_date,
            person.tobaccouserindicator as tobacco_user_indicator,

            person.birthname.formattedname as birth_name__formatted_name,
            person.birthname.givenname as birth_name__given_name,
            person.birthname.middlename as birth_name__middle_name,
            person.birthname.familyname1 as birth_name__family_name1,
            person.birthname.nickname as birth_name__nick_name,

            person.birthname.generationaffixcode.effectivedate
            as birth_name__generation_affix_code__effective_date,
            person.birthname.generationaffixcode.codevalue
            as birth_name__generation_affix_code__code_value,
            person.birthname.generationaffixcode.longname
            as birth_name__generation_affix_code__long_name,
            person.birthname.generationaffixcode.shortname
            as birth_name__generation_affix_code__short_name,

            person.birthname.qualificationaffixcode.effectivedate
            as birth_name__qualification_affix_code__effective_date,
            person.birthname.qualificationaffixcode.codevalue
            as birth_name__qualification_affix_code__code_value,
            person.birthname.qualificationaffixcode.longname
            as birth_name__qualification_affix_code__long_name,
            person.birthname.qualificationaffixcode.shortname
            as birth_name__qualification_affix_code__short_name,

            person.legalname.familyname1 as legal_name__family_name1,
            person.legalname.formattedname as legal_name__formatted_name,
            person.legalname.givenname as legal_name__given_name,
            person.legalname.middlename as legal_name__middle_name,
            person.legalname.nickname as legal_name__nick_name,

            person.legalname.generationaffixcode.effectivedate
            as legal_name__generation_affix_code__effective_date,
            person.legalname.generationaffixcode.codevalue
            as legal_name__generation_affix_code__code_value,
            person.legalname.generationaffixcode.longname
            as legal_name__generation_affix_code__long_name,
            person.legalname.generationaffixcode.shortname
            as legal_name__generation_affix_code__short_name,

            person.legalname.qualificationaffixcode.effectivedate
            as legal_name__qualification_affix_code__effective_date,
            person.legalname.qualificationaffixcode.codevalue
            as legal_name__qualification_affix_code__code_value,
            person.legalname.qualificationaffixcode.longname
            as legal_name__qualification_affix_code__long_name,
            person.legalname.qualificationaffixcode.shortname
            as legal_name__qualification_affix_code__short_name,

            person.preferredname.formattedname as preferred_name__formatted_name,
            person.preferredname.givenname as preferred_name__given_name,
            person.preferredname.middlename as preferred_name__middle_name,
            person.preferredname.familyname1 as preferred_name__family_name1,
            person.preferredname.nickname as preferred_name__nick_name,

            person.preferredname.generationaffixcode.effectivedate
            as preferred_name__generation_affix_code__effective_date,
            person.preferredname.generationaffixcode.codevalue
            as preferred_name__generation_affix_code__code_value,
            person.preferredname.generationaffixcode.longname
            as preferred_name__generation_affix_code__long_name,
            person.preferredname.generationaffixcode.shortname
            as preferred_name__generation_affix_code__short_name,

            person.preferredname.qualificationaffixcode.effectivedate
            as preferred_name__qualification_affix_code__effective_date,
            person.preferredname.qualificationaffixcode.codevalue
            as preferred_name__qualification_affix_code__code_value,
            person.preferredname.qualificationaffixcode.longname
            as preferred_name__qualification_affix_code__long_name,
            person.preferredname.qualificationaffixcode.shortname
            as preferred_name__qualification_affix_code__short_name,

            person.ethnicitycode.effectivedate as ethnicity_code__effective_date,
            person.ethnicitycode.codevalue as ethnicity_code__code_value,
            person.ethnicitycode.longname as ethnicity_code__long_name,
            person.ethnicitycode.shortname as ethnicity_code__short_name,

            person.gendercode.effectivedate as gender_code__effective_date,
            person.gendercode.codevalue as gender_code__code_value,
            person.gendercode.longname as gender_code__long_name,
            person.gendercode.shortname as gender_code__short_name,

            person.genderselfidentitycode.effectivedate
            as gender_self_identity_code__effective_date,
            person.genderselfidentitycode.codevalue
            as gender_self_identity_code__code_value,
            person.genderselfidentitycode.longname
            as gender_self_identity_code__long_name,
            person.genderselfidentitycode.shortname
            as gender_self_identity_code__short_name,

            person.highesteducationlevelcode.effectivedate
            as highest_education_level_code__effective_date,
            person.highesteducationlevelcode.codevalue
            as highest_education_level_code__code_value,
            person.highesteducationlevelcode.longname
            as highest_education_level_code__long_name,
            person.highesteducationlevelcode.shortname
            as highest_education_level_code__short_name,

            person.legaladdress.itemid as legal_address__item_id,
            person.legaladdress.lineone as legal_address__line_one,
            person.legaladdress.linetwo as legal_address__line_two,
            person.legaladdress.linethree as legal_address__line_three,
            person.legaladdress.cityname as legal_address__city_name,
            person.legaladdress.postalcode as legal_address__postal_code,
            person.legaladdress.countrycode as legal_address__country_code,

            person.legaladdress.countrysubdivisionlevel1.effectivedate
            as legal_address__country_subdivision_level1__effective_date,
            person.legaladdress.countrysubdivisionlevel1.subdivisiontype
            as legal_address__country_subdivision_level1__subdivision_type,
            person.legaladdress.countrysubdivisionlevel1.codevalue
            as legal_address__country_subdivision_level1__code_value,
            person.legaladdress.countrysubdivisionlevel1.longname
            as legal_address__country_subdivision_level1__long_name,
            person.legaladdress.countrysubdivisionlevel1.shortname
            as legal_address__country_subdivision_level1__short_name,

            person.legaladdress.countrysubdivisionlevel2.effectivedate
            as legal_address__country_subdivision_level2__effective_date,
            person.legaladdress.countrysubdivisionlevel2.subdivisiontype
            as legal_address__country_subdivision_level2__subdivision_type,
            person.legaladdress.countrysubdivisionlevel2.codevalue
            as legal_address__country_subdivision_level2__code_value,
            person.legaladdress.countrysubdivisionlevel2.longname
            as legal_address__country_subdivision_level2__long_name,
            person.legaladdress.countrysubdivisionlevel2.shortname
            as legal_address__country_subdivision_level2__short_name,

            person.legaladdress.namecode.effectivedate
            as legal_address__name_code__effective_date,
            person.legaladdress.namecode.codevalue
            as legal_address__name_code__code_value,
            person.legaladdress.namecode.longname
            as legal_address__name_code__long_name,
            person.legaladdress.namecode.shortname
            as legal_address__name_code__short_name,

            person.legaladdress.typecode.effectivedate
            as legal_address__type_code__effective_date,
            person.legaladdress.typecode.codevalue
            as legal_address__type_code__code_value,
            person.legaladdress.typecode.longname
            as legal_address__type_code__long_name,
            person.legaladdress.typecode.shortname
            as legal_address__type_code__short_name,

            person.maritalstatuscode.effectivedate
            as marital_status_code__effective_date,
            person.maritalstatuscode.codevalue as marital_status_code__code_value,
            person.maritalstatuscode.longname as marital_status_code__long_name,
            person.maritalstatuscode.shortname as marital_status_code__short_name,

            person.militarystatuscode.effectivedate
            as military_status_code__effective_date,
            person.militarystatuscode.codevalue as military_status_code__code_value,
            person.militarystatuscode.longname as military_status_code__long_name,
            person.militarystatuscode.shortname as military_status_code__short_name,

            person.preferredgenderpronouncode.effectivedate
            as preferred_gender_pronoun_code__effective_date,
            person.preferredgenderpronouncode.codevalue
            as preferred_gender_pronoun_code__code_value,
            person.preferredgenderpronouncode.longname
            as preferred_gender_pronoun_code__long_name,
            person.preferredgenderpronouncode.shortname
            as preferred_gender_pronoun_code__short_name,

            person.racecode.effectivedate as race_code__effective_date,
            person.racecode.codevalue as race_code__code_value,
            person.racecode.longname as race_code__long_name,
            person.racecode.shortname as race_code__short_name,

            person.racecode.identificationmethodcode.effectivedate
            as race_code__identification_method_code__effective_date,
            person.racecode.identificationmethodcode.codevalue
            as race_code__identification_method_code__code_value,
            person.racecode.identificationmethodcode.longname
            as race_code__identification_method_code__long_name,
            person.racecode.identificationmethodcode.shortname
            as race_code__identification_method_code__short_name,

            /* repeated records */
            person.disabilitytypecodes as disability_type_codes,
            person.governmentids as government_i_ds,
            person.militaryclassificationcodes as military_classification_codes,
            person.otherpersonaladdresses as other_personal_addresses,
            person.socialinsuranceprograms as social_insurance_programs,
            person.birthname.preferredsalutations as birth_name__preferred_salutations,
            person.communication.emails as communication__emails,
            person.communication.landlines as communication__landlines,
            person.communication.mobiles as communication__mobiles,
            person.customfieldgroup.codefields as custom_field_group__code_fields,
            person.customfieldgroup.datefields as custom_field_group__date_fields,
            person.customfieldgroup.indicatorfields
            as custom_field_group__indicator_fields,
            person.customfieldgroup.multicodefields
            as custom_field_group__multi_code_fields,
            person.customfieldgroup.numberfields as custom_field_group__number_fields,
            person.customfieldgroup.stringfields as custom_field_group__string_fields,
            person.legalname.preferredsalutations as legal_name__preferred_salutations,
            person.preferredname.preferredsalutations
            as preferred_name__preferred_salutations,

            {{ dbt_utils.generate_surrogate_key(["to_json_string(person)"]) }}
            as surrogate_key,
        from {{ ref("stg_adp_workforce_now__workers") }}
    )

    {{
        dbt_utils.deduplicate(
            relation="person",
            partition_by="associate_oid, surrogate_key",
            order_by="as_of_date_timestamp asc",
        )
    }}
