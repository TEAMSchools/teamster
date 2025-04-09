from email.message import EmailMessage
from smtplib import SMTP

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext, _check
from pydantic import PrivateAttr


class EmailResource(ConfigurableResource):
    host: str
    port: int
    user: str
    password: str
    timeout: int = 30
    test: bool = False

    _server: SMTP = PrivateAttr()
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext):
        self._log = _check.not_none(value=context.log)

        self._server = SMTP(host=self.host, port=self.port, timeout=self.timeout)
        self._server.set_debuglevel(1)  # Enable for troubleshooting

        # SMTP handshake
        self._server.ehlo()

        if self.test or self.port in [587, 2525]:
            self._server.starttls()

        # authenticate
        if self.test:
            self._server.login(user=self.user, password=self.password)
        else:
            self._server.docmd(cmd="AUTH LOGIN")
            self._server.docmd(cmd=self.user.encode("utf-8").hex())
            self._server.docmd(cmd=self.password.encode("utf-8").hex())

    def send_message(
        self,
        subject: str,
        from_email: str,
        to_email: str,
        content_args: tuple,
        alternative_args: tuple | None = None,
    ):
        msg = EmailMessage()

        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.set_content(*content_args)

        if alternative_args is not None:
            msg.add_alternative(*alternative_args)

        try:
            self._server.send_message(msg=msg)
            self._log.info(f"Email sent to {to_email}")
        except Exception as e:
            self._log.error(msg=e)
