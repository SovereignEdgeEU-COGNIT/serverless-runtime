from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from models.faas import *
from main import app

from fastapi.testclient import TestClient
from unittest.mock import patch
import cloudpickle
import base64

cognit_logger = CognitLogger()
client = TestClient(app)
parser = FaasParser()

def myfunction(a: int, b: int) -> int:
    return a + b

@patch("api.v1.faas.get_vmid")
def test_exec_sync_ok(mock_get_vmid):

    cognit_logger.info("Execute Sync: OK")

    mock_get_vmid.return_value = "test_vmid"

    fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = 3

    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang="PY", fc=fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())

    assert response.status_code == 200

    result = response.json()
    cognit_logger.debug(f"Result: {result}")

    assert result["ret_code"] == 0
    assert result["res"] == parser.serialize(5)
    assert result["err"] == None

@patch("api.v1.faas.get_vmid")
def test_exec_sync_wrong_function(mock_get_vmid):

    cognit_logger.info("Execute Sync: Wrong function")

    mock_get_vmid.return_value = "test_vmid"

    t_lang = "PY"
    t_fc = "c = a + b"
    a_param = 2
    b_param = 3
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())

    assert response.status_code == 200

    result = response.json()
    cognit_logger.debug(f"Response: {result}")
    cognit_logger.debug(f"Error: {result['err']}")

    assert result["ret_code"] == ExecReturnCode.ERROR.value
    assert parser.deserialize(result["res"]) is None
    assert result["err"] != ""

@patch("api.v1.faas.get_vmid")
def test_exec_sync_wrong_params(mock_get_vmid):

    cognit_logger.info("Execute Sync: Wrong Python params")

    mock_get_vmid.return_value = "test_vmid"

    t_lang = "PY"
    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")
    a_param = 2
    b_param = "WrongParam"
    param_list = []
    param_list.append(parser.serialize(a_param))
    param_list.append(parser.serialize(b_param))

    sync_ctx = ExecSyncParams(lang=t_lang, fc=t_fc, params=param_list)
    response = client.post("/v1/faas/execute-sync", json=sync_ctx.dict())

    assert response.status_code == 200

    result = response.json()
    cognit_logger.debug(f"Response: {result}")
    cognit_logger.debug(f"Error: {result['err']}")

    assert result["ret_code"] == ExecReturnCode.ERROR.value
    assert parser.deserialize(result["res"]) is None
    assert result["err"] != ""

@patch("api.v1.faas.get_vmid")
def test_exec_sync_wrong_language(mock_get_vmid):

    cognit_logger.info("Execute Sync: Wrong language")

    mock_get_vmid.return_value = "test_vmid"

    t_lang = "WrongLanguage"
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
    cognit_logger.debug(f"Response: {result}")
    cognit_logger.debug(f"Error: {result['err']}")

    assert result["ret_code"] == ExecReturnCode.ERROR.value
    assert parser.deserialize(result["res"]) is None
    assert result["err"] != ""
