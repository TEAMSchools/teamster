import json

import py_avro_schema

from teamster.libraries.finalsite.schema import (
    Contact,
    ContactStatus,
    Field,
    Grade,
    SchoolYear,
    StatusReport,
    User,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STATUS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StatusReport, options=pas_options)
)

CONTACT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Contact, options=pas_options)
)

CONTACT_STATUS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=ContactStatus, options=pas_options)
)

FIELD_SCHEMA = json.loads(py_avro_schema.generate(py_type=Field, options=pas_options))

GRADE_SCHEMA = json.loads(py_avro_schema.generate(py_type=Grade, options=pas_options))

SCHOOL_YEAR_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SchoolYear, options=pas_options)
)

USER_SCHEMA = json.loads(py_avro_schema.generate(py_type=User, options=pas_options))
