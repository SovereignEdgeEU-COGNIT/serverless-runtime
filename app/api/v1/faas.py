from typing import Any, Tuple
import time, re, socket
from ipaddress import ip_address as ipadd, IPv4Address, IPv6Address
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from . import nano_pb2
from google.protobuf.json_format import Parse, MessageToJson
import json#import random

from fastapi import APIRouter, HTTPException, Response, Body
from models.faas import *
from modules._cexec import CExec
from modules._faas_manager import FaasManager, TaskState
from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from modules._pyexec import PyExec #, start_pyexec_time, end_pyexec_time
from .daas import func_list
import modules._pyexec as p
import logging, os

cognit_logger = CognitLogger()
cognit_logger.set_level(logging.DEBUG)

faas_manager = FaasManager()
faas_router = APIRouter()
cognit_logger = CognitLogger()
faas_parser = FaasParser()

global app_req_id

def deserialize_py_fc(input_fc: ExecSyncParams | ExecAsyncParams) -> Tuple[Any, Any]:
    decoded_fc = faas_parser.deserialize(input_fc.fc)
    decoded_params = [faas_parser.deserialize(p) for p in input_fc.params]
    return decoded_fc, decoded_params

def get_vmid():
    with open("/var/run/one-context/one_env", "r") as file_one:
    #with open("/tmp/one_env", "r") as file_one:
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
    def __init__(self):
        pass

    def collect(self):
        vmid = get_vmid()
        if 'off_func' in globals():
            self.fc_hash = off_func.fc_hash
        else:
            self.fc_hash = "000-000-000"
        if 'sync_start_time' in globals():
            self.s_st_t = time.ctime(sync_start_time)
        else:
            self.s_st_t = "0"
        if 'sync_end_time' in globals():
            self.s_end_t = time.ctime(sync_end_time)
        else:
            self.s_end_t = "0"
        labels = ['vm_id', 'func_type', 'func_hash', 'start_time', 'end_time', 'requirement_id']
        if 'params_prom_label' in globals():
            for i in range(len(params_prom_label)):
                labels.append(f'param_l_{i}')

        # Define sync metric labels 
        gauge = GaugeMetricFamily("func_exec_time", f'Function execution time (in seconds) within VM_ID: {vmid}', labels=labels)
        if 'async_end_time' in globals() and isinstance(async_end_time, float):
            # Define variables for setting async labels
            self.exec_async_time = async_end_time - async_start_time
            self.a_st_t = time.ctime(async_start_time)
            self.a_end_t = time.ctime(async_end_time)
            # Add async metric
            metric_label_values = [vmid, "async", self.fc_hash, self.a_st_t, self.a_end_t, app_req_id]
            if 'params_prom_label' in globals():
                for i in range(len(params_prom_label)):
                    metric_label_values.append(str(params_prom_label[i]))

            gauge.add_metric(metric_label_values, self.exec_async_time)
            yield gauge 
        elif 'sync_end_time' in globals() and isinstance(sync_end_time, float) and\
            'sync_start_time' in globals() and isinstance(sync_start_time, float):
            # Define variables for setting sync labels    
            self.exec_time = sync_end_time - sync_start_time
            # Add sync metric
            metric_label_values = [vmid, "sync", self.fc_hash, self.s_st_t, self.s_end_t, app_req_id]
            if 'params_prom_label' in globals():
                for i in range(len(params_prom_label)):
                    metric_label_values.append(str(params_prom_label[i]))

            gauge.add_metric(metric_label_values, self.exec_time)
            yield gauge
        else:    
            self.exec_time = 0.0
            self.exec_async_time = 0.0

# POST /v1/faas/execute-sync
@faas_router.post("/execute-sync")
async def execute_sync(offloaded_func: ExecSyncParams):
    executor = None
    # Validate and deserialize the request based on the language
    if offloaded_func.lang == "PY":
        try:
            global app_req_id
            app_req_id = str(offloaded_func.app_req_id)
            fc, params = deserialize_py_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing sync PY function. More details; {0}".format(e))
        if not callable(fc):
            raise HTTPException(status_code=400, detail=" Not callable function")

        executor = PyExec(fc=fc, params=params)

    elif offloaded_func.lang == "C":
        try:
            fc, params = deserialize_c_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing sync C function. More details; {0}".format(e))
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
    
    if 'params' in locals():
        global params_prom_label
        params_prom_label = [params[i].__sizeof__() for i in range(len(params))]
        params_prom_label.insert(0,params.__sizeof__())

    # Define sync metric exposure global variables
    global sync_start_time
    global sync_end_time
    # Switch to not async mode for Prometheus metrics
    if 'async_end_time' in globals():
        global async_end_time
        del async_end_time

    # Once the executor is created, run it and get the result blocking the thread
    executor.run()
    sync_start_time = executor.start_pyexec_time
    sync_end_time = executor.end_pyexec_time

    if offloaded_func.lang == "PY":
        b64_res = faas_parser.serialize(executor.get_result())
    if offloaded_func.lang == "C":
        b64_res = faas_parser.any_to_b64(executor.get_result())
        
    result = ExecResponse(res=b64_res, ret_code=executor.get_ret_code(), err= executor.get_err())

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
            raise HTTPException(status_code=400, detail="Error deserializing async PY function. More details; {0}".format(e))
        if not callable(fc):
            raise HTTPException(status_code=400, detail=" Not callable function")

        executor = PyExec(fc=fc, params=params)
        
    elif offloaded_func.lang == "C":
        try:
            fc, params = deserialize_c_fc(offloaded_func)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Error deserializing async C function. More details; {0}".format(e))
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

    task_id = faas_manager.add_task(executor=executor)
    
    if 'params' in locals():
        global params_prom_label
        params_prom_label = [params[i].__sizeof__() for i in range(len(params))]
        params_prom_label.insert(0,params.__sizeof__())

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

    status, executor = task

    if status == TaskState.OK:
        if executor.lang == "PY":
            exec_response = ExecResponse(
                ret_code=ExecReturnCode.SUCCESS, res=faas_parser.serialize(executor.res)
            )
        elif executor.lang == "C":
            exec_response = ExecResponse(
                ret_code=ExecReturnCode.SUCCESS, res=faas_parser.any_to_b64(executor.res)
            )

        # Define async metrics global variables
        global async_start_time
        global async_end_time
        # And get the values from task's executor
        async_start_time = executor.start_pyexec_time
        async_end_time = executor.end_pyexec_time
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

def parse_params(faas_request):
    args = []
    for param in faas_request.params:
        if param.WhichOneof('param') == 'my_double':
            values = param.my_double.values
        elif param.WhichOneof('param') == 'my_float':
            values = param.my_float.values
        elif param.WhichOneof('param') == 'my_int32':
            values = param.my_int32.values
        elif param.WhichOneof('param') == 'my_int64':
            values = param.my_int64.values
        elif param.WhichOneof('param') == 'my_uint32':
            values = param.my_uint32.values
        elif param.WhichOneof('param') == 'my_uint64':
            values = param.my_uint64.values
        elif param.WhichOneof('param') == 'my_sint32':
            values = param.my_sint32.values
        elif param.WhichOneof('param') == 'my_sint64':
            values = param.my_sint64.values
        elif param.WhichOneof('param') == 'my_fixed32':
            values = param.my_fixed32.values
        elif param.WhichOneof('param') == 'my_fixed64':
            values = param.my_fixed64.values
        elif param.WhichOneof('param') == 'my_sfixed32':
            values = param.my_sfixed32.values
        elif param.WhichOneof('param') == 'my_sfixed64':
            values = param.my_sfixed64.values
        elif param.WhichOneof('param') == 'my_bool':
            values = param.my_bool.values
        elif param.WhichOneof('param') == 'my_string':
            values = [param.my_string]
        else:
            values = []

        # Añadimos valores al vector args
        args.append(values if len(values) > 1 else values[0])
    
    return args

def parse_result(result):
    # Construct a FaasResponse object and respond
    faas_response = nano_pb2.FaasResponse()
    response_param = faas_response.res

    # Determine the type of result and assign it appropriately
    if isinstance(result, float):
        response_param.my_float.values.extend([result])
    elif isinstance(result, int):
        response_param.my_int32.values.extend([result])  # Assuming 32-bit int, change to my_int64 for larger values
    elif isinstance(result, bool):
        response_param.my_bool.values.extend([result])
    elif isinstance(result, list):
        if all(isinstance(x, float) for x in result):
            response_param.my_double.values.extend(result)
        elif all(isinstance(x, int) for x in result):
            response_param.my_int32.values.extend(result)  # Adjust type as needed
        else:
            return "Unsupported list type", 400
    elif isinstance(result, str):
        response_param.my_string = result
    else:
        return "Unsupported return type", 400
    
    return faas_response

#POST /v1/faas/c/faas_request
@faas_router.post("/c/faas_request")
def faas_request(data: bytes = Body(..., media_type="application/octet-stream")):
    global func_list
    print(f"Bytes recibidos: {data.hex()}")  # Muestra los datos binarios

    cognit_logger.debug("Parsing FaaS request...")
    # Parse request body to FaasRequest objeto 
    faas_request = nano_pb2.FaasRequest()
    faas_request.ParseFromString(data)

    
    # Parse params
    args = parse_params(faas_request)
    
    my_bytes = faas_request.my_bytes
    if len(my_bytes) > 0:
        args.insert(faas_request.bytes_pos, my_bytes)
    cognit_logger.debug("Looking for function with ID: " + str(faas_request.fc_id))
    # Find corresponding function in global list
    target_func = next((func for func in func_list if func.fc_id == faas_request.fc_id), None)
    if not target_func:
        return "Function not found", 404

    # Call function with arguments
    func_name = target_func.fc_name
    cognit_logger.debug("Function found! Name: " + func_name)
    
    cognit_logger.debug("Importing function code...")
    # Execute code to import the function to global dictionary
    exec(target_func.fc_code, globals())
    
    cognit_logger.debug("Executing Function " + func_name + "with arguments " + str(args))
    result = globals()[func_name](*args)
    cognit_logger.debug("Result: " + str(result))
    
    cognit_logger.debug("Serializing result...")
    #Parse result
    faas_response = parse_result(result)
    
    return Response(content=faas_response.SerializeToString(), media_type="application/octet-stream")

