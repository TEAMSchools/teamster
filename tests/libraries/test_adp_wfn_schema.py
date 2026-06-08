import json

import py_avro_schema

from teamster.libraries.adp.workforce_now.api.schema import Worker


def _worker_avro_schema() -> dict:
    return json.loads(
        py_avro_schema.generate(
            py_type=Worker,
            namespace="worker",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    )


def test_new_fields_parse():
    worker = Worker.model_validate(
        {
            "associateOID": "X",
            "customFieldGroup": {},
            "person": {
                "birthDate": "2000-01-01",
                "deathDate": "2099-01-01",
                "disabledIndicator": False,
                "customFieldGroup": {},
                "genderCode": {"codeValue": "M"},
                "legalName": {},
                "preferredName": {},
                "militaryClassificationCodes": [],
                "religionCode": {"codeValue": "R"},
                "communication": {
                    "pagers": [
                        {
                            "areaDialing": "1",
                            "countryDialing": "1",
                            "dialNumber": "5551234",
                            "formattedNumber": "555-1234",
                            "itemID": "pg1",
                            "nameCode": {"codeValue": "PAGER"},
                        }
                    ]
                },
            },
            "workerDates": {
                "originalHireDate": "2020-01-01",
                "adjustedServiceDate": "2020-01-01",
                "retirementDate": "2099-01-01",
            },
            "workerID": {"idValue": "123"},
            "workerStatus": {"statusCode": {"codeValue": "A"}},
            "workAssignments": [
                {
                    "actualStartDate": "2020-01-01",
                    "hireDate": "2020-01-01",
                    "itemID": "1",
                    "managementPositionIndicator": False,
                    "positionID": "p1",
                    "primaryIndicator": True,
                    "assignmentStatus": {"statusCode": {"codeValue": "A"}},
                    "payrollProcessingStatusCode": {"codeValue": "X"},
                    "jobFunctionCode": {"codeValue": "JF"},
                    "rehireEligibleIndicator": True,
                    "customCountryInputs": [],
                    "payGradeCode": {"codeValue": "PG"},
                    "payGradePayRange": {
                        "minimumRate": {"amountValue": 1.0},
                        "medianRate": {"amountValue": 2.0},
                        "maximumRate": {"amountValue": 3.0},
                    },
                    "laborUnion": {"laborUnionCode": {"codeValue": "U"}},
                    "workShiftCode": {"codeValue": "S"},
                }
            ],
        }
    )

    wa = worker.workAssignments[0]
    assert wa.jobFunctionCode is not None and wa.jobFunctionCode.codeValue == "JF"
    assert wa.rehireEligibleIndicator is True
    assert wa.payGradePayRange is not None
    assert wa.payGradePayRange.maximumRate.amountValue == 3.0
    assert wa.laborUnion is not None and wa.laborUnion.laborUnionCode.codeValue == "U"
    assert wa.workShiftCode is not None and wa.workShiftCode.codeValue == "S"
    assert wa.customCountryInputs == []
    assert worker.workerDates.adjustedServiceDate == "2020-01-01"
    assert worker.workerDates.retirementDate == "2099-01-01"
    assert worker.person.deathDate == "2099-01-01"
    assert worker.person.religionCode is not None
    assert worker.person.communication.pagers[0].dialNumber == "5551234"


def test_avro_schema_includes_new_fields():
    schema = _worker_avro_schema()

    top_level = {f["name"] for f in schema["fields"]}
    assert "workAssignments" in top_level
    assert "person" in top_level

    # every new field (including deeply-nested record fields) must survive
    # py_avro_schema generation — otherwise it is silently dropped at write time
    schema_json = json.dumps(schema)
    for field in [
        "religionCode",
        "identityDocuments",
        "deathDate",
        "adjustedServiceDate",
        "retirementDate",
        "faxes",
        "pagers",
        "amountFields",
        "percentFields",
        "telephoneFields",
        "deliveryPoint",
        "jobFunctionCode",
        "rehireEligibleIndicator",
        "customCountryInputs",
        "payGradeCode",
        "payGradePayRange",
        "laborUnion",
        "workShiftCode",
    ]:
        assert f'"{field}"' in schema_json, (
            f"{field} missing from generated Avro schema"
        )
