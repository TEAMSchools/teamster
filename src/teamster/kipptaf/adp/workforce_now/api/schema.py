from teamster.core.utils.functions import get_avro_record_schema

CODE_FIELDS = [
    # codeValue
    # effectiveDate
    # shortName
    # longName
    # identificationMethodCode
]

NAME_FIELDS = [
    # familyName1
    # formattedName
    # generationAffixCode
    # givenName
    # middleName
    # nickName
    # qualificationAffixCode
]

ADDRESS_FIELDS = [
    # cityName
    # countryCode
    # countrySubdivisionLevel1
    # countrySubdivisionLevel2
    # deliveryPoint
    # lineOne
    # lineThree
    # lineTwo
    # postalCode
]

LOCATION_FIELDS = [
    # address
    # nameCode
]

HOURS_FIELDS = [
    # hoursQuantity
    # unitCode
]

REMUNERATIONS_FIELDS = [
    # currencyCode
    # effectiveDate
    # itemID
    # nameCode
    # rate
    # hourlyRateAmount
]

CUSTOM_FIELD_GROUP_FIELDS = [
    # amountFields
    # codeFields
    # dateFields
    # indicatorFields
    # numberFields
    # percentFields
    # stringFields
    # telephoneFields
]

EMAIL_RECORD_FIELDS = [
    # emailUri
]

PHONE_FIELDS = [
    # access
    # areaDialing
    # countryDialing
    # dialNumber
    # extension
]


def get_communication_fields(parent_namespace):
    return [
        {
            "name": "emails",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="email",
                        fields=EMAIL_RECORD_FIELDS,
                        namespace=f"{parent_namespace}.communication",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "faxes",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="fax",
                        fields=PHONE_FIELDS,
                        namespace=f"{parent_namespace}.communication",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "landlines",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="landline",
                        fields=PHONE_FIELDS,
                        namespace=f"{parent_namespace}.communication",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "mobiles",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="mobile",
                        fields=PHONE_FIELDS,
                        namespace=f"{parent_namespace}.communication",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
        {
            "name": "pagers",
            "type": [
                "null",
                {
                    "type": "array",
                    "items": get_avro_record_schema(
                        name="pager",
                        fields=PHONE_FIELDS,
                        namespace=f"{parent_namespace}.communication",
                    ),
                    "default": [],
                },
            ],
            "default": None,
        },
    ]


GOVERNMENT_ID_FIELDS = [
    # countryCode
    # idValue
    # itemID
    # nameCode
    # statusCode
]

SOCIAL_INSURANCE_PROGRAMS_FIELDS = [
    # coveredIndicator
    # nameCode
]

PERSON_FIELDS = [
    {"name": "birthDate", "type": ["null", "string"], "default": None},
    {"name": "deathDate", "type": ["null", "string"], "default": None},
    {"name": "militaryDischargeDate", "type": ["null", "string"], "default": None},
    #
    {
        "name": "birthName",
        "type": [
            "null",
            get_avro_record_schema(
                name="birth_name", fields=NAME_FIELDS, namespace="worker.person"
            ),
        ],
        "default": None,
    },
    {
        "name": "communication",
        "type": [
            "null",
            get_avro_record_schema(
                name="communication",
                fields=get_communication_fields("worker.person"),
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "customFieldGroup",
        "type": [
            "null",
            get_avro_record_schema(
                name="custom_field_group",
                fields=CUSTOM_FIELD_GROUP_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "ethnicityCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="ethnicity_code", fields=CODE_FIELDS, namespace="worker.person"
            ),
        ],
        "default": None,
    },
    {
        "name": "genderCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="gender_code", fields=CODE_FIELDS, namespace="worker.person"
            ),
        ],
        "default": None,
    },
    {
        "name": "genderSelfIdentityCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="gender_self_identity_code",
                fields=CODE_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "governmentIDs",
        "type": [
            "null",
            get_avro_record_schema(
                name="government_id",
                fields=GOVERNMENT_ID_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "highestEducationLevelCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="highest_education_level_code",
                fields=CODE_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "legalAddress",
        "type": [
            "null",
            get_avro_record_schema(
                name="legal_address",
                fields=ADDRESS_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "maritalStatusCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="marital_status_code",
                fields=CODE_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "militaryClassificationCodes",
        "type": [
            "null",
            get_avro_record_schema(
                name="military_classification_codes",
                fields=CODE_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "otherPersonalAddresses",
        "type": [
            "null",
            get_avro_record_schema(
                name="other_personal_addresses",
                fields=ADDRESS_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "preferredGenderPronounCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="preferred_gender_pronoun_code",
                fields=CODE_FIELDS,
                namespace="worker.person",
            ),
        ],
        "default": None,
    },
    {
        "name": "preferredName",
        "type": [
            "null",
            get_avro_record_schema(
                name="preferred_name", fields=NAME_FIELDS, namespace="worker.person"
            ),
        ],
        "default": None,
    },
    {
        "name": "raceCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="race_code", fields=CODE_FIELDS, namespace="worker.person"
            ),
        ],
        "default": None,
    },
]

WORKER_ID_FIELDS = [{"name": "idValue", "type": ["null", "string"], "default": None}]

WORKER_STATUS_FIELDS = [
    {
        "name": "statusCode",
        "type": [
            "null",
            get_avro_record_schema(
                name="status_code", fields=CODE_FIELDS, namespace="worker.status_code"
            ),
        ],
        "default": None,
    }
]

LINK_FIELDS = [
    # href
]
PHOTOS_FIELDS = [
    # links
]

WORKER_DATES_FIELDS = [
    # adjustedServiceDate
    # originalHireDate
    # rehireDate
    # retirementDate
    # terminationDate
]

ASSIGNMENT_STATUS_FIELDS = [
    # reasonCode
    # statusCode
]

BARGAINING_UNIT_FIELDS = [
    # bargainingUnitCode
]

LABOR_UNION_FIELDS = [
    # laborUnionCode
]

PAY_GRADE_PAY_RANGE_FIELDS = [
    # maximumRate
    # medianRate
    # minimumRate
]

WAGE_LAW_COVERAGE_FIELDS = [
    # wageLawNameCode
]

WORKER_TIME_PROFILE_FIELDS = [
    # badgeID
    # timeAndAttendanceIndicator
    # timeServiceSupervisor
    # timeZoneCode
]

HOME_ORGANIZATIONAL_UNITS_FIELDS = [
    # nameCode
    # typeCode
]

OCCUPATIONAL_CLASSIFICATIONS_FIELDS = [
    # classificationCode
    # nameCode
]

REPORTS_TO_FIELDS = [
    # positionID
]

WORKER_GROUPS_FIELDS = [
    # groupCode
]

WORK_ASSIGNMENTS_FIELDS = [
    # actualStartDate
    # fullTimeEquivalenceRatio
    # hireDate
    # itemID
    # jobFunctionCode
    # managementPositionIndicator
    # payrollFileNumber
    # payrollGroupCode
    # positionID
    # primaryIndicator
    # seniorityDate
    # terminationDate
    # voluntaryIndicator
    #
    # assignmentStatus/
    # bargainingUnit/
    # baseRemuneration/
    # customFieldGroup/
    # homeWorkLocation/
    # laborUnion/
    # payGradePayRange/
    # standardHours/
    # standardPayPeriodHours/
    # wageLawCoverage/
    # workerTimeProfile/
    #
    # jobCode/
    # payCycleCode/
    # payGradeCode/
    # workerTypeCode/
    # workShiftCode/
    #
    # additionalRemunerations/
    # assignedWorkLocations/
    # homeOrganizationalUnits/
    # occupationalClassifications/
    # reportsTo/
    # workerGroups/
]

WORKER_FIELDS = [
    {"name": "associateOID", "type": ["null", "string"], "default": None},
    #
    {
        "name": "workerID",
        "type": [
            "null",
            get_avro_record_schema(
                name="worker_id", fields=WORKER_ID_FIELDS, namespace="worker"
            ),
        ],
        "default": None,
    },
    {
        "name": "businessCommunication",
        "type": [
            "null",
            get_avro_record_schema(
                name="business_communication",
                fields=get_communication_fields("worker"),
                namespace="worker",
            ),
        ],
        "default": None,
    },
    {
        "name": "person",
        "type": [
            "null",
            get_avro_record_schema(
                name="person", fields=PERSON_FIELDS, namespace="worker"
            ),
        ],
        "default": None,
    },
    {
        "name": "workerStatus",
        "type": [
            "null",
            get_avro_record_schema(
                name="worker_status", fields=WORKER_STATUS_FIELDS, namespace="worker"
            ),
        ],
        "default": None,
    },
    #
    {
        "name": "photos",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="photos", fields=PHOTOS_FIELDS, namespace="worker"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "workAssignments",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="work_assignments",
                    fields=WORK_ASSIGNMENTS_FIELDS,
                    namespace="worker",
                ),
                "default": [],
            },
        ],
        "default": None,
    },
    {
        "name": "workerDates",
        "type": [
            "null",
            {
                "type": "array",
                "items": get_avro_record_schema(
                    name="worker_dates", fields=WORKER_DATES_FIELDS, namespace="worker"
                ),
                "default": [],
            },
        ],
        "default": None,
    },
]

# ---

# person/communication/emails/emailUri
# person/communication/faxes/access
# person/communication/faxes/areaDialing
# person/communication/faxes/countryDialing
# person/communication/faxes/dialNumber
# person/communication/landlines/access
# person/communication/landlines/areaDialing
# person/communication/landlines/countryDialing
# person/communication/landlines/dialNumber
# person/communication/mobiles/access
# person/communication/mobiles/areaDialing
# person/communication/mobiles/countryDialing
# person/communication/mobiles/dialNumber
# person/communication/pagers/access
# person/communication/pagers/areaDialing
# person/communication/pagers/countryDialing
# person/communication/pagers/dialNumber
# person/communication/pagers/extension
# person/customFieldGroup/amountFields/amountValue
# person/customFieldGroup/amountFields/currencyCode
# person/customFieldGroup/amountFields/nameCode
# person/customFieldGroup/codeFields/codeValue
# person/customFieldGroup/codeFields/itemID
# person/customFieldGroup/codeFields/longName
# person/customFieldGroup/codeFields/nameCode
# person/customFieldGroup/codeFields/shortName
# person/customFieldGroup/dateFields/dateValue
# person/customFieldGroup/dateFields/itemID
# person/customFieldGroup/dateFields/nameCode
# person/customFieldGroup/indicatorFields/indicatorValue
# person/customFieldGroup/indicatorFields/itemID
# person/customFieldGroup/indicatorFields/nameCode
# person/customFieldGroup/numberFields/itemID
# person/customFieldGroup/numberFields/nameCode
# person/customFieldGroup/numberFields/numberValue
# person/customFieldGroup/percentFields/itemID
# person/customFieldGroup/percentFields/nameCode
# person/customFieldGroup/percentFields/percentValue
# person/customFieldGroup/stringFields/itemID
# person/customFieldGroup/stringFields/nameCode
# person/customFieldGroup/stringFields/stringValue
# person/customFieldGroup/telephoneFields/formattedNumber
# person/customFieldGroup/telephoneFields/itemID
# person/customFieldGroup/telephoneFields/nameCode
# person/governmentIDs/nameCode/codeValue
# person/governmentIDs/nameCode/longName
# person/governmentIDs/nameCode/shortName
# person/legalAddress/countrySubdivisionLevel1/codeValue
# person/legalAddress/countrySubdivisionLevel1/longName
# person/legalAddress/countrySubdivisionLevel1/shortName
# person/legalAddress/countrySubdivisionLevel1/subdivisionType
# person/legalAddress/countrySubdivisionLevel2/codeValue
# person/legalAddress/countrySubdivisionLevel2/longName
# person/legalAddress/countrySubdivisionLevel2/shortName
# person/legalAddress/countrySubdivisionLevel2/subdivisionType
# person/legalName/generationAffixCode/codeValue
# person/legalName/generationAffixCode/shortName
# person/legalName/preferredSalutations/salutationCode
# person/legalName/qualificationAffixCode/codeValue
# person/legalName/qualificationAffixCode/longName
# person/legalName/qualificationAffixCode/shortName
# person/otherPersonalAddresses/countrySubdivisionLevel1/codeValue
# person/otherPersonalAddresses/countrySubdivisionLevel1/countrySubdivisionLevel1
# person/otherPersonalAddresses/countrySubdivisionLevel1/shortName
# person/otherPersonalAddresses/countrySubdivisionLevel2/codeValue
# person/otherPersonalAddresses/countrySubdivisionLevel2/longName
# person/otherPersonalAddresses/countrySubdivisionLevel2/shortName
# person/raceCode/identificationMethodCode/codeValue
# person/raceCode/identificationMethodCode/shortName
# workAssignments/additionalRemunerations/nameCode/codeValue
# workAssignments/additionalRemunerations/nameCode/shortName
# workAssignments/additionalRemunerations/rate/amountValue
# workAssignments/assignedWorkLocations/address/cityName
# workAssignments/assignedWorkLocations/address/countryCode
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel1
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel2
# workAssignments/assignedWorkLocations/address/lineOne
# workAssignments/assignedWorkLocations/address/lineThree
# workAssignments/assignedWorkLocations/address/lineTwo
# workAssignments/assignedWorkLocations/address/nameCode
# workAssignments/assignedWorkLocations/address/postalCode
# workAssignments/assignmentStatus/reasonCode/codeValue
# workAssignments/assignmentStatus/reasonCode/shortName
# workAssignments/assignmentStatus/statusCode/codeValue
# workAssignments/assignmentStatus/statusCode/longName
# workAssignments/assignmentStatus/statusCode/shortName
# workAssignments/bargainingUnit/bargainingUnitCode/codeValue
# workAssignments/bargainingUnit/bargainingUnitCode/longName
# workAssignments/bargainingUnit/bargainingUnitCode/shortName
# workAssignments/baseRemuneration/hourlyRateAmount/amountValue
# workAssignments/baseRemuneration/hourlyRateAmount/currencyCode
# workAssignments/baseRemuneration/hourlyRateAmount/nameCode
# workAssignments/customFieldGroup/stringFields/itemID
# workAssignments/customFieldGroup/stringFields/nameCode
# workAssignments/customFieldGroup/stringFields/stringValue
# workAssignments/homeOrganizationalUnits/nameCode/codeValue
# workAssignments/homeOrganizationalUnits/nameCode/longName
# workAssignments/homeOrganizationalUnits/nameCode/shortName
# workAssignments/homeOrganizationalUnits/typeCode/codeValue
# workAssignments/homeOrganizationalUnits/typeCode/longName
# workAssignments/homeOrganizationalUnits/typeCode/shortName
# workAssignments/homeWorkLocation/address/cityName
# workAssignments/homeWorkLocation/address/countryCode
# workAssignments/homeWorkLocation/address/countrySubdivisionLevel1
# workAssignments/homeWorkLocation/address/countrySubDivisionLevel2
# workAssignments/homeWorkLocation/address/lineOne
# workAssignments/homeWorkLocation/address/lineThree
# workAssignments/homeWorkLocation/address/lineTwo
# workAssignments/homeWorkLocation/address/postalCode
# workAssignments/homeWorkLocation/nameCode/codeValue
# workAssignments/homeWorkLocation/nameCode/longName
# workAssignments/homeWorkLocation/nameCode/shortName
# workAssignments/laborUnion/laborUnionCode/codeValue
# workAssignments/laborUnion/laborUnionCode/longName
# workAssignments/laborUnion/laborUnionCode/shortName
# workAssignments/occupationalClassifications/classificationCode/codeValue
# workAssignments/occupationalClassifications/classificationCode/longName
# workAssignments/occupationalClassifications/classificationCode/shortName
# workAssignments/occupationalClassifications/nameCode/codeValue
# workAssignments/occupationalClassifications/nameCode/longName
# workAssignments/occupationalClassifications/nameCode/shortName
# workAssignments/payGradePayRange/maximumRate/amountValue
# workAssignments/payGradePayRange/medianRate/amountValue
# workAssignments/payGradePayRange/minimumRate/amountValue
# workAssignments/reportsTo/reportsToWorkerName/associateOID
# workAssignments/reportsTo/reportsToWorkerName/formattedName
# workAssignments/reportsTo/workerID/idValue
# workAssignments/standardHours/unitCode/codeValue
# workAssignments/standardHours/unitCode/longName
# workAssignments/standardHours/unitCode/shortName
# workAssignments/wageLawCoverage/wageLawNameCode/codeValue
# workAssignments/wageLawCoverage/wageLawNameCode/longName
# workAssignments/wageLawCoverage/wageLawNameCode/shortName
# workAssignments/workerGroups/groupCode/codeValue
# workAssignments/workerGroups/groupCode/longName
# workAssignments/workerGroups/groupCode/shortName
# workAssignments/workerTimeProfile/timeServiceSupervisor/associateOID
# workAssignments/workerTimeProfile/timeServiceSupervisor/positionID
# workAssignments/workerTimeProfile/timeServiceSupervisor/reportsToWorkerName
# workAssignments/workerTimeProfile/timeServiceSupervisor/workerID

# ---

# person/customFieldGroup/amountFields/nameCode/codeValue
# person/customFieldGroup/amountFields/nameCode/longName
# person/customFieldGroup/amountFields/nameCode/shortName
# person/customFieldGroup/codeFields/nameCode/codeValue
# person/customFieldGroup/codeFields/nameCode/longName
# person/customFieldGroup/codeFields/nameCode/shortName
# person/customFieldGroup/dateFields/nameCode/codeValue
# person/customFieldGroup/indicatorFields/nameCode/codeValue
# person/customFieldGroup/indicatorFields/nameCode/longName
# person/customFieldGroup/indicatorFields/nameCode/shortName
# person/customFieldGroup/numberFields/nameCode/codeValue
# person/customFieldGroup/numberFields/nameCode/longName
# person/customFieldGroup/numberFields/nameCode/shortName
# person/customFieldGroup/percentFields/nameCode/codeValue
# person/customFieldGroup/percentFields/nameCode/longName
# person/customFieldGroup/percentFields/nameCode/shortName
# person/customFieldGroup/stringFields/nameCode/codeValue
# person/customFieldGroup/stringFields/nameCode/longName
# person/customFieldGroup/stringFields/nameCode/shortName
# person/customFieldGroup/telephoneFields/nameCode/codeValue
# person/customFieldGroup/telephoneFields/nameCode/longName
# person/customFieldGroup/telephoneFields/nameCode/shortName
# person/legalName/preferredSalutations/salutationCode/codeValue
# person/legalName/preferredSalutations/salutationCode/shortName
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel1/codeValue
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel1/longName
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel1/shortName
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel1/subdivisionType
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel2/codeValue
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel2/longName
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel2/shortName
# workAssignments/assignedWorkLocations/address/countrySubdivisionLevel2/subdivisionType
# workAssignments/assignedWorkLocations/address/nameCode/codeValue
# workAssignments/baseRemuneration/hourlyRateAmount/nameCode/codeValue
# workAssignments/baseRemuneration/hourlyRateAmount/nameCode/shortName
# workAssignments/customFieldGroup/stringFields/nameCode/codeValue
# workAssignments/customFieldGroup/stringFields/nameCode/shortName
# workAssignments/workerTimeProfile/timeServiceSupervisor/reportsToWorkerName/familyName1
# workAssignments/workerTimeProfile/timeServiceSupervisor/reportsToWorkerName/formattedName
# workAssignments/workerTimeProfile/timeServiceSupervisor/reportsToWorkerName/givenName
# workAssignments/workerTimeProfile/timeServiceSupervisor/reportsToWorkerName/middleName
# workAssignments/workerTimeProfile/timeServiceSupervisor/workerID/idValue

# ---

# workAssignments/assignedWorkLocations/address/nameCode/codeValue/longName
# workAssignments/assignedWorkLocations/address/nameCode/codeValue/shortName

# ---
