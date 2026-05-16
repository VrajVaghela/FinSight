# app/api/projects.py
"""
Project management endpoints.
Blueprint reference: implementation_plan_part1.md — /api/projects, /api/projects/{id}/status
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from typing import List
from uuid import UUID

from app.models.database import get_db
from app.models.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectStatusResponse, FileResponse
)
from app.services.project_service import ProjectService
from app.dependencies import get_current_user

router = APIRouter()


def _to_response(project) -> ProjectResponse:
    """Convert ORM Project → ProjectResponse with computed fields."""
    files = project.__dict__.get("files") or []
    return ProjectResponse(
        id=project.id,
        name=project.name,
        system_prompt=project.system_prompt,
        created_at=project.created_at,
        file_count=len(files),
        status=project.status() if files else "empty"
    )


@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(
    req: ProjectCreate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new project workspace."""
    service = ProjectService(db)
    project = await service.create(req, owner_id=user_id)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        system_prompt=project.system_prompt,
        created_at=project.created_at,
        file_count=0,
        status="empty"
    )


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all projects for the authenticated user."""
    service = ProjectService(db)
    projects = await service.list_by_owner(user_id)
    return [_to_response(p) for p in projects]


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single project by ID."""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if project.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return _to_response(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    req: ProjectUpdate,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Partial update of project name or system prompt."""
    service = ProjectService(db)
    project = await service.update(project_id, req, owner_id=user_id)
    return _to_response(project)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a project and all its files and conversations."""
    service = ProjectService(db)
    await service.delete(project_id, owner_id=user_id)


@router.get("/projects/{project_id}/status", response_model=ProjectStatusResponse)
async def get_project_status(
    project_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Polls ingestion status for all files in a project.
    Frontend uses this to know when documents are ready for Q&A.
    """
    service = ProjectService(db)
    status = await service.get_project_status(project_id)
    return status
