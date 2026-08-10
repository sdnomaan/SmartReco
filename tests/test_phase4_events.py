from __future__ import annotations

from app.db.models import Event, EventType, Product, User, UserRole
from app.db.repositories import create_product, create_user


def _login(client, db_session, email: str, role: UserRole = UserRole.USER):
    create_user(db_session, email, "password123", role=role)
    response = client.post("/login", data={"email": email, "password": "password123"})
    assert response.status_code == 200


def test_authenticated_single_event_ingestion_succeeds_and_is_persisted(client, db_session):
    _login(client, db_session, "single@example.com")

    response = client.post(
        "/api/events",
        json={
            "session_id": "session-1",
            "event_type": "PAGE_VIEW",
            "metadata": {"path": "/"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0

    db_session.expire_all()
    event = db_session.query(Event).one()
    assert event.user_id == db_session.query(User).filter(User.email == "single@example.com").one().id
    assert event.event_type == EventType.PAGE_VIEW
    assert event.timestamp is not None


def test_authenticated_batch_ingestion_succeeds_and_all_events_are_persisted(client, db_session):
    _login(client, db_session, "batch@example.com")

    response = client.post(
        "/api/events/batch",
        json={
            "events": [
                {"session_id": "session-2", "event_type": "PAGE_VIEW", "metadata": {"path": "/products"}},
                {"session_id": "session-2", "event_type": "SEARCH", "search_query": "rag"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 2
    assert body["rejected_count"] == 0

    db_session.expire_all()
    assert db_session.query(Event).count() == 2


def test_unauthenticated_request_is_rejected(client):
    response = client.post(
        "/api/events",
        json={"session_id": "session-1", "event_type": "PAGE_VIEW"},
    )

    assert response.status_code == 401


def test_client_supplied_user_id_is_ignored(client, db_session):
    _login(client, db_session, "spoof@example.com")
    spoofed_user = create_user(db_session, "other@example.com", "password123")

    response = client.post(
        "/api/events",
        json={
            "session_id": "session-3",
            "event_type": "PAGE_VIEW",
            "user_id": spoofed_user.id,
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    event = db_session.query(Event).one()
    actual_user = db_session.query(User).filter(User.email == "spoof@example.com").one()
    assert event.user_id == actual_user.id


def test_nonexistent_product_id_is_rejected_without_failing_rest_of_batch(client, db_session):
    _login(client, db_session, "mixed@example.com")
    product = create_product(
        db_session,
        title="Existing",
        description="Existing product.",
        category="ai",
        subcategory="agents",
        price=10.0,
        difficulty="beginner",
        tags=["ai"],
        duration="1h",
        instructor="Instructor",
        active=True,
        vector_sync_status="SYNCED",
    )

    response = client.post(
        "/api/events/batch",
        json={
            "events": [
                {"session_id": "session-4", "event_type": "PRODUCT_VIEW", "product_id": product.id},
                {"session_id": "session-4", "event_type": "PRODUCT_VIEW", "product_id": 999999},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    assert body["rejected"][0]["reason"].startswith("product_id 999999")

    db_session.expire_all()
    assert db_session.query(Event).count() == 1


def test_batch_exceeding_size_limit_is_rejected(client, db_session):
    _login(client, db_session, "limit@example.com")

    response = client.post(
        "/api/events/batch",
        json={
            "events": [
                {"session_id": "session-5", "event_type": "PAGE_VIEW"} for _ in range(201)
            ]
        },
    )

    assert response.status_code == 422


def test_malformed_event_type_value_is_rejected(client, db_session):
    _login(client, db_session, "invalid@example.com")

    response = client.post(
        "/api/events",
        json={"session_id": "session-6", "event_type": "NOT_A_REAL_EVENT"},
    )

    assert response.status_code == 422
    assert "event_type" in response.text


def test_events_are_queryable_afterward_with_correct_fields(client, db_session):
    _login(client, db_session, "queryable@example.com")

    response = client.post(
        "/api/events",
        json={"session_id": "session-7", "event_type": "CATEGORY_VIEW", "category": "llm"},
    )

    assert response.status_code == 200
    db_session.expire_all()
    event = db_session.query(Event).one()
    assert event.user.email == "queryable@example.com"
    assert event.event_type == EventType.CATEGORY_VIEW
    assert event.timestamp is not None