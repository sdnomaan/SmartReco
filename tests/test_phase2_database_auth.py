from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import inspect
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.auth.security import hash_password, verify_password
from app.auth.sessions import require_admin, require_authenticated_user
from app.config import get_settings
from app.db.database import initialize_database
from app.db.models import (
    Event,
    EventType,
    Product,
    Recommendation,
    RecommendationItem,
    RecommendationStatus,
    User,
    UserBehaviorState,
    UserRole,
)
from app.db.repositories import (
    authenticate_user,
    create_event,
    create_product,
    create_recommendation,
    create_recommendation_item,
    create_user,
    get_user_by_email,
)


def test_user_creation(db_session):
    user = create_user(db_session, "User@Example.com", "supersecret123")

    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.role == UserRole.USER


def test_email_uniqueness(db_session):
    create_user(db_session, "unique@example.com", "password123")

    with pytest.raises(Exception):
        create_user(db_session, "unique@example.com", "anotherpassword")


def test_password_hashing():
    hashed = hash_password("password123")

    assert hashed != "password123"
    assert verify_password("password123", hashed)


def test_password_verification(db_session):
    user = create_user(db_session, "verify@example.com", "password123")

    assert authenticate_user(db_session, "verify@example.com", "password123") == user
    assert authenticate_user(db_session, "verify@example.com", "wrong-password") is None


def test_plaintext_password_is_not_stored(db_session):
    user = create_user(db_session, "secure@example.com", "password123")

    assert user.password_hash != "password123"
    assert "password123" not in user.password_hash


def test_user_registration(client):
    response = client.post("/register", data={"email": "register@example.com", "password": "password123"})

    assert response.status_code == 200
    assert response.json()["email"] == "register@example.com"


def test_login_logout_and_current_user(client):
    client.post("/register", data={"email": "login@example.com", "password": "password123"})
    client.post("/logout")

    login_response = client.post("/login", data={"email": "login@example.com", "password": "password123"})
    assert login_response.status_code == 200

    profile_response = client.get("/profile")
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "login@example.com"

    logout_response = client.post("/logout")
    assert logout_response.status_code == 200

    profile_after_logout = client.get("/profile")
    assert profile_after_logout.status_code == 401


def test_authenticated_user_retrieval(client):
    client.post("/register", data={"email": "current@example.com", "password": "password123"})

    response = client.get("/profile")

    assert response.status_code == 200
    assert response.json()["email"] == "current@example.com"


def test_unauthenticated_user_blocked_from_protected_endpoint(client):
    response = client.get("/profile")

    assert response.status_code == 401


def test_admin_role_detection(db_session):
    admin = create_user(db_session, "admin@example.com", "password123", role=UserRole.ADMIN)

    assert admin.role == UserRole.ADMIN


def test_normal_user_blocked_from_admin_dependency(isolated_database):
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_settings().session_secret_value,
        same_site="lax",
        https_only=False,
    )
    app.include_router(auth_router)

    @app.get("/admin-check")
    def admin_check(current_user=Depends(require_admin)):
        return {"id": current_user.id}

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        test_client.post("/register", data={"email": "user@example.com", "password": "password123"})
        response = test_client.get("/admin-check")

    assert response.status_code == 403


def test_product_creation(db_session):
    product = create_product(
        db_session,
        title="Agentic AI Fundamentals",
        description="Build agent workflows.",
        category="ai",
        subcategory="agents",
        price=49.0,
        difficulty="intermediate",
        tags=["ai", "agents"],
        duration="4h",
        instructor="Instructor",
        active=True,
    )

    assert product.id is not None
    assert product.category == "ai"


def test_event_user_and_product_relationships(db_session):
    user = create_user(db_session, "event@example.com", "password123")
    product = create_product(
        db_session,
        title="RAG Basics",
        description="Learn retrieval augmented generation.",
        category="llm",
        subcategory="rag",
        price=19.0,
        difficulty="beginner",
        tags=["llm", "rag"],
        duration="2h",
        instructor="Instructor",
        active=True,
    )

    event = create_event(
        db_session,
        user_id=user.id,
        session_id="session-1",
        event_type=EventType.PRODUCT_VIEW,
        product_id=product.id,
        category=product.category,
        metadata={"source": "catalog"},
    )

    assert event.user.id == user.id
    assert event.product.id == product.id


def test_recommendation_relationships(db_session):
    user = create_user(db_session, "recommend@example.com", "password123")
    product = create_product(
        db_session,
        title="LLM Agents",
        description="Orchestrate agents.",
        category="ai",
        subcategory="agents",
        price=79.0,
        difficulty="advanced",
        tags=["agents"],
        duration="6h",
        instructor="Instructor",
        active=True,
    )
    event = create_event(
        db_session,
        user_id=user.id,
        session_id="session-2",
        event_type=EventType.SEARCH,
        search_query="agent orchestration",
        metadata={"query_length": 2},
    )
    recommendation = create_recommendation(
        db_session,
        user_id=user.id,
        trigger_event_id=event.id,
        narrative="Based on your recent activity, this is a next-step resource.",
        recommendation_reason="Matches current journey stage.",
        journey_stage="specialization",
        behavior_snapshot={"dominant_interest": "ai_agents"},
        status=RecommendationStatus.ACTIVE,
    )
    item = create_recommendation_item(
        db_session,
        recommendation_id=recommendation.id,
        product_id=product.id,
        rank=1,
        relevance_score=0.95,
        reason="Strong journey-gap match.",
    )

    assert recommendation.user.id == user.id
    assert recommendation.recommendation_items[0].id == item.id
    assert item.product.id == product.id


def test_models_and_indexes_load_correctly(isolated_database):
    engine = isolated_database["engine"]
    initialize_database()
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "users",
        "products",
        "events",
        "user_behavior_states",
        "recommendations",
        "recommendation_items",
    }

    event_indexes = {index["name"] for index in inspector.get_indexes("events")}
    recommendation_indexes = {index["name"] for index in inspector.get_indexes("recommendations")}
    product_indexes = {index["name"] for index in inspector.get_indexes("products")}

    assert "ix_events_user_timestamp" in event_indexes
    assert "ix_events_user_event_timestamp" in event_indexes
    assert "ix_events_product_id" in event_indexes
    assert "ix_recommendations_user_created" in recommendation_indexes
    assert "ix_products_category" in product_indexes
    assert "ix_products_active" in product_indexes


def test_phase1_smoke_still_passes(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["status"] == "running"