from teamster.kipptaf.google.sheets.assets import build_google_sheets_asset

_all = [
    build_google_sheets_asset(
        source_name="test",
        name="asset",
        uri="https://docs.google.com/spreadsheets/d/1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE",
        range_name="src_assessments__course_subject_crosswalk"
    )
]
