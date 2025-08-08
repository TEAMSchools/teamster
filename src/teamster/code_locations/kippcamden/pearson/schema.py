import json

import py_avro_schema

from teamster.libraries.pearson.schema import (
    NJGPA,
    NJSLA,
    PARCC,
    StudentListReport,
    StudentTestUpdate,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

PARCC_SCHEMA = json.loads(py_avro_schema.generate(py_type=PARCC, options=pas_options))

NJSLA_SCHEMA = json.loads(py_avro_schema.generate(py_type=NJSLA, options=pas_options))

NJGPA_SCHEMA = json.loads(py_avro_schema.generate(py_type=NJGPA, options=pas_options))

STUDENT_LIST_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentListReport, options=pas_options)
)

STUDENT_TEST_UPDATE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentTestUpdate, options=pas_options)
)
