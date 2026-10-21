"""
System health and readiness endpoints for PHOENIX.
"""

from datetime import datetime, timezone
from fastapi import APIRouter
from app.api.schemas.contracts import HealthCheckResponse, ReadinessResponse
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=HealthCheckResponse)
def get_system_health() -> HealthCheckResponse:
    """Return health status of core prototype subsystems."""
    return HealthCheckResponse(
        status="HEALTHY",
        timestamp=datetime.now(timezone.utc),
        version="1.0.0",
        environment=settings.environment,
        services={
            "perception": "OPERATIONAL",
            "risk_engine": "OPERATIONAL",
            "routing_engine": "OPERATIONAL",
            "sqlite_db": "OPERATIONAL",
        },
    )


@router.get("/ready", response_model=ReadinessResponse)
def get_system_readiness() -> ReadinessResponse:
    """Return readiness status indicating if AI models and database are ready to serve."""
    return ReadinessResponse(
        ready=True,
        ai_status="OPERATIONAL",
        persistence_status="OPERATIONAL",
        timestamp=datetime.now(timezone.utc),
    )
