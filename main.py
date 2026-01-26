import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse


from app.core.config import settings
from app.router import router
from app.database.session_mongo import connect_to_mongo, close_mongo_connection
from app.database.session_sql import (
    connect_to_postgres,
    close_postgres_connection,
    initialize_checkpointer,
    AsyncSessionLocal,
)
from app.utils.exception_utils import DetailedHTTPException
from app.utils.seed import seed_data
from app.utils.logger_utils import get_logger
from app.middlewares.exception_handler import (
    custom_http_exception_handler,
    unhandled_exception_handler,
    integrity_exception_handler,
)
from sqlalchemy.exc import IntegrityError
from app.middlewares.rate_limit_middleware import rate_limit_middleware
from app.schedulers import scheduler_manager
from app.crud import user_crud
from app.assistant.agent import chat_agent
from app.database.blob_storage import verify_containers, close_blob_service_client


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage FastAPI application lifecycle events.

    Args:
        app (FastAPI): The FastAPI application instance.
    """
    logger.info("Starting up...")

    # Establish DB connections
    await connect_to_mongo()
    await connect_to_postgres()
    await initialize_checkpointer()
    await verify_containers()

    logger.info("Database connections established and verified containers.")

    # Check and seed initial data if admin is missing
    async with AsyncSessionLocal() as session:
        admin = await user_crud.get_by_email(session, settings.SUPER_ADMIN_EMAIL)
        if not admin:
            logger.info("Database not seeded. Running seeder...")
            await seed_data(session)
            logger.info("Seeder finished.")
        else:
            logger.info("Database already seeded. Skipping seeder.")

    # Start background schedulers
    await scheduler_manager.start()
    await rate_limit_middleware.redis_client.ping()
    await chat_agent.initialize()

    logger.info("Background schedulers started, Redis client connected, and chat agent initialized.")
    logger.info("Startup complete.")

    yield

    # Cleanup tasks and DB connections on shutdown
    logger.info("Shutting down...")
    await close_blob_service_client()
    await rate_limit_middleware.redis_client.close()
    await scheduler_manager.stop()

    await close_mongo_connection()
    await close_postgres_connection()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description=settings.PROJECT_DESCRIPTION,
    lifespan=lifespan,
    docs_url=None,
)


@app.get("/docs", include_in_schema=False)
def docs():
    """
    Serve custom Swagger UI HTML.

    Returns:
        HTMLResponse: Custom documentation UI.
    """
    with open("static/custom_swagger.html") as f:
        return HTMLResponse(content=f.read())


# Custom exception handlers
app.add_exception_handler(DetailedHTTPException, custom_http_exception_handler)
app.add_exception_handler(IntegrityError, integrity_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "https://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit-Minute",
        "X-RateLimit-Remaining-Minute",
        "X-RateLimit-Reset-Minute",
    ],
)


# Trusted hosts
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])


# Rate-limit middleware
app.middleware("http")(rate_limit_middleware)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log incoming request details and processing time.

    Args:
        request (Request): Incoming HTTP request
        call_next (callable): Next handler in the chain

    Returns:
        Response: HTTP response from next handler
    """
    start_time = time.time()

    # Disable buffering for streaming endpoints
    if request.url.path in ["/api/chat/stream", "/api/v1/chat/stream"]:
        response = await call_next(request)
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        return response

    # Process request through next middleware/route
    response = await call_next(request)

    # Calculate request handling time
    process_time = time.time() - start_time

    logger.info(
        f"Method: {request.method} | "
        f"URL: {request.url} | "
        f"Status: {response.status_code} | "
        f"Process Time: {process_time:.4f}s"
    )
    return response


# Register main router
app.include_router(router, prefix=settings.API_STR)


@app.get("/")
def read_root():
    """
    Root endpoint returning a welcome message.

    Returns:
        dict: Welcome message with project name.
    """
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
