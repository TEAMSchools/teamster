NJSMART_POWERSCHOOL_FIELDS = [
    {"name": "dob", "type": ["null", "string"], "default": None},
    {"name": "first_name", "type": ["null", "string"], "default": None},
    {"name": "last_name", "type": ["null", "string"], "default": None},
    {"name": "nj_se_delayreason", "type": ["null", "double"], "default": None},
    {"name": "nj_se_earlyintervention", "type": ["null", "string"], "default": None},
    {"name": "nj_se_eligibilityddate", "type": ["null", "string"], "default": None},
    {"name": "nj_se_lastiepmeetingdate", "type": ["null", "string"], "default": None},
    {"name": "nj_se_parentalconsentdate", "type": ["null", "string"], "default": None},
    {"name": "nj_se_placement", "type": ["null", "double"], "default": None},
    {"name": "nj_se_reevaluationdate", "type": ["null", "string"], "default": None},
    {"name": "nj_se_referraldate", "type": ["null", "string"], "default": None},
    {"name": "nj_timeinregularprogram", "type": ["null", "string"], "default": None},
    {"name": "special_education", "type": ["null", "double"], "default": None},
    {
        "name": "state_studentnumber",
        "type": ["null", "long", "double"],
        "default": None,
    },
    {"name": "student_number", "type": ["null", "long"], "default": None},
    {"name": "ti_serv_counseling", "type": ["null", "string"], "default": None},
    {"name": "ti_serv_occup", "type": ["null", "string"], "default": None},
    {"name": "ti_serv_other", "type": ["null", "string"], "default": None},
    {"name": "ti_serv_physical", "type": ["null", "string"], "default": None},
    {"name": "ti_serv_speech", "type": ["null", "string"], "default": None},
    {
        "name": "nj_se_initialiepmeetingdate",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "nj_se_parentalconsentobtained",
        "type": ["null", "string"],
        "default": None,
    },
    {
        "name": "nj_se_consenttoimplementdate",
        "type": ["null", "string"],
        "default": None,
    },
]

ASSET_FIELDS = {
    "njsmart_powerschool": NJSMART_POWERSCHOOL_FIELDS,
}
