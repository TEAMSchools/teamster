import random

from fastavro import parse_schema, validation, writer
from numpy import nan
from pandas import read_csv

from teamster.core.renlearn.schema import ASSET_FIELDS
from teamster.core.utils.functions import get_avro_record_schema

CODE_LOCATION = "KIPPMIAMI"
# CODE_LOCATION = "KIPPNJ"


def _test(local_filepath, asset_name):
    df = read_csv(filepath_or_buffer=local_filepath, low_memory=False)

    df.replace({nan: None}, inplace=True)
    # df.rename(columns=lambda x: slugify(text=x, separator="_"), inplace=True)

    count = df.shape[0]
    records = df.to_dict(orient="records")
    # print(df.dtypes.to_dict())

    schema = get_avro_record_schema(name=asset_name, fields=ASSET_FIELDS[asset_name])
    # print(schema)

    parsed_schema = parse_schema(schema)

    sample_record = records[random.randint(a=0, b=(count - 1))]
    # sample_record = [r for r in records if "" in json.dumps(obj=r)]

    assert validation.validate(datum=sample_record, schema=parsed_schema, strict=True)

    assert validation.validate_many(records=records, schema=parsed_schema, strict=True)

    with open(file="/dev/null", mode="wb") as fo:
        writer(
            fo=fo,
            schema=parsed_schema,
            records=records,
            codec="snappy",
            strict_allow_default=True,
        )


def test_ar():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/AR.csv",
        asset_name="accelerated_reader",
    )


def test_sm():
    _test(local_filepath=f"env/renlearn/{CODE_LOCATION}/SM.csv", asset_name="star")


def test_sr():
    _test(local_filepath=f"env/renlearn/{CODE_LOCATION}/SR.csv", asset_name="star")


def test_sel():
    _test(local_filepath=f"env/renlearn/{CODE_LOCATION}/SEL.csv", asset_name="star")


def test_sel_dashboard_standards():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SEL_Dashboard_Standards_v2.csv",
        asset_name="star_dashboard_standards",
    )


def test_sm_dashboard_standards():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SM_Dashboard_Standards_v2.csv",
        asset_name="star_dashboard_standards",
    )


def test_sr_dashboard_standards():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SR_Dashboard_Standards_v2.csv",
        asset_name="star_dashboard_standards",
    )


def test_sel_skillarea():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SEL_SkillArea_v1.csv",
        asset_name="star_skill_area",
    )


def test_sm_skillarea():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SM_SkillArea_v1.csv",
        asset_name="star_skill_area",
    )


def test_sr_skillarea():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/SR_SkillArea_v1.csv",
        asset_name="star_skill_area",
    )


def test_fast_sm():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/FL_FAST_SM_K-2.csv",
        asset_name="fast_star",
    )


def test_fast_sr():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/FL_FAST_SR_K-2.csv",
        asset_name="fast_star",
    )


def test_fast_sel():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/FL_FAST_SEL_K-2.csv",
        asset_name="fast_star",
    )


def test_fast_sel_domains():
    _test(
        local_filepath=f"env/renlearn/{CODE_LOCATION}/FL_FAST_SEL_Domains_K-2.csv",
        asset_name="fast_star",
    )
