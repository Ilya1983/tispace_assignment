import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import engine
from app.redis import close_redis, init_redis
from app.routers.articles import router as articles_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title="Data Summarization Service", lifespan=lifespan)
app.include_router(articles_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files — must be last so API routes take priority
dist_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(dist_dir):
    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")
