import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# from app.core.config import Settings
from app.core.database import engine
from app.auth.routes import router as auth_router
from app.users.routes import router as users_router
from app.invitations.routes import router as invitations_router

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Knowledge Base API",
    version="0.1.0",
)


# ---------------------------------------------------------------------------
# CORS (Cross-Origin Resource Sharing)
# ---------------------------------------------------------------------------

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=Settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(invitations_router)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for any unhandled exception. Logs the full traceback
    server-side but returns a generic message to the client.
    """
    logger.exception(
        "Unhandled error on %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"},
    )


# ---------------------------------------------------------------------------
# Health / diagnostics
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Lightweight liveness probe — no DB dependency."""
    return {"status": "ok"}


@app.get("/db-test")
async def db_test():
    """Readiness probe — confirms the database is reachable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return {"database": "connected"}
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"database": "unavailable"},
        )
