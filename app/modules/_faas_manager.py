import uuid
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from dask.distributed import Client, Future
from fastapi import HTTPException
from modules._executor import Executor
from modules._logger import CognitLogger

TaskId = str

cognit_logger = CognitLogger()


class TaskState(Enum):
    WORKING = "WORKING"
    OK = "OK"
    FAILED = "FAILED"


class FaasManager:
    def __init__(self):
        # Dictionary with the proccesses (uuid, task_id)
        self.task_map: Dict[TaskId, Future] = {}
        #  dask.config.set(scheduler="threads")
        self.client = Client(processes=False)

    def add_task(self, executor: Executor) -> TaskId:
        task_uuid = str(uuid.uuid1())
        task: Future = self.client.submit(executor.run)
        self.task_map[task_uuid] = task

        return task_uuid

    # Return a tuple with the status and the result as Any
    def get_task_status(self, task_uuid: TaskId) -> Optional[Tuple[TaskState, Any]]:
        if task_uuid in self.task_map:
            if self.task_map[task_uuid].status == "pending":
                if self.task_map[task_uuid].exception() is not None:
                    cognit_logger.info(
                        "Status: {}; Error: {}".format(
                            self.task_map[task_uuid].status,
                            self.task_map[task_uuid].exception(),
                        )
                    )
                return TaskState.WORKING, None
            elif self.task_map[task_uuid].status == "finished":
                if self.task_map[task_uuid].exception() is not None:
                    cognit_logger.info(
                        "Status: {}; Error: {}".format(
                            self.task_map[task_uuid].status,
                            self.task_map[task_uuid].exception(),
                        )
                    )
                task_executor = self.task_map[task_uuid].result()
                return TaskState.OK, task_executor
            else:
                if self.task_map[task_uuid].exception() is not None:
                    cognit_logger.info(
                        "Status: {}; Error: {}".format(
                            self.task_map[task_uuid].status,
                            self.task_map[task_uuid].exception(),
                        )
                    )
                return TaskState.FAILED, None
        else:
            return None
