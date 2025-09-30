from modules._logger import CognitLogger
from modules._executor import *
from models.faas import *

from typing import Any, Callable, Optional
from threading import Lock
import time

cognit_logger = CognitLogger()

class PyExec(Executor):
    STATUS_DICT = {
        "RUNNING": 1,
        "IDLE": 0
    }
    
    executed_func_counter = 0
    successed_func_counter = 0
    failed_func_counter = 0
    
    _lock = Lock()

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
        
    def increase_counter(self, counter_name: str):
        """Thread-safe increment for class-level counters."""
        with self._lock:
            setattr(PyExec, counter_name, getattr(PyExec, counter_name) + 1)

    def run(self):
        """
        Run the Python function with the provided parameters.
        This method executes the function `fc` with the parameters `params`.
        """

        try:

            # Increment the class-level executed counter
            self.increase_counter("executed_func_counter")

            self.start_pyexec_time = time.time()
            self.status = self.STATUS_DICT.get("RUNNING", 1)
            
            cognit_logger.info("Starting the task ...")
            self.res = self.fc(*self.params)

            cognit_logger.info("Done task...")
            self.end_pyexec_time = time.time()
            self.ret_code = ExecReturnCode.SUCCESS

            # Increment the class-level success counter
            self.increase_counter("successed_func_counter")
            self.err = None
            self.status = self.STATUS_DICT.get("IDLE", 0)
            
            return self
        
        except Exception as e:

            cognit_logger.error(e)

            # Increment the class-level failed counter
            self.increase_counter("failed_func_counter")
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
    
    @classmethod
    def get_executed_func_counter(cls):
        return cls.executed_func_counter
    
    @classmethod
    def get_successed_func_counter(cls):
        return cls.successed_func_counter
    
    @classmethod
    def get_failed_func_counter(cls):
        return cls.failed_func_counter
