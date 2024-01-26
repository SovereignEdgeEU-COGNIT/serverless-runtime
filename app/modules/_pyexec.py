from typing import Any, Callable, Optional

from fastapi import HTTPException
from models.faas import *
from modules._executor import *
from modules._logger import CognitLogger

cognit_logger = CognitLogger()

import time


class PyExec(Executor):
    def __init__(self, fc: Callable, params: list[str]):
        self.fc = fc
        self.params = params
        self.res: Optional[float]
        self.process_manager: Any
        self.start_pyexec_time = 0.0
        self.end_pyexec_time = 0.1

    def run(self):
        try:
            self.start_pyexec_time = time.time()
            cognit_logger.info("Starting the task ...")
            self.res = self.fc(*self.params)
            cognit_logger.info("Done task...")
            self.end_pyexec_time = time.time()
            return self
        except Exception as e:
            cognit_logger.info(e)
            self.res = None
            self.end_pyexec_time = time.time()
            raise HTTPException(status_code=400, detail="Error executing function")

    def get_result(self):
        return self.res
