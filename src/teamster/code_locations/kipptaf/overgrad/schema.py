import json

import py_avro_schema

from teamster.libraries.overgrad.schema import (
    Admission,
    CustomField,
    Following,
    School,
    Student,
    University,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

ADMISSION_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Admission, options=pas_options)
)

SCHOOL_SCHEMA = json.loads(py_avro_schema.generate(py_type=School, options=pas_options))

STUDENT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Student, options=pas_options)
)

FOLLOWING_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Following, options=pas_options)
)

UNIVERSITY_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=University, options=pas_options)
)

CUSTOM_FIELD_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=CustomField, options=pas_options)
)
