"""
VaidyaMD HMS — FastAPI Main Application (Production Ready)
"""

import os
import time
import uuid
import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.core.websocket import ws_manager, connected_user_roles

# Structured logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vaidyamd")

# Sliding-window rate limiter for /auth/login (client IP -> timestamps)
login_attempts: dict[str, list[float]] = defaultdict(list)
LOGIN_RATE_LIMIT = 20  # max 20 login attempts per minute per IP
RATE_LIMIT_WINDOW = 60.0  # seconds


# Core routers
from app.modules.auth.router import router as auth_router
from app.modules.patients.router import router as patients_router
from app.modules.appointments.router import router as appointments_router
from app.modules.billing.router import router as billing_router
from app.modules.wallet.router import router as wallet_router
from app.modules.notifications.router import router as notifications_router
from app.modules.templates.router import router as templates_router
from app.modules.clinical_records.router import router as clinical_records_router
from app.modules.ai_scribe.router import router as ai_scribe_router
from app.core.routers.permission_profiles import router as permission_profiles_router
from app.core.routers.branches import router as branches_router
from app.modules.ipd.router import router as ipd_router
from app.modules.pharmacy.router import router as pharmacy_router
from app.modules.lims.router import router as lims_router
from app.core.routers.analytics import router as analytics_router
from app.core.routers.documents import router as documents_router
from app.modules.counseling.router import router as counseling_router
from app.core.routers.admin_hub import router as admin_hub_router

# Plugin routers
from app.plugins.fertility.router import router as fertility_router
from app.plugins.opd.router import router as opd_router
from app.plugins.cosgyn.router import router as cosgyn_router

# HL7 MLLP Server
from app.core.hl7_server import start_hl7_mllp_server


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    print("🚀 VaidyaMD HMS starting up...")
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        print("✅ Database connection verified (schema managed independently)")
    except Exception as e:
        print(f"⚠️ Database connection verification notice: {e}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Start background HL7 MLLP server on port 2575 if enabled (clinic LAN environments)
    if settings.ENABLE_HL7_MLLP:
        hl7_server_task = asyncio.create_task(start_hl7_mllp_server(host="0.0.0.0", port=2575))
    else:
        logger.info("ℹ️ HL7 MLLP raw TCP server disabled (Cloud Run mode). Use HTTP REST webhooks for analyzer feeds.")


    # Register default event listeners for cross-domain telemetry
    from app.core.events import event_bus, AppointmentStatusChangedEvent

    async def on_appointment_status_changed(evt: AppointmentStatusChangedEvent):
        logger.info(f"⚡ [EVENT BUS] Appointment {evt.appointment_id} status transitioned: {evt.old_status} -> {evt.new_status}")

    event_bus.subscribe(AppointmentStatusChangedEvent, on_appointment_status_changed)

    yield
    print("🛑 VaidyaMD HMS shutting down...")


app = FastAPI(
    title="VaidyaMD HMS API",
    description="Hospital Management System for VaidyaMD — Modular Monolith Architecture",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)

# --- Security & Timing Middleware ---
@app.middleware("http")
async def security_and_timing_middleware(request: Request, call_next):
    start_time = time.time()
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Rate limiting for auth login route
    path = request.url.path.rstrip("/")
    if request.method == "POST" and path.endswith("/auth/login"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        # Clean timestamps older than window
        login_attempts[client_ip] = [t for t in login_attempts[client_ip] if now - t < RATE_LIMIT_WINDOW]
        if len(login_attempts[client_ip]) >= LOGIN_RATE_LIMIT:
            logger.warning(f"Rate limit exceeded for IP {client_ip} on /auth/login (ReqID: {request_id})")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many login attempts. Please wait a minute before trying again.", "request_id": request_id},
            )
        login_attempts[client_ip].append(now)

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Request-ID"] = request_id

    # Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Structured request logging
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} [{process_time:.4f}s] (ReqID: {request_id})")

    return response



# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    if isinstance(exc, HTTPException):
        resp = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "request_id": req_id},
        )
    else:
        print(f"❌ [UNHANDLED ERROR] (Request ID: {req_id}): {exc}")
        detail = str(exc) if settings.DEBUG else "An unexpected internal error occurred. Please contact hospital technical support."
        resp = JSONResponse(
            status_code=500,
            content={"detail": detail, "request_id": req_id, "error_type": exc.__class__.__name__},
        )
    origin = request.headers.get("origin")
    if origin:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "*"
    return resp


# --- Core Routers ---
app.include_router(auth_router, prefix="/api/core")
app.include_router(patients_router, prefix="/api/core")
app.include_router(appointments_router, prefix="/api/core")
app.include_router(billing_router, prefix="/api/core")
app.include_router(wallet_router, prefix="/api/core")
app.include_router(notifications_router, prefix="/api/core")
app.include_router(templates_router, prefix="/api/core")
app.include_router(clinical_records_router, prefix="/api/core")
app.include_router(ai_scribe_router, prefix="/api/core")
app.include_router(permission_profiles_router, prefix="/api/core")
app.include_router(branches_router, prefix="/api/core")
app.include_router(ipd_router, prefix="/api/core")
app.include_router(pharmacy_router, prefix="/api/core")
app.include_router(lims_router, prefix="/api/core")
app.include_router(analytics_router, prefix="/api/core")
app.include_router(documents_router, prefix="/api/core")
app.include_router(counseling_router, prefix="/api/core")
app.include_router(admin_hub_router, prefix="/api/core")

# --- Plugin Routers ---
app.include_router(fertility_router, prefix="/api/plugins")
app.include_router(opd_router, prefix="/api/plugins")
app.include_router(cosgyn_router, prefix="/api/plugins")

# --- Static Files (uploads) ---
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
app.mount("/api/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="api_uploads")


# --- WebSocket Endpoint ---
@app.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(websocket: WebSocket, user_id: str):
    """
    Real-time notification channel per user.
    Frontend connects as: ws://localhost:8000/ws/notifications/{userId}?token={jwt}
    """
    token = websocket.query_params.get("token")
    if settings.ENVIRONMENT == "production" and not token:
        await websocket.close(code=4401, reason="Authentication token required")
        return

    if token:
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(token)
            if payload.get("sub") != user_id and settings.ENVIRONMENT == "production":
                await websocket.close(code=4403, reason="Token does not match requested user_id")
                return
        except Exception:
            if settings.ENVIRONMENT == "production":
                await websocket.close(code=4401, reason="Invalid token")
                return

    await ws_manager.connect(websocket, user_id)
    try:
        await websocket.send_json({"type": "connected", "message": "VaidyaMD HMS WebSocket connected"})
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "register":
                connected_user_roles[user_id] = {
                    "role": data.get("role"),
                    "tenant_id": data.get("tenant_id"),
                }
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
        connected_user_roles.pop(user_id, None)


# --- Production Health Check ---
@app.get("/api/health")
async def health_check():
    """Health check validating active database connectivity and websocket status."""
    db_status = "healthy"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "connected_users": ws_manager.connected_users_count,
        "active_plugins": ["fertility", "opd", "ipd", "pharmacy", "lims", "analytics"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
