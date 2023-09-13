from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExecSyncParams(BaseModel):
    lang: str = Field(
        default="",
        description="Language of the offloaded function",
    )
    fc: str = Field(
        default="",
        description="Function to be offloaded",
    )
    params: list[str] = Field(
        default="",
        description="List containing the serialized parameters by each device runtime transfered to the offloaded function",
    )


class ExecAsyncParams(BaseModel):
    lang: str = Field(
        default="",
        description="Language of the offloaded function",
    )
    fc: str = Field(
        default="",
        description="Function to be offloaded",
    )
    params: list[str] = Field(
        default="",
        description="List containing the serialized parameters by each device runtime transfered to the offloaded function",
    )


class FaasUuidStatus(BaseModel):
    state: str = Field(
        default="",
        description="Status of the offloaded function processing task",
    )
    result: str | None = Field(
        default=None,
        description="Result of the offloaded function",
    )


class ExecReturnCode(Enum):
    SUCCESS = 0
    ERROR = -1


class ExecResponse(BaseModel):
    ret_code: ExecReturnCode = Field(
        default=ExecReturnCode.SUCCESS,
        description="Offloaded function execution result (0 if finished successfully, 1 if not)",
    )
    res: str | None = Field(
        default=None,
        description="Result of the offloaded function",
    )
    err: str | None = Field(
        default=None,
        description="Offloaded function execution error description",
    )


class AsyncExecId(BaseModel):
    faas_task_uuid: str = Field(
        default="",
        description="UUID of the offloaded function processing task",
    )


class AsyncExecStatus(Enum):
    WORKING = "WORKING"
    READY = "READY"


class AsyncExecResponse(BaseModel):
    status: AsyncExecStatus = Field(
        default=AsyncExecStatus.WORKING,
        description="Status of the offloaded function processing task (WORKING if still executing READY if finished)",
    )
    res: Optional[ExecResponse] = Field(
        default="",
        description="Result of the offloaded function",
    )
    exec_id: AsyncExecId = Field(
        default=AsyncExecId(faas_task_uuid="000-000-000"),
        description="UUID of the offloaded function processing task",
    )
