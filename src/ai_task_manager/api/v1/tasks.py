"""Task endpoints: validate the contract, delegate and serialize."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response, status

from ai_task_manager.api.deps import TaskServiceDep
from ai_task_manager.repositories.task_repository import DEFAULT_LIMIT, MAX_LIMIT
from ai_task_manager.schemas.common import ErrorResponse
from ai_task_manager.schemas.task import (
    TaskCreate,
    TaskPage,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)

router = APIRouter(tags=["Tasks"])

StatusFilter = Annotated[TaskStatus | None, Query()]
PriorityFilter = Annotated[TaskPriority | None, Query()]
LimitQuery = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
OffsetQuery = Annotated[int, Query(ge=0)]
SortQuery = Annotated[Literal["created_at:asc", "created_at:desc"], Query()]

_CREATE_ERRORS = {
    status.HTTP_201_CREATED: {
        "model": TaskRead,
        "headers": {
            "Location": {
                "description": "Canonical URL of the created task.",
                "schema": {"type": "string", "format": "uri"},
            }
        },
    },
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}
_LIST_ERRORS = {status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse}}
_ITEM_ERRORS = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}


@router.post(
    "",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    responses=_CREATE_ERRORS,
)
def create_task(
    payload: TaskCreate,
    request: Request,
    response: Response,
    service: TaskServiceDep,
) -> TaskRead:
    """Create a task and expose its canonical URL in ``Location``."""
    task = service.create(
        title=payload.title,
        description=payload.description,
        status=payload.status.value,
        priority=payload.priority.value,
        due_at=payload.due_at,
    )
    response.headers["Location"] = str(request.url_for("get_task", task_id=task.id))
    return TaskRead.model_validate(task)


@router.get("", response_model=TaskPage, responses=_LIST_ERRORS)
def list_tasks(
    service: TaskServiceDep,
    status: StatusFilter = None,
    priority: PriorityFilter = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
    sort: SortQuery = "created_at:desc",
) -> TaskPage:
    """List tasks with filters, deterministic ordering and pagination metadata."""
    items, total = service.list(
        status=status.value if status is not None else None,
        priority=priority.value if priority is not None else None,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return TaskPage(
        items=[TaskRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{task_id}", response_model=TaskRead, name="get_task", responses=_ITEM_ERRORS)
def get_task(task_id: int, service: TaskServiceDep) -> TaskRead:
    """Return a single task by its integer identifier."""
    return TaskRead.model_validate(service.get(task_id))


@router.patch("/{task_id}", response_model=TaskRead, responses=_ITEM_ERRORS)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    service: TaskServiceDep,
) -> TaskRead:
    """Apply only the fields explicitly present in the request body."""
    changes: dict[str, object] = payload.model_dump(exclude_unset=True, mode="python")
    for name in ("status", "priority"):
        value = changes.get(name)
        if isinstance(value, Enum):
            changes[name] = value.value
    return TaskRead.model_validate(service.update(task_id, changes))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ITEM_ERRORS)
def delete_task(task_id: int, service: TaskServiceDep) -> Response:
    """Delete a task; the successful response has no body."""
    service.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
