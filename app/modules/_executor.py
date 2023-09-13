from modules._logger import CognitLogger

cognit_logger = CognitLogger()


class Executor:
    def run(self):
        cognit_logger.debug("Run base fuction")

    def get_result(self):
        cognit_logger.debug("Get base result func")
