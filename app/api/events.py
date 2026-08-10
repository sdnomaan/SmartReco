from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.sessions import require_authenticated_user
from app.db.database import get_db
from app.db.models import User
from app.db.schemas import BatchEventCreate, EventCreate
from app.services.event_service import EventService, EventServiceError


router = APIRouter(prefix="/api/events", tags=["events"])


def get_event_service(db=Depends(get_db)) -> EventService:
    return EventService(db=db)


@router.post("/batch")
def ingest_event_batch(
    batch: BatchEventCreate,
    current_user: User = Depends(require_authenticated_user),
    service: EventService = Depends(get_event_service),
) -> dict[str, object]:
    try:
        return service.ingest_batch(current_user=current_user, batch_in=batch)
    except EventServiceError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("")
def ingest_single_event(
    event: EventCreate,
    current_user: User = Depends(require_authenticated_user),
    service: EventService = Depends(get_event_service),
) -> dict[str, object]:
    batch = BatchEventCreate(events=[event], session_id=event.session_id)
    return service.ingest_batch(current_user=current_user, batch_in=batch)
