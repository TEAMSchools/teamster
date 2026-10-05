from email.message import EmailMessage
from smtplib import SMTP, SMTPServerDisconnected

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

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._connect()

    def teardown_after_execution(self, context: InitResourceContext) -> None:
        try:
            self._server.quit()
        except SMTPServerDisconnected:
            pass

    def _connect(self) -> None:
        self._server = SMTP(host=self.host, port=self.port, timeout=self.timeout)

        # SMTP handshake
        self._server.ehlo()
        self._server.starttls()

        self._server.login(user=self.user, password=self.password)

    def send_message(
        self,
        subject: str,
        from_email: str,
        content_args: tuple,
        bcc_emails: str | None = None,
        to_emails: str | None = None,
        alternative_args: tuple | None = None,
    ) -> None:
        """Send one email, reconnecting once if the server dropped the session.

        Raises any other SMTP error to the caller, so a failed send is never
        reported as a success.
        """
        if to_emails is None:
            to_emails = from_email

        msg = EmailMessage()

        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_emails
        msg.set_content(*content_args)

        if bcc_emails is not None:
            msg["Bcc"] = bcc_emails

        if alternative_args is not None:
            msg.add_alternative(*alternative_args)

        try:
            self._server.send_message(msg=msg)
        except SMTPServerDisconnected:
            self._log.warning("SMTP session dropped; reconnecting")
            self._connect()
            self._server.send_message(msg=msg)
