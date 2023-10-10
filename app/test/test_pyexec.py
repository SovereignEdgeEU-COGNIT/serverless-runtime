import base64
import logging

import cloudpickle
import pytest
from fastapi.testclient import TestClient
from main import app
from models.faas import *
from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from modules._pyexec import PyExec
from fastapi import HTTPException

client = TestClient(app)
cognit_logger = CognitLogger()
cognit_logger.set_level(logging.DEBUG)
parser = FaasParser()


def myfunction(a, b):
    return a + b


def test_ok_result():
    print("Python executor test")

    param_list = []
    param_list.append(2)
    param_list.append(3)

    py_executor = PyExec(fc=myfunction, params=param_list)

    py_executor.run()
    b64_res = parser.serialize(py_executor.get_result())

    cognit_logger.debug(f"Result: {b64_res}")
    assert b64_res == parser.serialize(5)


def test_error_func():
    print("Python function error test")

    t_fc = base64.b64encode(cloudpickle.dumps(myfunction)).decode("utf-8")

    with pytest.raises((HTTPException)) as e_info:
        py_executor = PyExec(fc=t_fc, params=[2, 3])
        py_executor.run()
        b64_res = parser.serialize(py_executor.get_result())

    cognit_logger.debug(e_info.value)
    assert e_info.type is HTTPException


def test_error_param_type():
    print("Python parameter error test")

    with pytest.raises((HTTPException)) as e_info:
        py_executor = PyExec(fc=myfunction, params=2)
        py_executor.run()
        b64_res = parser.serialize(py_executor.get_result())

    cognit_logger.debug(e_info.value)
    assert e_info.type is HTTPException


def test_error_param_number():
    print("Python parameter error test")

    with pytest.raises((HTTPException)) as e_info:
        py_executor = PyExec(fc=myfunction, params=[2])
        py_executor.run()
        b64_res = parser.serialize(py_executor.get_result())

    cognit_logger.debug(e_info.value)
    assert e_info.type is HTTPException
