import json
import pathlib

import fastavro
import py_avro_schema

from teamster.core.titan.schema import person_data_record

fp = pathlib.Path("env/titan/person_data/data.avro")

generated_schema = py_avro_schema.generate(
    py_type=person_data_record, namespace="person_data"
)

reader_schema = fastavro.parse_schema(json.loads(generated_schema))

avro_reader = fastavro.reader(fo=fp.open(mode="rb"), reader_schema=reader_schema)

record = next(avro_reader)

print(record)
