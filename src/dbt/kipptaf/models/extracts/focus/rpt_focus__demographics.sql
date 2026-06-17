with
    demographics as (
        select
            c.last_name,
            c.first_name,
            c.middle_name,
            c.preferred_name,
            c.email,
            c.gender,
            c.birth_date,
            cca.latino_hispanic_yn,
        from {{ ref("stg_finalsite__contacts") }} as c
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on c.finalsite_enrollment_id = l.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_custom_attributes") }} as cca
            on c.finalsite_enrollment_id = cca.finalsite_enrollment_id
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus DEMOGRAPHICS contract
select
    -- STDT_ID is null until the Finalsite-minted student id lands in
    -- id_attributes; repoint to int_finalsite__contact_id_attributes then.
    cast(null as string) as stdt_id,
    d.last_name,
    d.first_name,
    cast(null as string) as name_suffix,
    d.middle_name,
    d.preferred_name as nickname,
    format_date('%Y%m%d', d.birth_date) as dt_birth,
    case
        when d.gender in ('M', 'Male')
        then 'M'
        when d.gender in ('F', 'Female')
        then 'F'
    end as gender,
    cast(null as string) as lang,
    d.email as stdt_email,
    if(d.latino_hispanic_yn, 'Y', 'N') as ethnic_hl,
    cast(null as string) as single_ethnic,
    cast(null as string) as race_am_ind_ak_nat,
    cast(null as string) as race_asian,
    cast(null as string) as race_black,
    cast(null as string) as race_nat_haw_pac_isl,
    cast(null as string) as race_white,
    cast(null as string) as residence_county,
    cast(null as string) as contry_birth,
    cast(null as string) as homeroom_tchr,
    cast(null as string) as resident_st,
    cast(null as string) as birth_loc,
    cast(null as string) as bdate_verif,
    cast(null as string) as immun_st,
    cast(null as string) as primary_home_lang,
    cast(null as string) as native_parent_lang,
    cast(null as string) as grde_enter_dist,
    cast(null as string) as msix_id,
    cast(null as string) as homeroom,
    cast(null as string) as pmrn,
    cast(null as string) as internt_perm,
    cast(null as string) as act_perm,
    cast(null as string) as direct_perm,
    cast(null as string) as screen_perm,
    cast(null as string) as photo_vid_perm,
    cast(null as string) as survey_perm,
    cast(null as string) as mckay_sch_attend,
    cast(null as string) as fhsaa_el3_ind,
    cast(null as string) as fhsaa_el3ch_ind,
    cast(null as string) as dt_home_lang_survey,
    cast(null as string) as casas_track,
    cast(null as string) as lcp_cont_stdt,
    cast(null as string) as tide_access_code,
from demographics as d
