import base64
import logging
import time

import cloudpickle
import pydantic
from fastapi.testclient import TestClient
from main import app
from models.faas import *
from modules._faas_parser import FaasParser
from modules._logger import CognitLogger

client = TestClient(app)
cognit_logger = CognitLogger()
cognit_logger.set_level(logging.CRITICAL)
parser = FaasParser()


def myfunction(a, b):
    return a + b


def test_exec_sync_ok():
    cognit_logger.info("Execute-sync test")
    t_lang = "PY"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = 3

    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())
    assert response.status_code == 200
    result = response.json()
    cognit_logger.debug(f"Result: {result}")
    assert result["ret_code"] == 0
    assert result["res"] == parser.serialize(5)


def test_exec_async_ok():
    cognit_logger.info("Execute Async test")
    t_lang = "PY"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = 3

    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecAsyncParams(lang=t_lang, fc=t_fc, params=param_list)

    response = client.post("/v1/faas/execute-async", json=sync_ctx.dict())
    assert response.status_code == 200

    resp: AsyncExecResponse = pydantic.parse_obj_as(AsyncExecResponse, response.json())
    assert resp is not None

    time.sleep(1)
    response = client.get("/v1/faas/{}/status".format(resp.exec_id.faas_task_uuid))
    assert response.status_code == 200

    result: AsyncExecResponse = pydantic.parse_obj_as(
        AsyncExecResponse, response.json()
    )
    assert result is not None
    assert result.res is not None
    assert result.res.res is not None
    assert parser.deserialize(result.res.res) == 5
    assert result.res.ret_code == ExecReturnCode.SUCCESS
    print(response.json())


def test_exec_sync_http400_function_error():
    cognit_logger.info("Execute Sync: HTTP 400 - Wrong function")
    t_lang = "PY"
    t_fc = "c = a + b"
    a_param = 2
    b_param = 3
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)

    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")


def test_exec_sync_http400_params_error():
    cognit_logger.info("Execute Sync: HTTP 400 - Wrong Python params")
    t_lang = "Python"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    param_list = []
    param_list.append(2)
    param_list.append(3)

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")


def test_exec_sync_http400_language_error():
    cognit_logger.info("Execute Sync: HTTP 404 - Wrong languaje")
    t_lang = "Python"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = 3
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")


def test_exec_async_http400_function_error():
    cognit_logger.info("Execute Async: HTTP 400- Wrong function")
    t_lang = "PY"
    t_fc = "c = a + b"
    a_param = 2
    b_param = 3
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecAsyncParams(lang=t_lang, fc=t_fc, params=param_list)

    response = client.post("/v1/faas/execute-async", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")


def test_exec_async_http400_params_error():
    cognit_logger.info("Execute Sync: HTTP 400 - Wrong Python params")
    t_lang = "Python"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    param_list = []
    param_list.append(2)
    param_list.append(3)

    sync_ctx = ExecAsyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-async", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")


def test_exec_async_http400_language_error():
    cognit_logger.info("Execute Sync: HTTP 404 - Wrong languaje")
    t_lang = "Python"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = 3
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecAsyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-async", json=sync_ctx.dict())
    assert response.status_code == 400
    result = response.json()
    cognit_logger.debug(f"Response: {result}")
