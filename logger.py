import logging
from pathlib import Path
from typing import Literal

PACKAGE: str = __package__  # type: ignore


class TestFilter(logging.Filter):
    """Test filter that can be applied to handlers"""

    def filter(self, record):
        return not record.getMessage().startswith("parsing")


def set_console_handler_formatter(handler: logging.Handler):
    """
    Automatically trigger a more or less verbose output format, depending on the given
    handler's level.

    Args:
        handler (Handler)
    """
    if handler.level <= logging.DEBUG:
        console_format = logging.Formatter(
            "%(levelname)s %(name)s %(funcName)s(): %(message)s"
        )
    else:
        console_format = logging.Formatter(f"{PACKAGE} %(levelname)s: %(message)s")
    handler.setFormatter(fmt=console_format)


def get_logfile(make: bool = False) -> Path:
    """
    Returns the path to a log file. Creates parent folders if desired.

    Args:
        make (bool): Create parent folders

    Returns:
        Path: Logfile path
    """
    log_dir = Path.home() / ".local" / "share" / PACKAGE
    if make:
        log_dir.mkdir(parents=True, exist_ok=True)
    return Path(log_dir, f"{PACKAGE}.log").resolve()


def get_logger(name: str = PACKAGE) -> logging.Logger:
    """
    Returns existing logger or creates a new one, ensuring standard handlers
    and formats.

    Args:
        name (str): Logger name, module name by default

    Returns:
        Logger
    """
    # Get or create a new logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Don't pass messages to handlers of ancestor loggers, avoid duplication
    logger.propagate = False

    # Stream output (console)
    if "console" not in [h.name for h in logger.handlers]:
        console_handler = logging.StreamHandler()
        logger.addHandler(hdlr=console_handler)
        console_handler.set_name(name="console")
        set_console_handler_formatter(handler=console_handler)

        try:
            console_handler.setLevel(level=logging.INFO)
        except ValueError:
            print("Failed to set console log level")

    # File output
    if "logfile" not in [h.name for h in logger.handlers]:
        logfile_format = logging.Formatter(
            "%(asctime)s: %(name)s %(levelname)s - %(message)s"
        )
        logfile_handler = logging.FileHandler(get_logfile(make=True))
        logger.addHandler(hdlr=logfile_handler)
        logfile_handler.set_name(name="logfile")
        logfile_handler.setFormatter(fmt=logfile_format)
        try:
            logfile_handler.setLevel(level=logging.WARNING)
        except ValueError:
            print("Failed to set logfile log level")

    return logger


# Create a logger for all functions to be defined from here on out
log = get_logger(PACKAGE)


def set_console_filter(
    filter_string: str = "",
    logger_name: str = PACKAGE,
):
    """
    Set a lambda filter function for the console logger.

    Args:
        filter_string (str): String for
        logger_name (str): Logger name, should be package name
    """
    for logger in logging.Logger.manager.loggerDict.keys():

        # Skip loggers not originating from this package
        if not logger.startswith(logger_name):
            continue

        logger_short_name = logger.removeprefix(f"{logger_name}.")

        # Find console logger handler
        for handler in logging.getLogger(name=logger).handlers:

            # Apply filter only to console logger handler
            if handler.name != "console":
                continue

            # Remove all existing filters
            for filter in handler.filters:
                handler.removeFilter(filter=filter)
                log.debug(
                    f"Removed console handler filter for logger {logger_short_name}"
                )

            if filter_string:
                log.debug(
                    "Set filter for console handler of logger "
                    f"{logger_short_name} to {filter_string}"
                )
                # handler.addFilter(lambda r: filter in r.msg)
                filter = logging.Filter(name=filter_string)
                handler.addFilter(filter=filter)
                # handler.addFilter(TestFilter())

    if filter_string:
        log.info(f"Set filter for all console logger handlers to {filter_string}")
    else:
        log.info("Removed filter for all console logger handlers")


def set_handler_levels(
    handler_name: Literal["console", "logfile"] = "console",
    level: int = logging.INFO,
    logger_name: str = PACKAGE,
):
    """
    Sets logging handler levels based on name.

    Args:
        name (str): Handler name in:
            console
            logfile
        level (int): Logging level
            10: DEBUG
            20: INFO
            30: WARN
            40: ERROR
            50: CRITICAL
        logger_name (str): Logger name, should be package name
    """
    for logger in logging.Logger.manager.loggerDict.keys():
        if logger.startswith(logger_name):
            for handler in logging.getLogger(name=logger).handlers:
                if handler.name == handler_name:
                    handler.setLevel(level=level)
                    log.debug(
                        "Set {0} - {1} logging level to {2}".format(
                            logger, handler_name, logging.getLevelName(level=level)
                        )
                    )
                    if handler.name == "console":
                        set_console_handler_formatter(handler=handler)

    log.info(
        "Set {0} {1} logging level to {2}".format(
            logger_name, handler_name, logging.getLevelName(level=level)
        )
    )
