from api.v1.daas import daas_router
from api.v1.faas import faas_router
from fastapi import FastAPI

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

    uvicorn.run(app, host="0.0.0.0", port=8000)
