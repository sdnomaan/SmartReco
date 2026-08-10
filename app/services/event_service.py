from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Event, EventType, User
from app.db.repositories import create_event, get_product_by_id
from app.db.schemas import BatchEventCreate, EventCreate


MAX_EVENT_BATCH_SIZE = 200


@dataclass(frozen=True)
class EventResult:
    index: int
    status: str
    event_id: int | None = None
    reason: str | None = None


class EventServiceError(ValueError):
    pass


class EventService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _validate_product(self, product_id: int | None) -> str | None:
        if product_id is None:
            return None
        product = get_product_by_id(self.db, product_id)
        if product is None:
            return f"product_id {product_id} does not exist"
        return None

    def ingest_event(self, current_user: User, event_in: EventCreate) -> tuple[EventResult, Event | None]:
        product_error = self._validate_product(event_in.product_id)
        if product_error is not None:
            return EventResult(index=0, status="rejected", reason=product_error), None

        event = create_event(
            self.db,
            user_id=current_user.id,
            session_id=event_in.session_id,
            event_type=event_in.event_type,
            product_id=event_in.product_id,
            category=event_in.category,
            search_query=event_in.search_query,
            event_metadata=event_in.metadata,
            duration_ms=event_in.duration_ms,
        )
        return EventResult(index=0, status="accepted", event_id=event.id), event

    def ingest_batch(self, current_user: User, batch_in: BatchEventCreate) -> dict[str, object]:
        events = batch_in.events
        if len(events) > MAX_EVENT_BATCH_SIZE:
            raise EventServiceError(f"batch size exceeds {MAX_EVENT_BATCH_SIZE}")

        accepted: list[EventResult] = []
        rejected: list[EventResult] = []

        for index, event_in in enumerate(events):
            if batch_in.session_id and event_in.session_id != batch_in.session_id:
                rejected.append(EventResult(index=index, status="rejected", reason="session_id mismatch"))
                continue

            result, _event = self.ingest_event(current_user=current_user, event_in=event_in)
            result = EventResult(index=index, status=result.status, event_id=result.event_id, reason=result.reason)
            if result.status == "accepted":
                accepted.append(result)
            else:
                rejected.append(result)

        return {
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "accepted": [result.__dict__ for result in accepted],
            "rejected": [result.__dict__ for result in rejected],
        }
