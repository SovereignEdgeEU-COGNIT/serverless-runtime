from pydantic import BaseModel


class upload_file_info(BaseModel):
    src: str
    dst: str
    sql_op: list[str]
