"""Route aggregator for version 1 of the API."""

from __future__ import annotations

from fastapi import APIRouter

from ai_task_manager.api.v1.tasks import router as tasks_router

router = APIRouter()
router.include_router(tasks_router, prefix="/tasks")


__all__ = ["router"]
