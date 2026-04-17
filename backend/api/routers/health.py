from fastapi import APIRouter, Request
from pydantic import BaseModel

from core.settings import settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    version: str
    checkpointer: str | None = None


@router.get("", response_model=HealthResponse)
def health_check(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        version="0.1.0",
        checkpointer=getattr(request.app.state, "checkpointer_type", None),
    )
