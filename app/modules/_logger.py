import inspect
import logging
import os


class CognitLogger:
    LOGGER_NAME = "cognit-logger"

    def __init__(self, verbose=True):
        self.logger = logging.getLogger(self.LOGGER_NAME)
        self.verbose = verbose
        if not self.logger.hasHandlers():
            self.logger.propagate = False
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter("[%(asctime)5s] [%(levelname)-s] %(message)s")
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _log(self, level: int, message):
        if self.verbose:
            frame = inspect.stack()[2]
            filename = os.path.basename(frame.filename)
            line = frame.lineno
            self.logger.log(level, f"[{filename}::{line}] {message}")
        else:
            self.logger.log(level, message)

    def set_level(self, level: int):
        self.logger.setLevel(level)

    def debug(self, message):
        self._log(logging.DEBUG, message)
        return

    def info(self, message):
        self._log(logging.INFO, message)

    def warning(self, message):
        self._log(logging.WARNING, message)

    def error(self, message):
        self._log(logging.ERROR, message)

    def critical(self, message):
        self._log(logging.CRITICAL, message)
