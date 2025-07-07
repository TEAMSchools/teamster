from dagster import build_resources

from teamster.libraries.email.resources import EmailResource


def test_outlook_email():
    from teamster.code_locations.kipptaf.resources import OUTLOOK_RESOURCE

    with build_resources(resources={"email": OUTLOOK_RESOURCE}) as resources:
        email: EmailResource = resources.email

    email.send_message(
        subject="TEST",
        from_email=email.user,
        # bcc_emails=...,
        content_args=("Hello World",),
    )
