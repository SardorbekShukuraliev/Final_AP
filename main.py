# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from database import init_databases
from api import auth_api, chef, client, admin, waiter
from middleware.rate_limiter import RateLimiterMiddleware   # <-- новый импорт

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_databases()
    yield

app = FastAPI(title="BitePlate SRMS", lifespan=lifespan)

# CORS должен быть до rate limiter, чтобы OPTIONS не блокировались
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Подключаем Rate Limiter (после CORS, до роутеров)
app.add_middleware(RateLimiterMiddleware, requests_per_minute=100, burst_size=20)

app.include_router(auth_api.router)
app.include_router(client.router, prefix="/api/client")
app.include_router(admin.router, prefix="/api/admin")
app.include_router(waiter.router_http, prefix="/api/waiter")
app.include_router(waiter.router, prefix="/api/waiter")
app.include_router(chef.router_http, prefix="/api/chef")
app.include_router(chef.router, prefix="/api/chef")

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)