"""FastAPI application factory and lifespan."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.logging import setup_logging
from app.core.middleware import SecurityHeadersMiddleware

logger = structlog.get_logger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    setup_logging(debug=settings.DEBUG)
    logger.info(
        "starting",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    # Warm the Neon connection pool
    if await check_db_connection():
        logger.info("database_connected")
    else:
        logger.error("database_connection_failed")

    yield

    logger.info("shutting_down")


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # --- Security & Tracing Middleware ---
    app.add_middleware(SecurityHeadersMiddleware)


    # --- Health check ---
    @app.get("/api/health")
    async def health():
        return JSONResponse(
            content={
                "status": "ok",
                "version": settings.APP_VERSION,
            }
        )

    # --- Webhook router ---
    from app.webhook.router import router as webhook_router

    app.include_router(webhook_router)

    # --- Application Routers ---
    from app.routers.auth import router as auth_router
    from app.routers.conversations import router as conversations_router
    from app.routers.handoff import router as handoff_router
    from app.routers.orders import router as orders_router
    from app.routers.products import router as products_router
    from app.routers.settings import router as settings_router
    from app.routers.usage import router as usage_router

    app.include_router(auth_router)
    app.include_router(products_router)
    app.include_router(orders_router)
    app.include_router(handoff_router)
    app.include_router(conversations_router)
    app.include_router(settings_router)
    app.include_router(usage_router)

    return app


app = create_app()
