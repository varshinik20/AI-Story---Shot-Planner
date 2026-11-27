import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectNotFoundError
from app.db.models.project import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    """Business operations for managing CINEMIND projects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.project_repo = ProjectRepository(session)

    async def create_project(self, payload: ProjectCreate) -> Project:
        project = await self.project_repo.create(
            title=payload.title,
            description=payload.description,
        )
        await self.session.commit()
        return project

    async def get_project(self, project_id: uuid.UUID) -> Project:
        project = await self.project_repo.get_by_id(project_id)
        if project is None:
            raise ProjectNotFoundError()
        return project

    async def list_projects(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[Project], int]:
        return await self.project_repo.list_paginated(limit=limit, offset=offset)

    async def update_project(
        self,
        project_id: uuid.UUID,
        payload: ProjectUpdate,
    ) -> Project:
        project = await self.get_project(project_id)
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value

        if updates:
            project = await self.project_repo.update(project, updates)
            await self.session.commit()
        return project

    async def delete_project(self, project_id: uuid.UUID) -> None:
        project = await self.get_project(project_id)
        await self.project_repo.delete(project)
        await self.session.commit()
