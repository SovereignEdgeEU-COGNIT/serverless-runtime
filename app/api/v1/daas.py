from fastapi import APIRouter, HTTPException
from models.daas import *

daas_router = APIRouter()


# POST /v1/daas/upload
@daas_router.post("/upload")
async def upload_file(file_params: upload_file_info):
    raise HTTPException(status_code=501, detail="Not implemented")
