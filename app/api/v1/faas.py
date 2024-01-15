from typing import Any, Tuple
import time, re, socket
from ipaddress import ip_address as ipadd, IPv4Address, IPv6Address
from prometheus_client.core import GaugeMetricFamily, REGISTRY
#import random

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

def get_vmid():
    #with open("/var/run/one-context/one_env", "r") as file_one:
    with open("/tmp/one_env", "r") as file_one:
        patt = "VMID="
        for l in file_one:
            if re.search(patt, l):
                vmid = l.split("=")[1].replace("\"","")
                try:
                    if 'old_vmid' in locals() and vmid != old_vmid:
                        return "-1"
                    if 'old_vmid' in locals() and vmid == old_vmid:
                        vmid = vmid.replace("\n","")
                        return vmid
                    old_vmid = vmid
                except Exception as e:
                    cognit_logger.debug(f'Error while getting VM ID: {e}')


def deserialize_c_fc(input_fc: ExecSyncParams | ExecAsyncParams) -> Tuple[Any, Any]:
    # Function is deserialized
    decoded_fc = faas_parser.b64_to_str(input_fc.fc)
    decoded_params = [faas_parser.b64_to_str(param) for param in input_fc.params]
    return decoded_fc, decoded_params

class CognitFuncExecCollector(object):
    def __init__(self): #, et, fc_hash, st_t, end_t):
        pass

    def collect(self):
        vmid = get_vmid()
        if 'off_func' in globals():
            self.fc_hash = off_func.fc_hash
        else:
            self.fc_hash = "0"
        if 'sync_start_time' in globals():
            self.s_st_t = time.ctime(sync_start_time)
        else:
            self.s_st_t = "0"
        if 'sync_end_time' in globals():
            self.s_end_t = time.ctime(sync_end_time)
        else:
            self.s_end_t = "0"
        if 'sync_end_time' in globals() and isinstance(sync_end_time, float) and\
            'sync_start_time' in globals() and isinstance(sync_start_time, float):
            self.exec_time = sync_end_time - sync_start_time
        else:    
            self.exec_time = "0"
        gauge = GaugeMetricFamily("func_exec_time", f'Function execution timei within VM_ID: {vmid}', labels=['vm_id', 'func_hash', 'start_time', 'end_time'])
        gauge.add_metric([vmid, self.fc_hash, self.s_st_t, self.s_end_t], self.exec_time)
        yield gauge

class RandomNumberCollector(object):
    def __init__(self):
        pass
    def collect(self):
        gauge = GaugeMetricFamily("random_number", "A random number generator, I have no better idea", labels=["randomNum"])
        gauge.add_metric(['random_num'], random.randint(1, 20))
        yield gauge

# POST /v1/faas/execute-sync
@faas_router.post("/execute-sync")
async def execute_sync(offloaded_func: ExecSyncParams):
    executor = None
    # Validate and deserialize the request based on the language
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
        executor = CExec(fc=fc, params=params)
        pass
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported language. Supported languages: PY, C"
        )
    if offloaded_func.fc_hash != "":
        cognit_logger.debug(f"Hash of function: {offloaded_func.fc_hash}")
    global off_func
    off_func = offloaded_func

    # Once the executor is created, run it and get the result blocking the thread
    global sync_start_time
    sync_start_time = time.time()
    executor.run()
    global sync_end_time
    sync_end_time = time.time()

    if offloaded_func.lang == "PY":
        b64_res = faas_parser.serialize(executor.get_result())
    if offloaded_func.lang == "C":
        b64_res = faas_parser.any_to_b64(executor.get_result())
        
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
        executor = CExec(fc=fc, params=params)
        pass
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

