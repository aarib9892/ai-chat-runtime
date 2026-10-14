from fastapi.exceptions import RequestValidationError

from app.db.database import get_pool
from contextlib import asynccontextmanager
from app.db.database import connect_db, close_db
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router

from app.api.conversations import router as converstions_router
from app.api.documents import router as documents_router
from app.middleware.request_id import (
    RequestIdMiddleware,
)
from app.observability.logging import (
    configure_logging,
)
from app.config.settings import settings

from fastapi.responses import JSONResponse

from app.errors import AppError
from app.observability.logging import (
    request_id_context,
)
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


configure_logging()
app = FastAPI(
    title="AI Chat Runtime",
    lifespan=lifespan,
    docs_url=(None if settings.is_production else "/docs"),
    redoc_url=(None if settings.is_production else "/redoc"),
    openapi_url=(None if settings.is_production else "/openapi.json"),
)
app.add_middleware(RequestIdMiddleware)
# 1. Define the domains allowed to access your API
origins = settings.parsed_cors_origins

# 2. Add the CORS middleware to your FastAPI app
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Whitelist of domains
    allow_credentials=True,  # Allow cookies and authentication headers
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],  # Allow all standard HTTP methods (GET, POST, etc.)
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Request-ID",
    ],  # Allow all headers
    expose_headers=["X-Request-ID"],
)


@app.get("/")
async def root():
    return "Hello World"


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
):
    request_id = request_id_context.get()

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "The request payload is invalid.",
                "retryable": False,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(AppError)
async def app_error_handler(
    request: Request,
    exc: AppError,
):
    request_id = request_id_context.get()

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.public_message,
                "retryable": exc.retryable,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(
    request: Request,
    exc: Exception,
):
    request_id = request_id_context.get()

    logger.exception("unhandled_http_error")

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error " "occurred.",
                "retryable": False,
                "request_id": request_id,
            }
        },
    )


@app.get(
    "/health/ready",
    include_in_schema=False,
)
async def health_ready():
    try:
        pool = get_pool()

        await pool.fetchval("SELECT 1")

        return {
            "status": "ready",
        }

    except Exception:
        raise HTTPException(
            status_code=(status.HTTP_503_SERVICE_UNAVAILABLE),
            detail="Service not ready.",
        )


app.include_router(chat_router, prefix="/api")
app.include_router(
    converstions_router,
    prefix="/api",
)
app.include_router(
    documents_router,
    prefix="/api",
)
