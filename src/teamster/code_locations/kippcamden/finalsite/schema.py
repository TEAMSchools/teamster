import json

import py_avro_schema

from teamster.libraries.finalsite.schema import StatusReport

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

STATUS_REPORT_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StatusReport, options=pas_options)
)
