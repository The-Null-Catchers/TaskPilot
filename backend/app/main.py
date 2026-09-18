import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_workspace
from app.api.routes import (
    account,
    activity,
    admin,
    analytics,
    attachments,
    auth,
    integrations,
    notifications,
    personalization,
    planning,
    project_insights,
    projects,
    search,
    task_collaboration,
    task_comment_mentions,
    task_productivity,
    tasks,
    templates,
    workspaces,
)
from app.core.config import settings
from app.core.security import decode_access_token
from app.db import SessionLocal, get_db
from app.models import User
from app.realtime import channel

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger('taskpilot')


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.app_env == 'production':
        if settings.jwt_secret == 'development-only-change-me':
            raise RuntimeError('JWT_SECRET must be changed in production')
        if settings.storage_secret == 'taskpilot-dev-password':
            raise RuntimeError('STORAGE_SECRET must be changed in production')
        if not settings.notification_secret or settings.notification_secret.startswith('change-me'):
            raise RuntimeError('NOTIFICATION_SECRET must be set to a strong separate secret in production')
        if not settings.integration_secret or settings.integration_secret.startswith('change-me'):
            raise RuntimeError('INTEGRATION_SECRET must be set to a strong separate secret in production')
    yield


app = FastAPI(
    title='TaskPilot API',
    version='0.9.0',
    openapi_url='/api/v1/openapi.json',
    docs_url='/api/v1/docs',
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
    if request.url.path.startswith("/api/v1/auth"):
        response.headers["Cache-Control"] = "no-store"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


for router in (
    auth.router,
    account.router,
    workspaces.router,
    projects.router,
    task_comment_mentions.router,
    tasks.router,
    task_collaboration.router,
    attachments.router,
    planning.router,
    project_insights.router,
    templates.router,
    personalization.router,
    task_productivity.router,
    notifications.router,
    integrations.router,
    search.router,
    activity.router,
    analytics.router,
    admin.router,
):
    app.include_router(router, prefix='/api/v1')


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else 'Request failed'
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'error': {
                'code': f'HTTP_{exc.status_code}',
                'message': message,
                'detail': exc.detail,
            }
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            'error': {
                'code': 'VALIDATION_ERROR',
                'message': 'Request validation failed',
                'fields': exc.errors(),
            }
        },
    )


@app.get('/health')
async def health(db: AsyncSession = Depends(get_db)):
    checks = {'api': 'ok', 'database': 'error', 'redis': 'error'}
    try:
        await db.execute(text('SELECT 1'))
        checks['database'] = 'ok'
    except Exception:
        logger.exception('Database health check failed')
    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
        checks['redis'] = 'ok'
    except Exception:
        logger.exception('Redis health check failed')
    finally:
        await redis.aclose()
    if 'error' in checks.values():
        raise HTTPException(status_code=503, detail=checks)
    return checks


@app.websocket('/api/v1/ws/workspaces/{workspace_id}')
async def workspace_socket(websocket: WebSocket, workspace_id: str):
    from uuid import UUID

    origin = websocket.headers.get("origin")
    if origin and origin not in settings.cors_origin_list:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        payload = json.loads(auth_message)
        token = payload.get("token") if payload.get("type") == "auth" else None
        if not isinstance(token, str) or not token:
            raise ValueError("Missing WebSocket token")
        user_id = decode_access_token(token)
        wid = UUID(workspace_id)
    except Exception:
        await websocket.close(code=4401)
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4401)
            return
        try:
            await require_workspace(db, wid, user.id)
        except HTTPException:
            await websocket.close(code=4403)
            return

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(channel(wid))
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get('data'):
                await websocket.send_text(message['data'])
            try:
                incoming = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                if incoming == 'ping':
                    await websocket.send_text(json.dumps({'event': 'pong'}))
            except TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel(wid))
        await pubsub.aclose()
        await redis.aclose()
