import argparse
from copy import deepcopy
from io import BytesIO

import dagster as dg
from dagster_shared import check
from fastavro import parse_schema, reader, writer
from fastavro.types import Schema
from google.cloud import storage

from teamster.core.resources import GCS_RESOURCE


def rewrite_blob(
    blob: storage.Blob, asset_name: str, bucket: storage.Bucket, schema: Schema
):
    # split blob name
    blob_name_split = check.inst(obj=blob.name, ttype=str).split("/")

    # find index of blob name that matches asset name
    asset_name_index = blob_name_split.index(asset_name)

    # create copies
    blob_name_split_new = deepcopy(blob_name_split)
    blob_name_split_archive = deepcopy(blob_name_split)

    # rename index value
    blob_name_split_new[asset_name_index] = f"{asset_name}_new"
    blob_name_split_archive[asset_name_index] = f"{asset_name}_archive"

    # create new blobs
    new_blob = bucket.blob(blob_name="/".join(blob_name_split_new))
    archive_blob = bucket.blob(blob_name="/".join(blob_name_split_archive))

    # copy original blob to archive
    print(f"ARCHIVING: {blob.name}")
    archive_blob.rewrite(source=blob)

    print(f"READING: {blob.name}")
    with blob.open(mode="rb") as fo_read:
        # trunk-ignore(pyright/reportArgumentType)
        records = [record for record in reader(fo=fo_read)]

    print(f"WRITING: {new_blob.name}")
    with BytesIO() as fo_write:
        writer(fo=fo_write, schema=schema, records=records, codec="snappy")
        fo_write.seek(0)
        new_blob.upload_from_file(file_obj=fo_write)


def rewrite_blobs(asset_key: list[str], schema: Schema):
    with dg.build_resources(resources={"gcs": GCS_RESOURCE}) as resources:
        gcs: storage.Client = resources.gcs

    bucket = gcs.get_bucket(bucket_or_name=f"teamster-{asset_key[0]}")

    for blob in bucket.list_blobs(match_glob=f"dagster/{'/'.join(asset_key)}/**/data"):
        rewrite_blob(blob=blob, asset_name=asset_key[-1], bucket=bucket, schema=schema)


def rewrite_kipptaf_grow_assignments():
    from teamster.code_locations.kipptaf.level_data.grow.schema import ASSIGNMENT_SCHEMA

    rewrite_blobs(
        asset_key=["kipptaf", "schoolmint", "grow", "assignments"],
        schema=parse_schema(ASSIGNMENT_SCHEMA),
    )


def rewrite_kippcamden_deanslist_incidents():
    from teamster.code_locations.kippcamden.deanslist.schema import INCIDENTS_SCHEMA

    rewrite_blobs(
        asset_key=["kippcamden", "deanslist", "incidents"],
        schema=parse_schema(INCIDENTS_SCHEMA),
    )


def rewrite_kippmiami_deanslist_incidents():
    from teamster.code_locations.kippmiami.deanslist.schema import INCIDENTS_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "deanslist", "incidents"],
        schema=parse_schema(INCIDENTS_SCHEMA),
    )


def rewrite_kippnewark_deanslist_incidents():
    from teamster.code_locations.kippnewark.deanslist.schema import INCIDENTS_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "deanslist", "incidents"],
        schema=parse_schema(INCIDENTS_SCHEMA),
    )


def rewrite_kippmiami_fldoe_fast():
    from teamster.code_locations.kippmiami.fldoe.schema import FAST_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "fast"], schema=parse_schema(FAST_SCHEMA)
    )


def rewrite_kippmiami_fldoe_eoc():
    from teamster.code_locations.kippmiami.fldoe.schema import EOC_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "fldoe", "eoc"], schema=parse_schema(EOC_SCHEMA)
    )


def rewrite_kippnewark_renlearn_accelerated_reader():
    from teamster.code_locations.kippnewark.renlearn.schema import (
        ACCELERATED_READER_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippnewark", "renlearn", "accelerated_reader"],
        schema=parse_schema(ACCELERATED_READER_SCHEMA),
    )


def rewrite_kippnewark_renlearn_star():
    from teamster.code_locations.kippnewark.renlearn.schema import STAR_SCHEMA

    rewrite_blobs(
        asset_key=["kippnewark", "renlearn", "star"], schema=parse_schema(STAR_SCHEMA)
    )


def rewrite_kippmiami_renlearn_accelerated_reader():
    from teamster.code_locations.kippmiami.renlearn.schema import (
        ACCELERATED_READER_SCHEMA,
    )

    rewrite_blobs(
        asset_key=["kippmiami", "renlearn", "accelerated_reader"],
        schema=parse_schema(ACCELERATED_READER_SCHEMA),
    )


def rewrite_kippmiami_renlearn_star():
    from teamster.code_locations.kippmiami.renlearn.schema import STAR_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "renlearn", "star"], schema=parse_schema(STAR_SCHEMA)
    )


def rewrite_kippmiami_renlearn_fast_star():
    from teamster.code_locations.kippmiami.renlearn.schema import FAST_STAR_SCHEMA

    rewrite_blobs(
        asset_key=["kippmiami", "renlearn", "fast_star"],
        schema=parse_schema(FAST_STAR_SCHEMA),
    )


def main(fn):
    globals()[fn]()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)

    parser.add_argument("fn")
    args = parser.parse_args()

    main(args.fn)
