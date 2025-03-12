import inspect
import logging
import os
import sys

class CognitLogger:
    LOGGER_NAME = "cognit-logger"
    LOG_PATH = "/var/log/cognit"
    LOG_FILENAME = "sr-app"

    def __init__(self, verbose=True):
        self.logger = logging.getLogger(self.LOGGER_NAME)
        self.verbose = verbose
        # Make sure log path exists
        try:
            os.makedirs(self.LOG_PATH, exist_ok=True)
        except OSError as e:
            print("COGNIT logger Error: {0}".format(e))
        if not self.logger.hasHandlers():
            self.logger.propagate = False
            self.logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter("[%(asctime)5s] [%(levelname)-s] %(message)s")
            # Handle stdout output
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

            # Redirect output to log file
            fileHandler = logging.FileHandler("{0}/{1}.log".format(self.LOG_PATH, self.LOG_FILENAME))
            fileHandler.setFormatter(formatter)
            self.logger.addHandler(fileHandler)
            
        # Set global exception hook for uncaught exceptions
        sys.excepthook = self._unhandled_exception

    def _unhandled_exception(self, exc_type, exc_value, exc_traceback):
        """Handles uncaught exceptions and logs them."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self.logger.critical("Uncaught Exception", exc_info=(exc_type, exc_value, exc_traceback))

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
