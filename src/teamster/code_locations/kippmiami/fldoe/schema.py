import json

import py_avro_schema

from teamster.libraries.fldoe.schema import EOC, FAST, FSA, FTE, Science

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

FAST_SCHEMA = json.loads(py_avro_schema.generate(py_type=FAST, options=pas_options))

SCIENCE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=Science, options=pas_options)
)

EOC_SCHEMA = json.loads(py_avro_schema.generate(py_type=EOC, options=pas_options))

FTE_SCHEMA = json.loads(py_avro_schema.generate(py_type=FTE, options=pas_options))

FSA_SCHEMA = json.loads(py_avro_schema.generate(py_type=FSA, options=pas_options))
