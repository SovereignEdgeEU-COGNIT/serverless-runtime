from enum import Enum
from typing import Any, Optional

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
    fc_hash: str = Field(
        default="",
        description="Hash of the function to be offloaded",
    )
    params: list[str] = Field(
        default="",
        description="List containing the serialized parameters by each device runtime transfered to the offloaded function",
    )
    app_req_id: int = Field(
        default=0,
        description="Requirement ID taht belongs to current function",
    )

class ExecutionMode(str, Enum):
    SYNC = "sync"


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
