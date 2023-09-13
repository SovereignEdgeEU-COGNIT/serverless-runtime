from modules._executor import *
from modules._logger import CognitLogger


cognit_logger = CognitLogger()


class CExec(Executor):
    def run(self):
        cognit_logger.debug("Run C fuction")

    def get_result(self):
        cognit_logger.debug("Get C result func")
        return 5
