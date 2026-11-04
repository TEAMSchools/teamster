import json

import py_avro_schema

from teamster.libraries.edplan.schema import NJSmartPowerschool

NJSMART_POWERSCHOOL_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=NJSmartPowerschool,
        options=(
            py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE
        ),
    )
)
