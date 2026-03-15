"""Lineaf Parser — FastAPI application with scheduler lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from lineaf.api.prices import router as prices_router
from lineaf.api.products import router as products_router
from lineaf.api.runs import router as runs_router
from lineaf.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start APScheduler on startup, shut it down on shutdown."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Lineaf Parser", lifespan=lifespan)

app.include_router(prices_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(runs_router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
