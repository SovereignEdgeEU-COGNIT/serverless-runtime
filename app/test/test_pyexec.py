from modules._faas_parser import FaasParser
from modules._logger import CognitLogger
from modules._pyexec import PyExec
from models.faas import *
from main import app

from fastapi.testclient import TestClient

cognit_logger = CognitLogger()
client = TestClient(app)
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

    cognit_logger.debug(f"Result: {py_executor.get_result()}")
    assert py_executor.get_result() == 5

    # Close client
    client.close()

def test_error_func():

    print("Python function error test")

    param_list = []
    param_list.append(2)
    param_list.append("wrong_param")

    py_executor = PyExec(fc=myfunction, params=param_list)
    py_executor.run()

    cognit_logger.debug(f"Result: {py_executor.get_result()}")
    cognit_logger.debug(f"Error: {py_executor.err}")
    cognit_logger.debug(f"Return code: {py_executor.ret_code}")

    assert py_executor.get_result() == None
    assert py_executor.err is not None
    assert py_executor.ret_code == ExecReturnCode.ERROR

    # Close client
    client.close()

def test_error_param_type():

    print("Python parameter error test")

    py_executor = PyExec(fc=myfunction, params=2)
    py_executor.run()

    cognit_logger.debug(f"Result: {py_executor.get_result()}")
    cognit_logger.debug(f"Error: {py_executor.err}")
    cognit_logger.debug(f"Return code: {py_executor.ret_code}")

    assert py_executor.get_result() == None
    assert py_executor.err is not None
    assert py_executor.ret_code == ExecReturnCode.ERROR

    # Close client
    client.close()

def test_error_param_number():

    print("Python parameter error test")

    py_executor = PyExec(fc=myfunction, params=[2])
    py_executor.run()

    cognit_logger.debug(f"Result: {py_executor.get_result()}")
    cognit_logger.debug(f"Error: {py_executor.err}")
    cognit_logger.debug(f"Return code: {py_executor.ret_code}")

    assert py_executor.get_result() == None
    assert py_executor.err is not None
    assert py_executor.ret_code == ExecReturnCode.ERROR
    
    # Close client
    client.close()
