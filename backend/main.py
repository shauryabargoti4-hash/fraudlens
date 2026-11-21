import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend import __version__
from backend.core.config import get_settings
from backend.core.database import init_db
from backend.core.logging_config import logger
from backend.api.v1.router import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager: sets up DB tables & storage on startup."""
    logger.info(f"Starting {settings.app_name} v{__version__} [Env: {settings.app_env}]")
    settings.ensure_directories()
    init_db()
    logger.info("Application initialization complete. Ready to receive requests.")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "ClauseGuard - Explainable AI Insurance Fraud & Policy Loophole Detection Platform. "
        "Automates cross-document fraud detection, clause contradiction analysis, "
        "and policy loophole identification."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    return response


# Global Exception Handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An internal server error occurred.",
            "detail": str(exc) if settings.app_debug else None,
        },
    )


# Root Endpoint
@app.get("/", tags=["Root"])
def read_root():
    """Root metadata endpoint."""
    return {
        "app": settings.app_name,
        "version": __version__,
        "environment": settings.app_env,
        "status": "online",
        "docs": "/docs",
        "api_v1": settings.api_v1_prefix,
    }


# Mount API Router
app.include_router(api_router, prefix=settings.api_v1_prefix)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
