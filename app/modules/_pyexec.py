from typing import Any, Callable, Optional

from fastapi import HTTPException
from models.faas import *
from modules._executor import *
from modules._logger import CognitLogger

cognit_logger = CognitLogger()

import time


class PyExec(Executor):
    def __init__(self, fc: Callable, params: list[str]):
        self.lang = "PY"
        self.fc = fc
        self.params = params
        self.res: Optional[float]
        self.err: str
        self.ret_code: ExecReturnCode
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
            self.ret_code = ExecReturnCode.SUCCESS
            self.err = None
            return self
        except Exception as e:
            cognit_logger.info(e)
            self.res = None
            self.end_pyexec_time = time.time()
            self.ret_code = ExecReturnCode.ERROR
            self.err = "Error executing function: " + str(e)

    def get_result(self):
        return self.res

    def get_err(self):
        return self.err
    
    def get_ret_code(self):
        return self.ret_code