from dagster import build_init_resource_context, instance_for_test

from teamster.code_locations.kipptaf.resources import GOOGLE_FORMS_RESOURCE


def test_google_forms_resource():
    with instance_for_test() as instance:
        context = build_init_resource_context(instance=instance)
        assert context.log is not None

        GOOGLE_FORMS_RESOURCE.setup_for_execution(context=context)
        forms = GOOGLE_FORMS_RESOURCE.list_forms()

        files = forms.get("files")

        context.log.info(files)

    assert files is not None
