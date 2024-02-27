from teamster.core.utils.functions import get_avro_record_schema

WORKER_ID_FIELDS = [
    # idValue
]

WORKER_STATUS_FIELDS = [
    # statusCode
]

BUSINESS_COMMUNICATION_FIELDS = [
    # emails
    # faxes
    # landlines
    # mobiles
    # pagers
]

PERSON_FIELDS = [
    # birthDate
    # birthName
    # communication
    # customFieldGroup
    # deathDate
    # ethnicityCode
    # genderCode
    # genderSelfIdentityCode
    # governmentIDs
    # highestEducationLevelCode
    # legalAddress
    # maritalStatusCode
    # militaryClassificationCodes
    # militaryDischargeDate
    # otherPersonalAddresses
    # preferredGenderPronounCode
    # preferredName
    # raceCode
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

WORK_ASSIGNMENTS_FIELDS = [
    # actualStartDate
    # additionalRemunerations
    # assignedWorkLocations
    # assignmentStatus
    # bargainingUnit
    # baseRemuneration
    # customFieldGroup
    # fullTimeEquivalenceRatio
    # hireDate
    # homeOrganizationalUnits
    # homeWorkLocation
    # itemID
    # jobCode
    # jobFunctionCode
    # laborUnion
    # managementPositionIndicator
    # occupationalClassifications
    # payCycleCode
    # payGradeCode
    # payGradePayRange
    # payrollFileNumber
    # payrollGroupCode
    # positionID
    # primaryIndicator
    # reportsTo
    # seniorityDate
    # standardHours
    # standardPayPeriodHours
    # terminationDate
    # voluntaryIndicator
    # wageLawCoverage
    # workerGroups
    # workerTimeProfile
    # workerTypeCode
    # workShiftCode
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
                fields=BUSINESS_COMMUNICATION_FIELDS,
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

# businessCommunication/emails/emailUri
# businessCommunication/faxes/access
# businessCommunication/faxes/areaDialing
# businessCommunication/faxes/countryDialing
# businessCommunication/faxes/dialNumber
# businessCommunication/landlines/access
# businessCommunication/landlines/areaDialing
# businessCommunication/landlines/countryDialing
# businessCommunication/landlines/dialNumber
# businessCommunication/landlines/extension
# businessCommunication/mobiles/access
# businessCommunication/mobiles/areaDialing
# businessCommunication/mobiles/countryDialing
# businessCommunication/mobiles/dialNumber
# businessCommunication/pagers/access
# businessCommunication/pagers/areaDialing
# businessCommunication/pagers/countryDialing
# businessCommunication/pagers/dialNumber
# businessCommunication/pagers/extension
# person/birthName/familyName1
# person/communication/emails
# person/communication/faxes
# person/communication/landlines
# person/communication/mobiles
# person/communication/pagers
# person/customFieldGroup/amountFields
# person/customFieldGroup/codeFields
# person/customFieldGroup/dateFields
# person/customFieldGroup/indicatorFields
# person/customFieldGroup/numberFields
# person/customFieldGroup/percentFields
# person/customFieldGroup/stringFields
# person/customFieldGroup/telephoneFields
# person/ethnicityCode/codeValue
# person/ethnicityCode/longName
# person/ethnicityCode/shortName
# person/genderCode/codeValue
# person/genderCode/shortName
# person/genderSelfIdentityCode/codeValue
# person/genderSelfIdentityCode/shortName
# person/governmentIDs/countryCode
# person/governmentIDs/idValue
# person/governmentIDs/itemID
# person/governmentIDs/nameCode
# person/governmentIDs/statusCode
# person/highestEducationLevelCode/codeValue
# person/highestEducationLevelCode/longName
# person/highestEducationLevelCode/shortName
# person/legalAddress/cityName
# person/legalAddress/countryCode
# person/legalAddress/countrySubdivisionLevel1
# person/legalAddress/countrySubdivisionLevel2
# person/legalAddress/deliveryPoint
# person/legalAddress/lineOne
# person/legalAddress/lineThree
# person/legalAddress/lineTwo
# person/legalAddress/postalCode
# person/legalName/familyName1
# person/legalName/formattedName
# person/legalName/generationAffixCode
# person/legalName/givenName
# person/legalName/middleName
# person/legalName/nickName
# person/legalName/qualificationAffixCode
# person/maritalStatusCode/codeValue
# person/maritalStatusCode/effectiveDate
# person/maritalStatusCode/shortName
# person/militaryClassificationCodes/codeValue
# person/militaryClassificationCodes/longName
# person/militaryClassificationCodes/shortName
# person/otherPersonalAddresses/cityName
# person/otherPersonalAddresses/countryCode
# person/otherPersonalAddresses/countrySubdivisionLevel1
# person/otherPersonalAddresses/countrySubdivisionLevel2
# person/otherPersonalAddresses/lineOne
# person/otherPersonalAddresses/lineThree
# person/otherPersonalAddresses/lineTwo
# person/otherPersonalAddresses/postalCode
# person/preferredGenderPronounCode/codeValue
# person/preferredGenderPronounCode/longName
# person/preferredGenderPronounCode/shortName
# person/preferredName/familyName1
# person/preferredName/givenName
# person/preferredName/middleName
# person/raceCode/codeValue
# person/raceCode/identificationMethodCode
# person/raceCode/longName
# person/raceCode/shortName
# person/socialInsurancePrograms/coveredIndicator
# person/socialInsurancePrograms/nameCode

# photos/links/href

# workAssignments/additionalRemunerations/currencyCode
# workAssignments/additionalRemunerations/effectiveDate
# workAssignments/additionalRemunerations/itemID
# workAssignments/additionalRemunerations/nameCode
# workAssignments/additionalRemunerations/rate
# workAssignments/assignedWorkLocations/address
# workAssignments/assignmentStatus/reasonCode
# workAssignments/assignmentStatus/statusCode
# workAssignments/bargainingUnit/bargainingUnitCode
# workAssignments/baseRemuneration/hourlyRateAmount
# workAssignments/customFieldGroup/stringFields
# workAssignments/homeOrganizationalUnits/nameCode
# workAssignments/homeOrganizationalUnits/typeCode
# workAssignments/homeWorkLocation/address
# workAssignments/homeWorkLocation/nameCode
# workAssignments/jobCode/codeValue
# workAssignments/jobCode/longName
# workAssignments/jobCode/shortName
# workAssignments/laborUnion/laborUnionCode
# workAssignments/occupationalClassifications/classificationCode
# workAssignments/occupationalClassifications/nameCode
# workAssignments/payCycleCode/codeValue
# workAssignments/payCycleCode/longName
# workAssignments/payCycleCode/shortName
# workAssignments/payGradeCode/codeValue
# workAssignments/payGradeCode/longName
# workAssignments/payGradeCode/shortName
# workAssignments/payGradePayRange/maximumRate
# workAssignments/payGradePayRange/medianRate
# workAssignments/payGradePayRange/minimumRate
# workAssignments/reportsTo/positionID
# workAssignments/standardHours/hoursQuantity
# workAssignments/standardHours/unitCode
# workAssignments/standardPayPeriodHours/hoursQuantity
# workAssignments/workerGroups/groupCode
# workAssignments/workerTimeProfile/badgeID
# workAssignments/workerTimeProfile/timeAndAttendanceIndicator
# workAssignments/workerTimeProfile/timeServiceSupervisor
# workAssignments/workerTimeProfile/timeZoneCode
# workAssignments/workerTypeCode/codeValue
# workAssignments/workerTypeCode/longName
# workAssignments/workerTypeCode/shortName
# workAssignments/workShiftCode/codeValue
# workAssignments/workShiftCode/longName
# workAssignments/workShiftCode/shortName

# workerStatus/statusCode/codeValue
# workerStatus/statusCode/longName
# workerStatus/statusCode/shortName

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
