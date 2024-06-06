import json

import py_avro_schema

from teamster.libraries.fldoe.schema import EOC, FAST, FSA, Science


class fast_record(FAST):
    """helper classes for backwards compatibility"""


class fsa_record(FSA):
    """helper classes for backwards compatibility"""


pas_options = (
    py_avro_schema.Option.NO_DOC
    | py_avro_schema.Option.NO_AUTO_NAMESPACE
    | py_avro_schema.Option.USE_FIELD_ALIAS
)

ASSET_SCHEMA = {
    "fast": json.loads(
        py_avro_schema.generate(py_type=fast_record, options=pas_options)
    ),
    "fsa": json.loads(py_avro_schema.generate(py_type=fsa_record, options=pas_options)),
    "science": json.loads(
        py_avro_schema.generate(py_type=Science, options=pas_options)
    ),
    "eoc": json.loads(py_avro_schema.generate(py_type=EOC, options=pas_options)),
}
