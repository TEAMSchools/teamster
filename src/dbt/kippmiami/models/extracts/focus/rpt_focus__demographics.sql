with
    focus_state as (
        select
            s.first_name,
            s.last_name,
            s.middle_name,
            s.student_e_mail_address,

            p.language_label,

            cast(s.student_id as string) as student_id,

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

    -- Emit a row only when the student is absent from Focus or any populated
    -- export field differs. The surrogate key compares the two sides as a unit;
    -- coalescing each export field to its Focus value means a null export field
    -- (not populated in Finalsite) never registers as a difference, so it never
    -- triggers a re-import.
    diffed as (
        select d.*,
        from {{ source("kipptaf_extracts", "rpt_focus__demographics") }} as d
        left join focus_state as f on d.stdt_id = f.student_id
        where
            f.student_id is null
            or
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "coalesce(d.first_name, f.first_name)",
                        "coalesce(d.last_name, f.last_name)",
                        "coalesce(d.middle_name, f.middle_name)",
                        "coalesce(d.stdt_email, f.student_e_mail_address)",
                        "coalesce(d.dt_birth, f.dt_birth_focus)",
                        "coalesce(d.gender, f.gender_focus)",
                        "coalesce(d.lang, f.language_label)",
                        "coalesce(d.ethnic_hl, f.ethnic_hl_focus)",
                        "coalesce(d.race_am_ind_ak_nat, f.race_am_ind_ak_nat_focus)",
                        "coalesce(d.race_asian, f.race_asian_focus)",
                        "coalesce(d.race_black, f.race_black_focus)",
                        "coalesce(d.race_nat_haw_pac_isl, f.race_nat_haw_pac_isl_focus)",
                        "coalesce(d.race_white, f.race_white_focus)",
                    ]
                )
            }}
            != {{
                dbt_utils.generate_surrogate_key(
                    [
                        "f.first_name",
                        "f.last_name",
                        "f.middle_name",
                        "f.student_e_mail_address",
                        "f.dt_birth_focus",
                        "f.gender_focus",
                        "f.language_label",
                        "f.ethnic_hl_focus",
                        "f.race_am_ind_ak_nat_focus",
                        "f.race_asian_focus",
                        "f.race_black_focus",
                        "f.race_nat_haw_pac_isl_focus",
                        "f.race_white_focus",
                    ]
                )
            }}
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
