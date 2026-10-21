from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.domain import router as domain_router
from app.api.routes.spatial import router as spatial_router
from app.api.routes.system import router as system_router
from app.api.routes.videos import router as videos_router
from app.api.routes.explorer import router as explorer_router
from app.events.websocket_router import router as ws_router
from app.core.config import settings
from app.core.errors import PhoenixError
from app.db.sqlite import init_db
from app.perception.continuous_pipeline import continuous_perception_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database schema
    init_db()
    # Bootstrap default users if empty
    from app.core.bootstrap import bootstrap_database_users
    bootstrap_database_users()
    # Start continuous live perception & decision pipeline
    await continuous_perception_pipeline.start()
    yield
    # Graceful shutdown of perception worker
    await continuous_perception_pipeline.stop()


app = FastAPI(
    title="PHOENIX API",
    description="Predictive Heat Observation and Emergency Navigation Intelligence System REST API & Realtime Bus",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount video directory for simulated CCTV video streaming
videos_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "videos")
if os.path.isdir(videos_dir):
    app.mount("/videos", StaticFiles(directory=videos_dir), name="videos")

# Exception handler for domain errors
@app.exception_handler(PhoenixError)
async def phoenix_error_handler(request: Request, exc: PhoenixError):
    return JSONResponse(
        status_code=400,
        content={
            "error_code": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


# Include API Routers with /api/v1 prefix
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(system_router, prefix=settings.api_v1_prefix)
app.include_router(domain_router, prefix=settings.api_v1_prefix)
app.include_router(spatial_router, prefix=settings.api_v1_prefix)
app.include_router(videos_router, prefix=settings.api_v1_prefix)
app.include_router(explorer_router, prefix=settings.api_v1_prefix)
app.include_router(ws_router)



@app.get("/")
def root():
    return {
        "system": "PHOENIX Emergency Navigation Intelligence",
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/system/health",
    }

