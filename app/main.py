from api.v1.daas import daas_router
from api.v1.faas import faas_router, CognitFuncExecCollector
from fastapi import FastAPI, Response
import prometheus_client
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server, multiprocess, CollectorRegistry
import os, socket
from ipaddress import ip_address as ipadd, IPv4Address, IPv6Address

SR_PORT = 8000
PROM_PORT = 9100

app = FastAPI(title="Serverless Runtime")

@app.get("/")
async def root():
    return "Main routes: \
            POST -> /v1/faas/execute-sync  \
                    /v1/faas/execute-async \
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
    local_ip = socket.getaddrinfo(host='localhost', port='80')[0][-1][0]
    ip_version = ipadd(local_ip)
    # Different Prometheus and COGNIT API server cmds in IPv4 or IPv6
    if type(ip_version) == IPv4Address:
        # Start Prometheus HTTP server on the desired port, for instance 9100
        start_http_server(PROM_PORT, addr="0.0.0.0", registry=r)
        # Start uvicorn server to serve COGNIT Serverless Runtime API
        uvicorn.run(app, host="0.0.0.0", port=SR_PORT)
    elif type(ip_version) == IPv6Address:
        # Start Prometheus HTTP server on the desired port, for instance 9100
        start_http_server(PROM_PORT, addr='::', registry=r)
        # Start uvicorn server to serve COGNIT Serverless Runtime API
        uvicorn.run(app, host="::", port=SR_PORT)
