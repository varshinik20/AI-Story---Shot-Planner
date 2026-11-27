from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.core.constants import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT
from app.dependencies import get_project_service
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])

ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
    summary="Create a new project",
)
async def create_project(
    payload: ProjectCreate,
    service: ProjectServiceDep,
) -> ProjectResponse:
    project = await service.create_project(payload)
    return ProjectResponse.model_validate(project)


@router.get(
    "",
    response_model=PaginatedResponse[ProjectResponse],
    summary="List projects ordered by most recently updated",
)
async def list_projects(
    service: ProjectServiceDep,
    limit: int = Query(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> PaginatedResponse[ProjectResponse]:
    projects, total = await service.list_projects(limit=limit, offset=offset)
    return PaginatedResponse[ProjectResponse](
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get project details by ID",
)
async def get_project(
    project_id: UUID,
    service: ProjectServiceDep,
) -> ProjectResponse:
    project = await service.get_project(project_id)
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    summary="Update project fields",
)
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    service: ProjectServiceDep,
) -> ProjectResponse:
    project = await service.update_project(project_id, payload)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete a project and its conversations",
)
async def delete_project(
    project_id: UUID,
    service: ProjectServiceDep,
) -> Response:
    await service.delete_project(project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
