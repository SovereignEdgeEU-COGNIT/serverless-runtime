from fastapi import APIRouter, HTTPException, HTTPException, Body, Response
from models.daas import *
from modules._logger import CognitLogger
import logging
from . import nano_pb2
from google.protobuf.json_format import Parse, MessageToJson
from google.protobuf.message import DecodeError

import json
cognit_logger = CognitLogger()
cognit_logger.set_level(logging.DEBUG)

daas_router = APIRouter()

func_list = []

# POST /v1/daas/upload
@daas_router.post("/upload")
async def upload_file(file_params: upload_file_info):
    raise HTTPException(status_code=501, detail="Not implemented")

# POST /v1/daas/c/upload_fc
@daas_router.post("/c/upload_fc")
async def c_upload_func(data: bytes = Body(..., media_type="application/octet-stream")):
    cognit_logger.info("Receivend upload_fc request")
    
    # Parse request body to MyFunc object
    cognit_logger.debug("Parsing function data...")
    # Crear una instancia de MyFunc y parsear los datos binarios
    my_func = nano_pb2.MyFunc()
    my_func.ParseFromString(data)
    global func_list
    target_func = next((func for func in func_list if func.fc_hash == my_func.fc_hash), None)
    if not target_func:
        cognit_logger.debug("Function '" + my_func.fc_name + "' was uploaded!")
        # Asign ID to MyFunc object
        func_list.append(my_func)

        my_func.fc_id = len(func_list)
        cognit_logger.debug("Assigned ID: " + str(my_func.fc_id))
        
        # Append MyFunc object to global list
        cognit_logger.debug("Function code: ")
        cognit_logger.debug(my_func.fc_code)
        
        # Respondemos con el mismo objeto modificado
        return Response(content=my_func.SerializeToString(), media_type="application/octet-stream")
    else:
        cognit_logger.debug("Function " + target_func.fc_name + " already exists")
        return Response(content=target_func.SerializeToString(), media_type="application/octet-stream")