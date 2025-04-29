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

# POST /v1/daas/upload
@daas_router.post("/upload")
async def upload_file(file_params: upload_file_info):
    raise HTTPException(status_code=501, detail="Not implemented")