import base64
from typing import Any

import cloudpickle


class FaasParser:
    """
    This class is responsible for serializing the functions that will be offloaded
    and deserializing the results that will be returned from the serverless runtime.
    """

    def __init__(self):
        pass

    def serialize(self, input: Any) -> str:
        # For now clear the __global__ attribute to avoid sending global namespace info
        # TODO: Implement a dependency analyzer to send the required imports
        if hasattr(input, "__globals__"):
            input.__globals__.clear()
        # Cloudpickle it
        blob_cp = cloudpickle.dumps(input)
        # Encode it in base64 and return it in an utf-8 string
        blob_b64 = base64.b64encode(blob_cp)
        return blob_b64.decode("utf-8")

    def deserialize(self, input: str) -> Any:
        # Decode it from base64
        b64_bytes = base64.b64decode(input)
        # Cloudpickle it
        return cloudpickle.loads(b64_bytes)
