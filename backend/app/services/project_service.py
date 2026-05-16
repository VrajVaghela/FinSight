# app/services/project_service.py
"""
CRUD operations for Projects and Files.
Owned by Member 3 (Backend Lead).
Blueprint reference: implementation_plan_part1.md §1 services/project_service.py
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.models.orm import Project, File
from app.models.schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from fastapi import HTTPException


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: ProjectCreate, owner_id: UUID) -> Project:
        """Create a new project workspace."""
        project = Project(
            name=data.name,
            system_prompt=data.system_prompt,
            owner_id=owner_id
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_by_id(self, project_id: UUID) -> Project:
        """Fetch a project or raise 404."""
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.files))
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    async def list_by_owner(self, owner_id: UUID) -> List[Project]:
        """List all projects belonging to a user."""
        stmt = (
            select(Project)
            .where(Project.owner_id == owner_id)
            .options(selectinload(Project.files))
            .order_by(Project.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update(self, project_id: UUID, data: ProjectUpdate, owner_id: UUID) -> Project:
        """Partial update of project fields."""
        project = await self.get_by_id(project_id)
        if project.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this project")
        if data.name is not None:
            project.name = data.name
        if data.system_prompt is not None:
            project.system_prompt = data.system_prompt
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: UUID, owner_id: UUID) -> None:
        """Delete a project (cascades to files and conversations)."""
        project = await self.get_by_id(project_id)
        if project.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this project")
        await self.db.delete(project)
        await self.db.commit()

    async def get_project_status(self, project_id: UUID) -> dict:
        """Return aggregate ingestion status across all files."""
        project = await self.get_by_id(project_id)
        files_data = [
            {
                "id": f.id,
                "original_name": f.original_name,
                "docling_status": f.docling_status,
                "page_count": f.page_count,
                "chunk_count": f.chunk_count,
                "error_message": f.error_message,
                "ingested_at": f.ingested_at,
                "created_at": f.created_at,
            }
            for f in project.files
        ]
        # Derive aggregate status
        if not project.files:
            overall = "empty"
        else:
            statuses = {f.docling_status for f in project.files}
            if "processing" in statuses:
                overall = "processing"
            elif "ready" in statuses and "failed" not in statuses:
                overall = "ready"
            elif "ready" in statuses:
                overall = "partial"
            else:
                overall = "processing"

        return {"project_id": str(project_id), "files": files_data, "overall_status": overall}
