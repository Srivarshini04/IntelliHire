"""DELULU v2 API layer (Workstream B).

Stub FastAPI routers for the seven-stage pipeline, fully typed so OpenAPI is
complete. Response models REUSE the frozen shared domain models
(``app.shared.models``); request models are NEW input schemas defined in
``app.api.v2.schemas`` and never carry server-generated ids.

Mount point: ``app.api.v2.router.router`` exposes ``APIRouter(prefix="/v2")``.
"""

from app.api.v2.router import router

__all__ = ["router"]
