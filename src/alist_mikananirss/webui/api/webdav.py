"""FastAPI routes exposing WebDAV helper actions to the WebUI."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, status

from ..services.webdav_service import get_webdav_service, webdav_service
from ..models import WebdavManualFixJob, WebdavJobStatus

router = APIRouter()


class ManualFixRequest(BaseModel):
    path: str | None = None
    execute_mode: bool | None = None
    recursive_scan: bool | None = None
    conflict_strategy: str | None = Field(
        default=None, pattern="^(skip|rename|overwrite)$"
    )


class ManualFixResponse(BaseModel):
    job_id: str
    status: WebdavJobStatus
    message: str | None = None
    target_dir: str | None = None
    dry_run: bool | None = None
    options: dict | None = None
    result: dict | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


def _job_to_response(job: WebdavManualFixJob) -> ManualFixResponse:
    return ManualFixResponse(
        job_id=job.id,
        status=job.status,
        message=job.message,
        target_dir=job.target_dir,
        dry_run=job.dry_run,
        options=job.options,
        result=job.result,
        error=job.error,
        created_at=job.created_at.isoformat() if job.created_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


@router.post("/manual-fix", response_model=ManualFixResponse, status_code=status.HTTP_202_ACCEPTED)
async def manual_fix(payload: ManualFixRequest) -> ManualFixResponse:
    service = webdav_service
    if service is None:
        service = get_webdav_service()

    try:
        job = await service.submit_manual_fix(
            path=payload.path,
            execute_mode=payload.execute_mode,
            recursive_scan=payload.recursive_scan,
            conflict_strategy=payload.conflict_strategy,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=ManualFixResponse)
async def manual_fix_status(job_id: str) -> ManualFixResponse:
    service = webdav_service
    if service is None:
        service = get_webdav_service()

    job = await service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Manual fix job '{job_id}' not found")
    return _job_to_response(job)


@router.get("/jobs", response_model=list[ManualFixResponse])
async def manual_fix_jobs() -> list[ManualFixResponse]:
    service = webdav_service
    if service is None:
        service = get_webdav_service()

    jobs = await service.list_jobs()
    return [_job_to_response(job) for job in jobs]
