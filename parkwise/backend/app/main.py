from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import get_settings
from .core.logging import configure_logging
from .routers import auth, availability, facilities, feedback, parking, predictions, reports, slots, users, vehicles
from .schemas.common import HealthResponse


settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Authenticated smart-parking management and prediction API.",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", uuid4().hex)
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request_id,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "request_error", "message": exc.detail}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in exc.errors()
    ]
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected server error occurred",
            }
        },
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", environment=settings.environment)


for api_router in (
    auth.router,
    users.router,
    vehicles.router,
    facilities.router,
    slots.router,
    parking.router,
    availability.router,
    feedback.router,
    reports.router,
    predictions.router,
):
    app.include_router(api_router)
