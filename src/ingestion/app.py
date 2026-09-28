"""FastAPI app exposing the mock government catalogue endpoint (api/ingest.py)
plus a basic health check. This is what main.py's CatalogClient polls against.
"""

import logging

from fastapi import FastAPI

from api.ingest import router as catalogue_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Netra Catalogue Service")
app.include_router(catalogue_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}