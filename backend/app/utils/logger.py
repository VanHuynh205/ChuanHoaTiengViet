from __future__ import annotations

import logging

_DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Initialise the root logger once at process startup.

    Safe to call multiple times — ``basicConfig`` is a no-op after the first
    configuration. Library code should NOT call this; only application
    entrypoints (FastAPI lifespan, CLI ``run_cli``) should.
    """
    logging.basicConfig(level=level, format=_DEFAULT_LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
