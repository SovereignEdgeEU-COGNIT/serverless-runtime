from typing import Any, Callable, Optional

from models.faas import *
from modules._executor import *
from modules._logger import CognitLogger

cognit_logger = CognitLogger()


class PyExec(Executor):
    def __init__(self, fc: Callable, params: list[str]):
        self.fc = fc
        self.params = params
        self.res: Optional[float]
        self.process_manager: Any

    def run(self):
        cognit_logger.info("Starting the task ...")
        self.res = self.fc(*self.params)
        cognit_logger.info("Done task...")
        return self.res

    def get_result(self):
        return self.res
