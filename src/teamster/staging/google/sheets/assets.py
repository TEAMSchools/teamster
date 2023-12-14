import re

from dagster import AssetSpec, external_asset_from_spec

from ... import CODE_LOCATION

uri = "https://docs.google.com/spreadsheets/d/1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE"
range_name = "src_assessments__course_subject_crosswalk"

re_match = re.match(
    pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
)

google_sheets_assets = [
    external_asset_from_spec(
        AssetSpec(
            key=[CODE_LOCATION, "google", "sheets", "test"],
            metadata={"sheet_id": re_match.group(1), "range_name": range_name},
            group_name="google_sheets",
        )
    )
]

_all = [
    google_sheets_assets,
]
