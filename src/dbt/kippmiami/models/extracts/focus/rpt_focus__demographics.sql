with
    desired as (
        select *, from {{ source("kipptaf_extracts", "rpt_focus__demographics") }}
    ),

    focus_state as (
        select
            s.student_id,
            s.first_name,
            s.last_name,
            s.middle_name,
            s.student_e_mail_address,
            p.language_label,
            format_date('%Y%m%d', date(s.birthdate)) as dt_birth_focus,
            regexp_extract(p.sex_label, r'\[(.+)\]') as gender_focus,
            case
                p.ethnicity_hispanic_or_latino_label
                when 'Yes'
                then 'Y'
                when 'No'
                then 'N'
            end as ethnic_hl_focus,
            case
                p.race_american_indian_or_alaska_native_label when 'Yes' then 'Y'
            end as race_am_ind_ak_nat_focus,
            case p.race_asian_label when 'Yes' then 'Y' end as race_asian_focus,
            case
                p.race_black_or_african_american_label when 'Yes' then 'Y'
            end as race_black_focus,
            case
                p.race_native_hawaiian_or_other_pacific_islander_label
                when 'Yes'
                then 'Y'
            end as race_nat_haw_pac_isl_focus,
            case p.race_white_label when 'Yes' then 'Y' end as race_white_focus,
        from {{ ref("stg_focus__students") }} as s
        left join
            {{ ref("int_focus__students__pivot") }} as p on s.student_id = p.student_id
    ),

    diffed as (
        select d.*,
        from desired as d
        left join focus_state as f on cast(d.stdt_id as int64) = f.student_id
        where
            f.student_id is null
            or (d.first_name is not null and d.first_name is distinct from f.first_name)
            or (d.last_name is not null and d.last_name is distinct from f.last_name)
            or (
                d.middle_name is not null
                and d.middle_name is distinct from f.middle_name
            )
            or (
                d.stdt_email is not null
                and d.stdt_email is distinct from f.student_e_mail_address
            )
            or (d.dt_birth is not null and d.dt_birth is distinct from f.dt_birth_focus)
            or (d.gender is not null and d.gender is distinct from f.gender_focus)
            or (d.lang is not null and d.lang is distinct from f.language_label)
            or (
                d.ethnic_hl is not null
                and d.ethnic_hl is distinct from f.ethnic_hl_focus
            )
            or (
                d.race_am_ind_ak_nat is not null
                and d.race_am_ind_ak_nat is distinct from f.race_am_ind_ak_nat_focus
            )
            or (
                d.race_asian is not null
                and d.race_asian is distinct from f.race_asian_focus
            )
            or (
                d.race_black is not null
                and d.race_black is distinct from f.race_black_focus
            )
            or (
                d.race_nat_haw_pac_isl is not null
                and d.race_nat_haw_pac_isl is distinct from f.race_nat_haw_pac_isl_focus
            )
            or (
                d.race_white is not null
                and d.race_white is distinct from f.race_white_focus
            )
    )

select
    stdt_id,
    last_name,
    first_name,
    name_suffix,
    middle_name,
    nickname,
    dt_birth,
    gender,
    lang,
    stdt_email,
    ethnic_hl,
    single_ethnic,
    race_am_ind_ak_nat,
    race_asian,
    race_black,
    race_nat_haw_pac_isl,
    race_white,
    residence_county,
    contry_birth,
    homeroom_tchr,
    resident_st,
    birth_loc,
    bdate_verif,
    immun_st,
    primary_home_lang,
    native_parent_lang,
    grde_enter_dist,
    msix_id,
    homeroom,
    pmrn,
    internt_perm,
    act_perm,
    direct_perm,
    screen_perm,
    photo_vid_perm,
    survey_perm,
    mckay_sch_attend,
    fhsaa_el3_ind,
    fhsaa_el3ch_ind,
    dt_home_lang_survey,
    casas_track,
    lcp_cont_stdt,
from diffed
