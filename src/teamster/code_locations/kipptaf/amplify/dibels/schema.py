import json

import py_avro_schema

from teamster.libraries.amplify.dibels.schema import DataFarming

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

DATA_FARMING_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=DataFarming, options=pas_options)
)
