class BaseSSHTunnelForwarderError(Exception):
    """Exception raised by :class:`SSHTunnelForwarder` errors"""

    def __init__(self, *args, **kwargs):
        self.value = kwargs.pop("value", args[0] if args else "")

    def __str__(self):
        return self.value


class HandlerSSHTunnelForwarderError(BaseSSHTunnelForwarderError):
    """Exception for Tunnel forwarder errors"""

    pass
