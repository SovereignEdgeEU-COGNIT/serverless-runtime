from api.v1.daas import daas_router
from api.v1.faas import faas_router, RandomNumberCollector, CognitFuncExecCollector
from fastapi import FastAPI, Response
import prometheus_client
from prometheus_client.core import GaugeMetricFamily, REGISTRY

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

@app.get("/metrics")
async def get_metrics():
    return Response(
        media_type="text/plain",
        content=prometheus_client.generate_latest(r),
    )

if __name__ == "__main__":
    import uvicorn
    global r

    r = REGISTRY
    #r.register(RandomNumberCollector())
    r.register(CognitFuncExecCollector())
    uvicorn.run(app, host="0.0.0.0", port=8000)
