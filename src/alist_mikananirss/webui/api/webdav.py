"""FastAPI routes exposing WebDAV helper actions to the WebUI."""

from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from ..services.webdav_service import get_webdav_service, webdav_service

router = APIRouter()


class ManualFixRequest(BaseModel):
    path: str | None = None
    execute_mode: bool | None = None
    recursive_scan: bool | None = None
    conflict_strategy: str | None = Field(
        default=None, pattern="^(skip|rename|overwrite)$"
    )


class ManualFixResponse(BaseModel):
    success: bool
    message: str | None = None
    target_dir: str | None = None
    dry_run: bool | None = None
    options: dict | None = None
    result: dict | None = None


@router.post("/manual-fix", response_model=ManualFixResponse)
async def manual_fix(payload: ManualFixRequest) -> ManualFixResponse:
    service = webdav_service
    if service is None:
        service = get_webdav_service()

    result = await service.run_manual_fix(
        path=payload.path,
        execute_mode=payload.execute_mode,
        recursive_scan=payload.recursive_scan,
        conflict_strategy=payload.conflict_strategy,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Manual fix failed"))

    return ManualFixResponse(
        success=True,
        message=result.get("message"),
        target_dir=result.get("target_dir"),
        dry_run=result.get("dry_run"),
        options=result.get("options"),
        result=result.get("result"),
    )
