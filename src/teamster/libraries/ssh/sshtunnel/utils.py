import logging
import os
import random
import string
import sys

DEFAULT_LOGLEVEL = logging.ERROR


def check_host(host):
    assert isinstance(host, str), f"IP is not a string ({type(host).__name__})"


def check_port(port):
    assert isinstance(port, int), "PORT is not a number"
    assert port >= 0, f"PORT < 0 ({port})"


def check_address(address):
    """
    Check if the format of the address is correct

    Arguments:
        address (tuple):
            (``str``, ``int``) representing an IP address and port,
            respectively

            .. note::
                alternatively a local ``address`` can be a ``str`` when working
                with UNIX domain sockets, if supported by the platform
    Raises:
        ValueError:
            raised when address has an incorrect format

    Example:
        >>> check_address(('127.0.0.1', 22))
    """
    if isinstance(address, tuple):
        check_host(address[0])
        check_port(address[1])
    elif isinstance(address, str):
        if not (
            os.path.exists(address) or os.access(os.path.dirname(address), os.W_OK)
        ):
            raise ValueError(f"ADDRESS not a valid socket domain socket ({address})")
    else:
        raise ValueError(
            "ADDRESS is not a tuple, string, or character buffer "
            f"({type(address).__name__})"
        )


def check_addresses(address_list, is_remote=False):
    """
    Check if the format of the addresses is correct

    Arguments:
        address_list (list[tuple]):
            Sequence of (``str``, ``int``) pairs, each representing an IP
            address and port respectively

            .. note::
                when supported by the platform, one or more of the elements in
                the list can be of type ``str``, representing a valid UNIX
                domain socket

        is_remote (boolean):
            Whether or not the address list
    Raises:
        AssertionError:
            raised when ``address_list`` contains an invalid element
        ValueError:
            raised when any address in the list has an incorrect format

    Example:

        >>> check_addresses([('127.0.0.1', 22), ('127.0.0.1', 2222)])
    """
    assert all(isinstance(x, (tuple, str)) for x in address_list)

    if is_remote and any(isinstance(x, str) for x in address_list):
        raise AssertionError("UNIX domain sockets not allowed for remote" "addresses")

    for address in address_list:
        check_address(address)


def create_logger(
    logger=None, loglevel=None, capture_warnings=True, add_paramiko_handler=True
):
    """
    Attach or create a new logger and add a console handler if not present

    Arguments:

        logger (Optional[logging.Logger]):
            :class:`logging.Logger` instance; a new one is created if this
            argument is empty

        loglevel (Optional[str or int]):
            :class:`logging.Logger`'s level, either as a string (i.e.
            ``ERROR``) or in numeric format (10 == ``DEBUG``)

            .. note:: a value of 1 == ``TRACE`` enables Tracing mode

        capture_warnings (boolean):
            Enable/disable capturing the events logged by the warnings module
            into ``logger``'s handlers

            Default: True

            .. note:: ignored in python 2.6

        add_paramiko_handler (boolean):
            Whether or not add a console handler for ``paramiko.transport``'s
            logger if no handler present

            Default: True
    Return:
        :class:`logging.Logger`
    """
    logger = logger or logging.getLogger("sshtunnel.SSHTunnelForwarder")

    if not any(isinstance(x, logging.Handler) for x in logger.handlers):
        logger.setLevel(loglevel or DEFAULT_LOGLEVEL)
        console_handler = logging.StreamHandler()

        _add_handler(
            logger, handler=console_handler, loglevel=loglevel or DEFAULT_LOGLEVEL
        )

    if loglevel:  # override if loglevel was set
        logger.setLevel(loglevel)

        for handler in logger.handlers:
            handler.setLevel(loglevel)

    if add_paramiko_handler:
        _check_paramiko_handlers(logger=logger)

    if capture_warnings and sys.version_info >= (2, 7):
        logging.captureWarnings(True)
        pywarnings = logging.getLogger("py.warnings")

        pywarnings.handlers.extend(logger.handlers)

    return logger


def _add_handler(
    logger: logging.Logger, handler: logging.Handler, loglevel: int | str | None = None
):
    """
    Add a handler to an existing logging.Logger object
    """

    handler.setLevel(loglevel or DEFAULT_LOGLEVEL)

    if handler.level <= logging.DEBUG:
        handler.setFormatter(
            logging.Formatter(
                fmt=(
                    "%(asctime)s| %(levelname)-4.3s|%(threadName)10.9s/"
                    "%(lineno)04d@%(module)-10.9s| %(message)s"
                )
            )
        )
    else:
        handler.setFormatter(
            logging.Formatter(fmt="%(asctime)s| %(levelname)-8s| %(message)s")
        )

    logger.addHandler(handler)


def _check_paramiko_handlers(logger=None):
    """
    Add a console handler for paramiko.transport's logger if not present
    """
    paramiko_logger = logging.getLogger("paramiko.transport")

    if not paramiko_logger.handlers:
        if logger:
            paramiko_logger.handlers = logger.handlers
        else:
            console_handler = logging.StreamHandler()

            console_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s | %(levelname)-8s| PARAMIKO: "
                    "%(lineno)03d@%(module)-10s| %(message)s"
                )
            )
            paramiko_logger.addHandler(console_handler)


def address_to_str(address):
    if isinstance(address, tuple):
        return f"{address[0]}:{address[1]}"
    return str(address)


def remove_none_values(dictionary):
    """Remove dictionary keys whose value is None"""
    return list(map(dictionary.pop, [i for i in dictionary if dictionary[i] is None]))


def generate_random_string(length):
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for _ in range(length))
