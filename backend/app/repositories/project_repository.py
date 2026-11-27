import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


class ProjectRepository:
    """Data access methods for Project records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        title: str,
        description: str | None = None,
    ) -> Project:
        project = Project(title=title, description=description)
        self.session.add(project)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        stmt = select(Project).where(Project.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[Project], int]:
        count_stmt = select(func.count()).select_from(Project)
        total = int((await self.session.execute(count_stmt)).scalar_one())

        stmt = (
            select(Project)
            .order_by(Project.updated_at.desc(), Project.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def update(
        self,
        project: Project,
        updates: dict[str, object],
    ) -> Project:
        for field, value in updates.items():
            setattr(project, field, value)
        project.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(project)
        return project

    async def delete(self, project: Project) -> None:
        await self.session.delete(project)
        await self.session.flush()
