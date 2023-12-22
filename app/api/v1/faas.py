from typing import Any, Tuple

from fastapi import APIRouter, HTTPException, Response
from models.faas import *
from modules._cexec import CExec
from modules._faas_manager import FaasManager, TaskState
from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from modules._pyexec import PyExec

faas_manager = FaasManager()
faas_router = APIRouter()
cognit_logger = CognitLogger()
faas_parser = FaasParser()


def deserialize_py_fc(input_fc: ExecSyncParams | ExecAsyncParams) -> Tuple[Any, Any]:
    decoded_fc = faas_parser.deserialize(input_fc.fc)
    decoded_params = [faas_parser.deserialize(p) for p in input_fc.params]
    return decoded_fc, decoded_params


def deserialize_c_fc(input_fc: ExecSyncParams | ExecAsyncParams) -> Tuple[Any, Any]:
    # TODO: Apply specific C deserialization
    decoded_fc = faas_parser.deserialize(input_fc.fc)
    decoded_params = [faas_parser.deserialize(p) for p in input_fc.params]
    return decoded_fc, decoded_params


# POST /v1/faas/execute-sync
@faas_router.post("/execute-sync")
async def execute_sync(offloaded_func: ExecSyncParams):
    executor = None
    # Validate and deserialize the reuquest based on the language
    if offloaded_func.lang == "PY":
        try:
            fc, params = deserialize_py_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing function")
        if not callable(fc):
            raise HTTPException(status_code=400, detail=" Not callable function")

        executor = PyExec(fc=fc, params=params)

    elif offloaded_func.lang == "C":
        try:
            fc, params = deserialize_c_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing function")
        executor = CExec()
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported language. Supported languages: PY, C"
        )
    if offloaded_func.fc_hash != "":
        cognit_logger.debug(f"Hash of function: {offloaded_func.fc_hash}")

    # Once the executor is created, run it and get the result blocking the thread
    executor.run()
    b64_res = faas_parser.serialize(executor.get_result())
    result = ExecResponse(res=b64_res, ret_code=ExecReturnCode.SUCCESS)

    cognit_logger.debug(f"Result: {result}")

    return result.dict()


# POST /v1/faas/execute-async
@faas_router.post("/execute-async")
async def execute_async(offloaded_func: ExecAsyncParams, response: Response):
    executor = None
    # Validate and deserialize the reuquest based on the language
    if offloaded_func.lang == "PY":
        try:
            fc, params = deserialize_py_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing function")
        if not callable(fc):
            raise HTTPException(status_code=400, detail=" Not callable function")

        executor = PyExec(fc=fc, params=params)

    elif offloaded_func.lang == "C":
        try:
            fc, params = deserialize_c_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing function")
        executor = CExec()
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported language. Supported languages: PY, C"
        )

    if offloaded_func.fc_hash != "":
        cognit_logger.debug(f"Hash of function: {offloaded_func.fc_hash}")

    task_id = faas_manager.add_task(executor=executor)

    return AsyncExecResponse(
        status=AsyncExecStatus.WORKING,
        res=None,
        exec_id=AsyncExecId(faas_task_uuid=task_id),
    ).dict()


# GET /v1/faas/{faas_uuid}/status
@faas_router.get("/{faas_task_uuid}/status")
async def get_faas_uuid_status(faas_task_uuid: str):
    task = faas_manager.get_task_status(task_uuid=faas_task_uuid)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    status, result = task

    if status == TaskState.OK:
        exec_response = ExecResponse(
            ret_code=ExecReturnCode.SUCCESS, res=faas_parser.serialize(result)
        )
        response = AsyncExecResponse(
            status=AsyncExecStatus.READY,
            res=exec_response,
            exec_id=AsyncExecId(faas_task_uuid=faas_task_uuid),
        )
    elif status == TaskState.FAILED:
        response = AsyncExecResponse(
            status=AsyncExecStatus.FAILED,
            res=None,
            exec_id=AsyncExecId(faas_task_uuid=faas_task_uuid),
        )
    else:
        response = AsyncExecResponse(
            status=AsyncExecStatus.WORKING,
            res=None,
            exec_id=AsyncExecId(faas_task_uuid=faas_task_uuid),
        )

    return response.dict()
