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

ASSET_SCHEMA = {
    "parcc": json.loads(
        py_avro_schema.generate(py_type=parcc_record, options=pas_options)
    ),
    "njsla": json.loads(
        py_avro_schema.generate(py_type=njsla_record, options=pas_options)
    ),
    "njsla_science": json.loads(
        py_avro_schema.generate(py_type=njsla_science_record, options=pas_options)
    ),
    "njgpa": json.loads(
        py_avro_schema.generate(py_type=njgpa_record, options=pas_options)
    ),
    "student_list_report": json.loads(
        py_avro_schema.generate(py_type=StudentListReport, options=pas_options)
    ),
}
