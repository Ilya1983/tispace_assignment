from contextlib import asynccontextmanager

from fastapi import FastAPI

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
