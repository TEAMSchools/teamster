from dagster import build_init_resource_context, instance_for_test

from teamster.kipptaf.resources import GOOGLE_FORMS_RESOURCE


def test_google_forms_resource():
    with instance_for_test() as instance:
        context = build_init_resource_context(instance=instance)

        GOOGLE_FORMS_RESOURCE.setup_for_execution(context=context)
        forms = GOOGLE_FORMS_RESOURCE.list_forms()

        context.log.info(forms.get("files"))

    assert forms.get("files") is not None
