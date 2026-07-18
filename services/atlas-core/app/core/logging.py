import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIRECTORY = Path("/opt/atlas/logs")
LOG_FILE = LOG_DIRECTORY / "atlas-core.log"

LOG_FORMAT = (
    "%(asctime)s "
    "%(levelname)-8s "
    "%(name)s "
    "%(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
