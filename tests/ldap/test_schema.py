import pickle
import random

from fastavro import parse_schema, validation, writer

from teamster.core.ldap.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

# from numpy import nan
# from pandas import DataFrame, read_pickle


TESTS = [
    # {
    #     "local_filepath": "env/(&(objectClass=user)(objectCategory=person)).pickle",
    #     "asset_name": "user_person",
    # },
    {"local_filepath": "env/(objectClass=group).pickle", "asset_name": "group"},
]


def test_schema():
    for test in TESTS:
        print(test)

        with open(file=test["local_filepath"], mode="rb") as f:
            records = pickle.load(file=f)

        # df = DataFrame(
        #     data=read_pickle(filepath_or_buffer=test["local_filepath"])
        # ).replace({nan: None})
        # dtypes_dict = df.dtypes.to_dict()
        # print(dtypes_dict)
        # records = df.to_dict(orient="records")

        count = len(records)

        asset_name = test["asset_name"]
        schema = get_avro_record_schema(
            name=asset_name, fields=ASSET_FIELDS[asset_name]
        )
        # print(schema)

        parsed_schema = parse_schema(schema)

        sample_record = records[random.randint(a=0, b=(count - 1))]
        # sample_record = [r for r in records if "" in json.dumps(obj=r)]
        print(sample_record)

        assert validation.validate(
            datum=sample_record, schema=parsed_schema, strict=True
        )

        assert validation.validate_many(
            records=records, schema=parsed_schema, strict=True
        )

        with open(file="/dev/null", mode="wb") as fo:
            writer(
                fo=fo,
                schema=parsed_schema,
                records=records,
                codec="snappy",
                strict_allow_default=True,
            )
