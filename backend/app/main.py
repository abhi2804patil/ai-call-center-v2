import json
import logging

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, audio, auth, calls, campaigns, scripts, webhooks
from app.config import get_settings
from app.utils.security import decode_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="AI Call Center API",
    description="AI-powered call center SaaS platform with pre-generated audio and real-time intent classification",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = ["http://localhost:3000"] if settings.APP_ENV == "development" else settings.CORS_ORIGINS.split(",") if hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(scripts.router, prefix="/api/v1/scripts", tags=["Scripts"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["Campaigns"])
app.include_router(calls.router, prefix="/api/v1/calls", tags=["Calls"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(audio.router, prefix="/api/v1/audio", tags=["Audio"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["Webhooks"])


@app.on_event("startup")
async def startup_event():
    if settings.APP_ENV == "development":
        from app.database import Base, engine

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Development mode: tables created")
    logger.info("AI Call Center API started")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-call-center-api"}


@app.websocket("/ws/calls/{company_id}")
async def live_call_monitor(websocket: WebSocket, company_id: str):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return
    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or payload.get("company_id") != company_id:
            await websocket.close(code=4003)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    redis_client = aioredis.from_url(settings.REDIS_URL)
    pubsub = redis_client.pubsub()
    channel = f"calls:{company_id}"
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for company {company_id}")
    finally:
        await pubsub.unsubscribe(channel)
        await redis_client.close()
