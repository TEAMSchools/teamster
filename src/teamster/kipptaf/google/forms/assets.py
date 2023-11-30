from dagster import StaticPartitionsDefinition

from teamster.core.google.forms.assets import build_google_forms_assets

from ... import CODE_LOCATION

FORM_IDS = [
    "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA",  # staff info
    "1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0",  # manager
    "1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI",  # support
]

google_forms_assets = build_google_forms_assets(
    code_location=CODE_LOCATION, partitions_def=StaticPartitionsDefinition(FORM_IDS)
)
