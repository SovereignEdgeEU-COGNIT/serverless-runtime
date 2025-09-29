# Serverless Runtime example

This folders contains useful turnkey examples that may show to the first time user how to make use of the Cognit Serverless Runtime.

## Function and parameter serialization

The example function that represents the offloading function is a simple addition: `c = a + b`:

```python
def dummy_func(a, b):
    return a + b
```

In order to transfer the function and the corresponding parameters to the Serverless Runtime module, a serialization and encoding process is necessary. `cloudpickle` is used for the serialization/deserialization step. The obtained result is encoded in `base64` as an UTF-8 string. The serialized results are obtained as follows:

```python
base64.b64encode(cloudpickle.dumps(dummy_func)).decode("utf-8")
base64.b64encode(cloudpickle.dumps(a)).decode("utf-8")
base64.b64encode(cloudpickle.dumps(b)).decode("utf-8")
```

To obtain the result in plain text, we would need to revert the previous process:

```python
cloudpickle.loads(base64.b64decode(<serialized_value>))
```

## REST API requests

Once the required data is serialized, it can be sent to the Serverless Runtime in order to be executed. The examples of both synchronous and asynchronous execution calls are given next, being `a = 2` and `b = 3`.

* **Synchronous function execution:**

  `POST http://127.0.0.1:8000/v1/faas/execute-sync`

    In the POST request we need to specify the language of the offloaded function, and the serialized function and parameters, which need to be include in the request body as a json:

    ```json
    {
    "lang": "PY",
    "fc": "gAWVKwIAAAAAAACMF2Nsb3VkcGlja2xlLmNsb3VkcGlja2xllIwOX21ha2VfZnVuY3Rpb26Uk5QoaACMDV9idWlsdGluX3R5cGWUk5SMCENvZGVUeXBllIWUUpQoSwJLAEsASwJLAktDQwh8AHwBFwBTAJROhZQpjAFhlIwBYpSGlIx2L21udC9jL1VzZXJzL2dwZXJhbHRhL09uZURyaXZlIC0gSUtFUkxBTiBTLkNPT1AvUFJPWUVDVE9TL0VVUk9QRU9TL0NPR05JVC9EZXNhcnJvbGxvIFdQMy9QcnVlYmFzL3Rlc3Rfc2VyaWFsaXphdGlvbi5weZSMCm15ZnVuY3Rpb26USxJDAggBlCkpdJRSlH2UKIwLX19wYWNrYWdlX1+UTowIX19uYW1lX1+UjAhfX21haW5fX5SMCF9fZmlsZV9flGgNdU5OTnSUUpSMHGNsb3VkcGlja2xlLmNsb3VkcGlja2xlX2Zhc3SUjBJfZnVuY3Rpb25fc2V0c3RhdGWUk5RoGH2UfZQoaBRoDowMX19xdWFsbmFtZV9flGgOjA9fX2Fubm90YXRpb25zX1+UfZSMDl9fa3dkZWZhdWx0c19flE6MDF9fZGVmYXVsdHNfX5ROjApfX21vZHVsZV9flGgVjAdfX2RvY19flE6MC19fY2xvc3VyZV9flE6MF19jbG91ZHBpY2tsZV9zdWJtb2R1bGVzlF2UjAtfX2dsb2JhbHNfX5R9lHWGlIZSMC4=",
    "params": 
        [
        "gAVLAi4=",
        "gAVLAy4="
        ]
    }
    ```

    The expected response for a successful execution will be as follows:

    ```json
    {
        "ret_code": 0,
        "res": "gAVLBS4=",
        "err": null
    }
    ```

## Postman collection

A postman collection with the requests is included [here](endpoint_request_examples.json)