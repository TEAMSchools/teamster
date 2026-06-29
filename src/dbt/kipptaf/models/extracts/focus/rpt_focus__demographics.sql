-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus DEMOGRAPHICS contract
select
    concat('8400', ida.focus_student_id) as stdt_id,

    c.last_name,
    c.first_name,

    cast(null as string) as name_suffix,

    c.middle_name,
    c.preferred_name as nickname,

    format_date('%Y%m%d', c.birth_date) as dt_birth,

    case
        when c.gender in ('M', 'Male')
        then 'M'
        when c.gender in ('F', 'Female')
        then 'F'
    end as gender,

    -- LANG, PRIMARY_HOME_LANG, and NATIVE_PARENT_LANG all draw the same Focus
    -- value code from the language crosswalk. NOTE: the Focus LANG field
    -- (custom_200000005) historically carried a legacy 3-option set
    -- (EN/English/Spanish); pending registrar confirmation it is assumed to
    -- accept the same FLDOE code as the home/native-language fields.
    lcc.focus_language_code as lang,

    c.email as stdt_email,

    -- null (not 'N') when no custom_attributes row exists, so an unknown is not
    -- silently reported as not-Hispanic for FLDOE.
    case
        when cca.latino_hispanic_yn then 'Y' when not cca.latino_hispanic_yn then 'N'
    end as ethnic_hl,

    cast(null as string) as single_ethnic,

    if('American Indian' in unnest(cca.race_ms), 'Y', null) as race_am_ind_ak_nat,
    if('Asian' in unnest(cca.race_ms), 'Y', null) as race_asian,
    if('Black' in unnest(cca.race_ms), 'Y', null) as race_black,
    if(
        'Native Pacific Islander' in unnest(cca.race_ms), 'Y', null
    ) as race_nat_haw_pac_isl,
    if('White' in unnest(cca.race_ms), 'Y', null) as race_white,

    cast(null as string) as residence_county,
    cast(null as string) as contry_birth,
    cast(null as string) as homeroom_tchr,
    cast(null as string) as resident_st,
    cast(null as string) as birth_loc,
    cast(null as string) as bdate_verif,
    cast(null as string) as immun_st,

    lcc.focus_language_code as primary_home_lang,
    lcc.focus_language_code as native_parent_lang,

    cast(null as string) as grde_enter_dist,
    cast(null as string) as msix_id,
    cast(null as string) as homeroom,
    cast(null as string) as pmrn,
    cast(null as string) as internt_perm,
    cast(null as string) as act_perm,
    cast(null as string) as direct_perm,
    cast(null as string) as screen_perm,

    if(cca.media_release_yn, 'Y', 'N') as photo_vid_perm,

    cast(null as string) as survey_perm,
    cast(null as string) as mckay_sch_attend,
    cast(null as string) as fhsaa_el3_ind,
    cast(null as string) as fhsaa_el3ch_ind,
    cast(null as string) as dt_home_lang_survey,
    cast(null as string) as casas_track,
    cast(null as string) as lcp_cont_stdt,
from {{ ref("stg_finalsite__contacts") }} as c
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
left join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
left join
    {{ ref("int_finalsite__contact_custom_attributes") }} as cca
    on c.finalsite_enrollment_id = cca.finalsite_enrollment_id
left join
    {{ ref("stg_google_sheets__focus__language_code_crosswalk") }} as lcc
    on cca.lang_parent_ss = lcc.finalsite_language
