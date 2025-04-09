import time
from pathlib import Path

from dagster import Config, OpExecutionContext, op

from teamster.libraries.email.resources import EmailResource


class SendEmailOpConfig(Config):
    subject: str
    text_body: str
    template_path: str | None = None


def chunk(obj: list, size: int):
    """Yield successive chunks from list object."""
    for i in range(0, len(obj), size):
        yield obj[i : i + size]


@op
def send_email_op(
    context: OpExecutionContext,
    config: SendEmailOpConfig,
    email: EmailResource,
    recipients,
):
    if config.template_path:
        alternative_args = (Path(config.template_path).read_text(), "html")
    else:
        alternative_args = None

    for i, batch in enumerate(chunk(obj=recipients, size=450)):
        context.log.info(f"Processing batch {i} ({len(batch)} recipients)")

        for recipient in batch:
            email.send_message(
                subject=config.subject,
                from_email=email.user,
                to_email=recipient["email"],
                content_args=(config.text_body,),
                alternative_args=alternative_args,
            )

            if email.test:
                time.sleep(1)

        time.sleep(60)
