from typing import Any, Callable, Optional

from fastapi import HTTPException
from models.faas import *
from modules._executor import *
from modules._logger import CognitLogger

cognit_logger = CognitLogger()

import time


class PyExec(Executor):
    STATUS_DICT = {
        "RUNNING": 1,
        "IDLE": 0
    }
    
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
        
        self.status = None
        self.executed_func_counter = 0
        self.successed_func_counter = 0
        self.failed_func_counter = 0

    def run(self):
        try:
            self.executed_func_counter +=1
            self.start_pyexec_time = time.time()
            self.status = self.STATUS_DICT.get("RUNNING", 1)
            
            cognit_logger.info("Starting the task ...")
            self.res = self.fc(*self.params)
            cognit_logger.info("Done task...")
            self.end_pyexec_time = time.time()
            self.ret_code = ExecReturnCode.SUCCESS
            self.successed_func_counter += 1
            self.err = None
            return self
        except Exception as e:
            cognit_logger.info(e)
            self.failed_func_counter += 1
            self.status = self.STATUS_DICT.get("IDLE", 0)
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
    
    def get_status(self):
        return self.status
    
    def get_executed_func_counter(self):
        return self.executed_func_counter
    
    def get_successed_func_counter(self):
        return self.successed_func_counter
    
    def get_failed_func_counter(self):
        return self.failed_func_counter