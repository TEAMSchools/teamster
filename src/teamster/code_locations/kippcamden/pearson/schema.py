import json

import py_avro_schema

from teamster.libraries.pearson.schema import NJGPA, NJSLA, PARCC, StudentListReport


class parcc_record(PARCC):
    """helper classes for backwards compatibility"""


class njsla_record(NJSLA):
    """helper classes for backwards compatibility"""


class njsla_science_record(NJSLA):
    """helper classes for backwards compatibility"""


class njgpa_record(NJGPA):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

PARCC_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=parcc_record, options=pas_options)
)

NJSLA_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=njsla_record, options=pas_options)
)

NJSLA_SCIENCE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=njsla_science_record, options=pas_options)
)

NJGPA_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=njgpa_record, options=pas_options)
)

STUDENT_LIST_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StudentListReport, options=pas_options)
)
