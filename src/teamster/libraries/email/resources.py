from email.message import EmailMessage
from smtplib import SMTP

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr


class EmailResource(ConfigurableResource):
    host: str
    port: int
    user: str
    password: str
    chunk_size: int = 1
    timeout: int = 30

    _server: SMTP = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext):
        self._log = check.not_none(value=context.log)

        self._server = SMTP(host=self.host, port=self.port, timeout=self.timeout)
        self._server.set_debuglevel(1)  # Enable for troubleshooting

        # SMTP handshake
        self._server.ehlo()
        self._server.starttls()

        self._server.login(user=self.user, password=self.password)

    def send_message(
        self,
        subject: str,
        from_email: str,
        bcc_emails: str,
        content_args: tuple,
        to_emails: str | None = None,
        alternative_args: tuple | None = None,
    ):
        if to_emails is None:
            to_emails = from_email

        msg = EmailMessage()

        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_emails
        msg["Bcc"] = bcc_emails
        msg.set_content(*content_args)

        if alternative_args is not None:
            msg.add_alternative(*alternative_args)

        try:
            self._server.send_message(msg=msg)
            self._log.info(f"Email sent to {to_emails} {bcc_emails}")
        except Exception as e:
            self._log.error(msg=e)
