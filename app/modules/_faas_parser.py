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

    def deserialize_pb(self, input: str) -> Any:
        # Decode it from base64
        b64_bytes = base64.b64decode(input)
        # Cloudpickle it
        return b64_bytes

    def deserialize(self, input: str) -> Any:
        # Decode it from base64
        b64_bytes = base64.b64decode(input)
        # Cloudpickle it
        return cloudpickle.loads(b64_bytes)

    def b64_to_str(self, input: str) -> Any:
        # Decode it from base64
        decoded_str = base64.b64decode(input).decode()
        return decoded_str

    def any_to_b64(self, input: Any) -> str:
        # Encode it to base64
        encoded_str = base64.b64encode(input).decode("utf-8")
        return encoded_str
