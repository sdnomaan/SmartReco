from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.database import Base


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class EventType(str, Enum):
    PAGE_VIEW = "PAGE_VIEW"
    PRODUCT_VIEW = "PRODUCT_VIEW"
    SEARCH = "SEARCH"
    CATEGORY_VIEW = "CATEGORY_VIEW"
    CLICK = "CLICK"
    DWELL = "DWELL"
    ADD_TO_CART = "ADD_TO_CART"
    FAVORITE = "FAVORITE"


class RecommendationStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda enum_cls: [item.value for item in enum_cls], native_enum=False),
        nullable=False,
        default=UserRole.USER,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    events: Mapped[list[Event]] = relationship(back_populates="user", cascade="all, delete-orphan")
    behavior_state: Mapped[UserBehaviorState | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @validates("email")
    def validate_email(self, key: str, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email is required")
        return normalized


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(120), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difficulty: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[list[str] | dict | None] = mapped_column(JSON, nullable=True)
    duration: Mapped[str | None] = mapped_column(String(80), nullable=True)
    instructor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    vector_sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    vector_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vector_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list[Event]] = relationship(back_populates="product")
    recommendation_items: Mapped[list[RecommendationItem]] = relationship(back_populates="product")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(
        SAEnum(EventType, name="event_type", values_callable=lambda enum_cls: [item.value for item in enum_cls], native_enum=False),
        nullable=False,
        index=True,
    )
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    search_query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship(back_populates="events")
    product: Mapped[Product | None] = relationship(back_populates="events")
    triggered_recommendation: Mapped[Recommendation | None] = relationship(back_populates="trigger_event", uselist=False)


class UserBehaviorState(Base):
    __tablename__ = "user_behavior_states"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    dominant_interest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    interest_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    journey_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    journey_gap: Mapped[str | None] = mapped_column(String(255), nullable=True)
    momentum: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="behavior_state")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    trigger_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), nullable=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    journey_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    behavior_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RecommendationStatus] = mapped_column(
        SAEnum(
            RecommendationStatus,
            name="recommendation_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
        ),
        nullable=False,
        default=RecommendationStatus.ACTIVE,
    )

    user: Mapped[User] = relationship(back_populates="recommendations")
    trigger_event: Mapped[Event | None] = relationship(back_populates="triggered_recommendation")
    recommendation_items: Mapped[list[RecommendationItem]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    recommendation: Mapped[Recommendation] = relationship(back_populates="recommendation_items")
    product: Mapped[Product] = relationship(back_populates="recommendation_items")


Index("ix_events_user_timestamp", Event.user_id, Event.timestamp)
Index("ix_events_user_event_timestamp", Event.user_id, Event.event_type, Event.timestamp)
Index("ix_events_product_id", Event.product_id)
Index("ix_recommendations_user_created", Recommendation.user_id, Recommendation.created_at)