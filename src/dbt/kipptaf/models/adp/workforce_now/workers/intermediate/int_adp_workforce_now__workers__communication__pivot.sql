select
    associate_oid,

    item_id_homephone as communication__home_phone__item_id,
    formatted_number_homephone as communication__home_phone__formatted_number,
    country_dialing_homephone as communication__home_phone__country_dialing,
    area_dialing_homephone as communication__home_phone__area_dialing,
    dial_number_homephone as communication__home_phone__dial_number,
    extension_homephone as communication__home_phone__extension,
    access_homephone as communication__home_phone__access,

    item_id_personalcell as communication__personal_cell__item_id,
    formatted_number_personalcell as communication__personal_cell__formatted_number,
    country_dialing_personalcell as communication__personal_cell__country_dialing,
    area_dialing_personalcell as communication__personal_cell__area_dialing,
    dial_number_personalcell as communication__personal_cell__dial_number,
    extension_personalcell as communication__personal_cell__extension,
    access_personalcell as communication__personal_cell__access,

    item_id_personalemail as communication__personal_email__item_id,
    email_uri_personalemail as communication__personal_email__email_uri,
    notification_indicator_personalemail
    as communication__personal_email__notification_indicator,

    item_id_workcell as communication__work_cell__item_id,
    formatted_number_workcell as communication__work_cell__formatted_number,
    country_dialing_workcell as communication__work_cell__country_dialing,
    area_dialing_workcell as communication__work_cell__area_dialing,
    dial_number_workcell as communication__work_cell__dial_number,
    extension_workcell as communication__work_cell__extension,
    access_workcell as communication__work_cell__access,

    item_id_workemail as communication__work_email__item_id,
    email_uri_workemail as communication__work_email__email_uri,
    notification_indicator_workemail
    as communication__work_email__notification_indicator,

    item_id_workphone as communication__work_phone__item_id,
    formatted_number_workphone as communication__work_phone__formatted_number,
    country_dialing_workphone as communication__work_phone__country_dialing,
    area_dialing_workphone as communication__work_phone__area_dialing,
    dial_number_workphone as communication__work_phone__dial_number,
    extension_workphone as communication__work_phone__extension,
    access_workphone as communication__work_phone__access,
from
    {{ ref("int_adp_workforce_now__workers__communication") }} pivot (
        max(item_id) as item_id,
        max(email_uri) as email_uri,
        max(notification_indicator) as notification_indicator,
        max(formatted_number) as formatted_number,
        max(country_dialing) as country_dialing,
        max(area_dialing) as area_dialing,
        max(dial_number) as dial_number,
        max(`extension`) as `extension`,
        max(`access`) as `access`
        for regexp_replace(name_code__code_value, r'\W', '') in (
            'HomePhone',
            'PersonalCell',
            'PersonalEmail',
            'WorkCell',
            'WorkEmail',
            'WorkPhone'
        )
    )
