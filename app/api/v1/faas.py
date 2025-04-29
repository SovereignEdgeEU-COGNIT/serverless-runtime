from typing import Any, Tuple
import time, re, socket
from ipaddress import ip_address as ipadd, IPv4Address, IPv6Address
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY, Histogram
from . import nano_pb2
from google.protobuf.json_format import Parse, MessageToJson
import json
from fastapi import APIRouter, HTTPException, Response, Body
from models.faas import *
from modules._cexec import CExec
from modules._faas_manager import FaasManager, TaskState
from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from modules._pyexec import PyExec
from modules._pyexec import PyExec #, start_pyexec_time, end_pyexec_time
import modules._pyexec as p
import logging, os
from threading import Lock
import sys

cognit_logger = CognitLogger()
cognit_logger.set_level(logging.DEBUG)

faas_manager = FaasManager()
faas_router = APIRouter()
faas_parser = FaasParser()

global app_req_id
global executor
global executor_lock  # Thread lock for executor
executor = None
executor_lock = Lock()

def deserialize_py_fc(input_fc: ExecSyncParams | ExecAsyncParams) -> Tuple[Any, Any]:
    decoded_fc = faas_parser.deserialize(input_fc.fc)
    decoded_params = [faas_parser.deserialize(p) for p in input_fc.params]
    return decoded_fc, decoded_params

def get_vmid():
    with open("/var/run/one-context/one_env", "r") as file_one:
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

# Define histograms
execution_time_histogram = Histogram(
    'sr_histogram_func_exec_time_seconds',
    'Histogram of function execution time',
    buckets=[1, 5, 10],
    labelnames=['vmid', 'function_outcome']
)

input_size_histogram = Histogram(
    'sr_histogram_func_input_size_bytes',
    'Histogram of function input size',
    buckets=[1024, 1024 * 1024, 1024 * 1024 * 1024], # KB, MB, GB
    labelnames=['vmid', 'function_outcome']
)

def update_histogram_metrics(executor, vmid, asyncExecutionSuccess=None):
    """Updates Prometheus metrics immediately after execution."""
    try:
        if asyncExecutionSuccess not in [True,False]:
            outcome = "success" if executor.get_ret_code() == ExecReturnCode.SUCCESS else "error"
        else:
            outcome = asyncExecutionSuccess

        # Record input size
        if "params_prom_label" in globals() and params_prom_label:
            input_size = sum(params_prom_label)
            cognit_logger.warning(f"Recording input size: {input_size}")
            if input_size > 0:
                input_size_histogram.labels(vmid=str(vmid), function_outcome=str(outcome)).observe(float(input_size))
            else:
                cognit_logger.warning("Warning: params_prom_label sum is zero")

        # Record execution time
        exec_time = executor.end_pyexec_time - executor.start_pyexec_time
        if isinstance(exec_time, (int, float)) and exec_time > 0:
            cognit_logger.warning(f"Recording execution time: {exec_time}")
            execution_time_histogram.labels(vmid=str(vmid), function_outcome=str(outcome)).observe(float(exec_time))
        else:
            cognit_logger.warning(f"Warning: exec_time is missing or invalid: {exec_time}")

    except Exception as e:
        cognit_logger.error(f"Error updating metrics: {e}")

def pb_serialize_result(result):
    # Construct a FaasResponse object and respond
    response_param = nano_pb2.MyParam()
    

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
    
    return response_param.SerializeToString()

def deserialize_protobuf_params(params):
    
    param = nano_pb2.MyParam()
    args = []

    for encoded_param in params:
        param_decoded = faas_parser.deserialize_pb(encoded_param)
        param.ParseFromString(param_decoded)
        
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
        elif param.WhichOneof('param') == 'my_bytes':
            values = [param.my_bytes]
        else:
            values = []

        # Añadimos valores al vector args
        args.append(values if len(values) > 1 else values[0])
    return args

def make_fc_executable(fc_str):
    # Buscar el nombre de la función con regex
    match = re.search(r"def\s+(\w+)\s*\(", fc_str)

    if match:
        fc_name = match.group(1)  # Extrae el nombre de la función
        exec(fc_str, globals())  # Ejecutar el código
        fc = globals().get(fc_name)
    
    return fc
    

def deserialize_protobuf_fc(input_fc: ExecSyncParams):
    # Parse request body to MyFunc object
    cognit_logger.debug("Parsing function data...")

    my_func = nano_pb2.MyFunc()
    decoded_fc = faas_parser.deserialize_pb(input_fc.fc)
    my_func.ParseFromString(decoded_fc)
    
    cognit_logger.debug("Function code: ")
    cognit_logger.debug(my_func.fc_code)
    
    args = deserialize_protobuf_params(input_fc.params)
    cognit_logger.debug("Args: " + str(args))
   
    # Respondemos con el mismo objeto modificado
    return make_fc_executable(my_func.fc_code), args


class CognitFuncExecCollector(object):
    def __init__(self):
        pass

    def collect(self):
        try:
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
            labels = ['vm_id', 'func_type', 'func_hash', 'start_time', 'end_time', 'requirement_id', 'total_param_size']

            # Define sync metric labels 
            gauge = GaugeMetricFamily("sr_last_func_exec_time", f'Function execution time (in seconds) within VM_ID: {vmid}', labels=labels)
            if 'async_end_time' in globals() and isinstance(async_end_time, float):
                # Define variables for setting async labels
                self.exec_async_time = async_end_time - async_start_time
                self.a_st_t = time.ctime(async_start_time)
                self.a_end_t = time.ctime(async_end_time)
                # Add async metric
                metric_label_values = [vmid, "async", self.fc_hash, self.a_st_t, self.a_end_t, app_req_id, str(sum(params_prom_label))]
                gauge.add_metric(metric_label_values, self.exec_async_time)
                yield gauge 
            elif 'sync_end_time' in globals() and isinstance(sync_end_time, float) and\
                'sync_start_time' in globals() and isinstance(sync_start_time, float):
                # Define variables for setting sync labels    
                self.exec_time = sync_end_time - sync_start_time
                # Add sync metric
                metric_label_values = [vmid, "sync", self.fc_hash, self.s_st_t, self.s_end_t, app_req_id, str(sum(params_prom_label))]
                gauge.add_metric(metric_label_values, self.exec_time)
                yield gauge
            else:    
                self.exec_time = 0.0
                self.exec_async_time = 0.0
                
            # Add metric GAUGE for function status
            func_status_labels = ['func_hash', 'vm_id', 'total_param_size']
            func_status_gauge = GaugeMetricFamily("sr_func_status", "Function execution status (RUNNING : 1.0, IDLE: 0.0)", labels=func_status_labels)
            
            global executor
            if executor is not None:
                func_status = executor.get_status()
                func_status_gauge.add_metric([off_func.fc_hash, vmid, str(sum(params_prom_label))], func_status)
                yield func_status_gauge

                # Add counters for executed, succeeded, and failed functions
                executed_counter = CounterMetricFamily("sr_func_executed_total", "Total number of executed functions", labels=['vm_id'])
                succeeded_counter = CounterMetricFamily("sr_func_succeeded_total", "Total number of succeeded functions", labels=['vm_id'])
                failed_counter = CounterMetricFamily("sr_func_failed_total", "Total number of failed functions", labels=['vm_id'])

                executed_counter.add_metric([vmid], executor.get_executed_func_counter())
                succeeded_counter.add_metric([vmid], executor.get_successed_func_counter())
                failed_counter.add_metric([vmid], executor.get_failed_func_counter())

                yield executed_counter
                yield succeeded_counter
                yield failed_counter
                
                
        except Exception as e:
            # Manually call sys.excepthook to log the exception
            sys.excepthook(type(e), e, e.__traceback__)

# POST /v1/faas/execute-sync
@faas_router.post("/execute-sync")
async def execute_sync(offloaded_func: ExecSyncParams):
    global executor
    global executor_lock
    global app_req_id

    with executor_lock:  # Ensure proper locking
        # cognit_logger.debug(f"Before execution, executor: {executor}")
        
        executor = None  # Reset executor before assignment

        if offloaded_func.lang == "PY":
            try:
                app_req_id = str(offloaded_func.app_req_id)
                fc, params = deserialize_py_fc(offloaded_func)
            except Exception as e:
                cognit_logger.error(f"Error deserializing sync PY function: {e}")
                raise HTTPException(status_code=400, detail=f"Error deserializing sync PY function: {e}")

            if not callable(fc):
                cognit_logger.error("Function is not callable")
                raise HTTPException(status_code=400, detail="Not callable function")

            executor = PyExec(fc=fc, params=params)
            cognit_logger.debug("PyExec created successfully")

        elif offloaded_func.lang == "C":
            try:
                #global app_req_id
                app_req_id = str(offloaded_func.app_req_id)
                fc, params = deserialize_protobuf_fc(offloaded_func)
            except Exception as e:
                raise HTTPException(status_code=400, detail="Error deserializing sync C function. More details; {0}".format(e))
        
        
            if not callable(fc):
                raise HTTPException(status_code=400, detail=" Not callable function")
            executor = PyExec(fc=fc, params=params)
        else:
            raise HTTPException(
                status_code=400, detail="Unsupported language. Supported languages: PY, C"
            )


        if not executor:
            cognit_logger.error("Executor is None after assignment")
            raise HTTPException(status_code=500, detail="Internal Server Error: Executor is None")

        # cognit_logger.debug(f"Executor assigned: {executor}")

        global off_func
        off_func = offloaded_func

        if 'params' in locals():
            global params_prom_label
            params_prom_label = [params[i].__sizeof__() for i in range(len(params))]
            params_prom_label.insert(0, params.__sizeof__())

        # Define sync metric exposure global variables
        global sync_start_time
        global sync_end_time

        # Switch to not async mode for Prometheus metrics
        if 'async_end_time' in globals():
            global async_end_time
            del async_end_time

        # Run executor within lock
        try:
            executor.run()
            sync_start_time = executor.start_pyexec_time
            sync_end_time = executor.end_pyexec_time
            update_histogram_metrics(executor, get_vmid())
        except Exception as e:
            cognit_logger.error(f"Unhandled exception during execution: {e}")
            raise HTTPException(status_code=500, detail=f"Execution failed: {e}")

        # Serialize result
        try:
            if offloaded_func.lang == "PY":
                b64_res = faas_parser.serialize(executor.get_result())
            if offloaded_func.lang == "C":
                b64_res = faas_parser.any_to_b64(pb_serialize_result(executor.get_result()))


            result = ExecResponse(res=b64_res, ret_code=executor.get_ret_code(), err=executor.get_err())
            cognit_logger.debug(f"Execution result: {result}")

            return result.dict()

        except Exception as e:
            cognit_logger.error(f"Error serializing response: {e}")
            raise HTTPException(status_code=500, detail=f"Error serializing response: {e}")



# POST /v1/faas/execute-async
@faas_router.post("/execute-async")
async def execute_async(offloaded_func: ExecAsyncParams, response: Response):
    global executor, executor_lock
    with executor_lock:
        # Validate and deserialize the request based on the language
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
    
    global executor, executor_lock
    with executor_lock:
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
        if status != AsyncExecStatus.WORKING:
            update_histogram_metrics(executor, get_vmid(), status==TaskState.OK)

        return response.dict()

    

