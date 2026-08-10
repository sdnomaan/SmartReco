from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import EventType, RecommendationStatus, UserRole


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: UserRole = UserRole.USER


class UserLogin(BaseModel):
    email: str
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    role: UserRole
    created_at: datetime


class ProductCreate(BaseModel):
    title: str
    description: str
    category: str
    subcategory: str | None = None
    price: float = 0.0
    difficulty: str | None = None
    tags: list[str] | None = None
    duration: str | None = None
    instructor: str | None = None
    active: bool = True


class EventCreate(BaseModel):
    session_id: str
    event_type: EventType
    product_id: int | None = None
    category: str | None = None
    search_query: str | None = None
    metadata: dict | None = None
    duration_ms: int | None = None


class RecommendationItemCreate(BaseModel):
    product_id: int
    rank: int
    relevance_score: float
    reason: str


class RecommendationCreate(BaseModel):
    trigger_event_id: int | None = None
    narrative: str
    recommendation_reason: str
    journey_stage: str
    behavior_snapshot: dict | None = None
    expires_at: datetime | None = None
    status: RecommendationStatus = RecommendationStatus.ACTIVE