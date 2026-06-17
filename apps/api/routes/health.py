"""Health-check route.

Contains no business logic (§2.5 / §5 — routes delegate to `packages/`); it only
reports liveness so orchestration and the demo UI can probe the API.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
