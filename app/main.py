from api.v1.daas import daas_router
from api.v1.faas import faas_router, CognitFuncExecCollector
from fastapi import FastAPI, Response
import prometheus_client
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server, multiprocess, CollectorRegistry
import os

app = FastAPI(title="Serverless Runtime")

@app.get("/")
async def root():
    return "Main routes: \
            POST -> /v1/faas/execute-sync  \
                    /v1/faas/execute-sync \
                    /v1/daas/upload \
            GET -> /v1/faas/{faas_uuid}/status"


app.include_router(faas_router, prefix="/v1/faas")
app.include_router(daas_router, prefix="/v1/daas")

if __name__ == "__main__":
    import uvicorn
    global r

    # Create Prometheus registry
    #r = REGISTRY
    r = CollectorRegistry()
    # Register COGNIT collector within the registry
    r.register(CognitFuncExecCollector())
    #multiprocess.MultiProcessCollector(r)
    # Start Prometheus HTTP server on the desired port, for instance 9100
    start_http_server(9100, registry=r)
    # Start uvicorn server to serve COGNIT Serverless Runtime API
    uvicorn.run(app, host="0.0.0.0", port=8000)
