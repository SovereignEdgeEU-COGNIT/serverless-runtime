import logging
import sys

import pytest
from pytest_mock import MockerFixture

sys.path.append("..")

from api.v1.faas import *
from models.faas import *
from modules._cexec import *
from modules._faas_parser import FaasParser

faas_parser = FaasParser()


# To run it: pytest --log-cli-level=DEBUG -s test_cexec.py
def test_gen_func_call(
    mocker: MockerFixture,
):
    # This is the decoded function call
    # {
    #     "lang": "C",
    #     "fc": "'#include <stdio.h>\nvoid sum(int a, int b, float *c){*c = a + b;}\nfloat c;\nsum(3, 4, &c);\nc'"
    #     "params": [
    #         {
    #         "type": "int",
    #         "var_name": "a",
    #         "value": "Mw==", #3
    #         "mode": "IN"
    #         },
    #         {
    #         "type": "int",
    #         "var_name": "b",
    #         "value": "NA==", # 4
    #         "mode": "IN"
    #         },
    #         {
    #         "type": "float",
    #         "var_name": "c",
    #         "mode": "OUT"
    #         }
    #     ]
    # }

    req = {
        "lang": "C",
        "fc": "I2luY2x1ZGUgPHN0ZGlvLmg+IAp2b2lkIHN1bWEgKGludCBhLCBpbnQgYiwgZmxvYXQgKmMpCnsKKmMgPSBhICtiOwp9",
        "params": [
            "ewogICAgInR5cGUiOiAiaW50IiwKICAgICJ2YXJfbmFtZSI6ICJhIiwKICAgICJ2YWx1ZSI6ICJNdz09IiwKICAgICJtb2RlIjogIklOIgogICAgfQ==",
            "ewogICAgInR5cGUiOiAiaW50IiwKICAgICJ2YXJfbmFtZSI6ICJiIiwKICAgICJ2YWx1ZSI6ICJOQT09IiwKICAgICJtb2RlIjogIklOIgogICAgfQ==",
            "ewogICAgInR5cGUiOiAiZmxvYXQiLAogICAgInZhcl9uYW1lIjogImMiLAogICAgIm1vZGUiOiAiT1VUIgogICAgfQ==",
        ],
    }

    decoded_params = [faas_parser.b64_to_str(param) for param in req["params"]]
    executor = CExec(fc=faas_parser.b64_to_str(req["fc"]), params=decoded_params)

    # Mock the cling subprocess call to avoid installing it to run this test
    mock_process = mocker.Mock()
    #  mock communicate fd to return (7, None ) tuple
    mock_process.communicate.return_value = ("7", None)
    mocker.patch("subprocess.Popen", return_value=mock_process)

    executor.run()

    result = executor.get_result()

    assert result == (4 + 3)
