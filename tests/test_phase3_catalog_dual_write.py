from __future__ import annotations

import math

import pytest

from app.db.models import Product, UserRole
from app.db.repositories import create_user
from app.retrieval.chroma_store import ProductVectorStore
from app.retrieval.embeddings import MeshEmbeddingClient
from app.services.catalog_sync import sync_product, verify_product_sync


@pytest.fixture(autouse=True)
def deterministic_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    keywords = ["python", "machine learning", "ml", "deep learning", "llm", "rag", "agent", "agents", "orchestration", "data"]

    def embed_text(self: MeshEmbeddingClient, text: str) -> list[float]:
        lowered = text.lower()
        vector = [0.0 for _ in keywords]
        for index, keyword in enumerate(keywords):
            if keyword in lowered:
                vector[index] += 1.0
        if not any(vector):
            vector[0] = 1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]

    monkeypatch.setattr(MeshEmbeddingClient, "embed_text", embed_text)


def _admin_login(client, db_session):
    create_user(db_session, "admin@example.com", "password123", role=UserRole.ADMIN)
    response = client.post("/login", data={"email": "admin@example.com", "password": "password123"})
    assert response.status_code == 200


def _create_product_via_admin(client, title: str, description: str, category: str, tags: str, active: str = "on"):
    response = client.post(
        "/admin/products",
        data={
            "title": title,
            "description": description,
            "category": category,
            "subcategory": "",
            "price": "49.0",
            "difficulty": "intermediate",
            "tags": tags,
            "duration": "4h",
            "instructor": "Instructor",
            "active": active,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_admin_creates_product_and_writes_to_sqlite_and_chroma(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Agent Orchestration", "Build multi-agent workflows.", "ai", "agent, orchestration")

    product = db_session.query(Product).filter(Product.title == "Agent Orchestration").one()
    vector_store = ProductVectorStore()
    chroma_record = vector_store.get(product.id)

    assert product.active is True
    assert product.vector_sync_status == "SYNCED"
    assert chroma_record is not None
    assert chroma_record["metadata"]["product_id"] == product.id


def test_product_id_matches_between_sqlite_and_chroma(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "RAG Bootcamp", "Learn retrieval augmented generation.", "llm", "rag, llm")

    product = db_session.query(Product).filter(Product.title == "RAG Bootcamp").one()
    vector_store = ProductVectorStore()
    chroma_record = vector_store.get(product.id)

    assert chroma_record is not None
    assert chroma_record["metadata"]["product_id"] == product.id


def test_product_update_updates_sqlite(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "ML Foundations", "Intro to ML.", "ml", "machine learning")
    product = db_session.query(Product).filter(Product.title == "ML Foundations").one()

    response = client.post(
        f"/admin/products/{product.id}/update",
        data={
            "title": "ML Foundations Updated",
            "description": "Intro to ML updated.",
            "category": "ml",
            "subcategory": "foundations",
            "price": "59.0",
            "difficulty": "beginner",
            "tags": "machine learning, basics",
            "duration": "5h",
            "instructor": "Instructor",
            "active": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    db_session.expire_all()
    updated = db_session.get(Product, product.id)
    assert updated is not None
    assert updated.title == "ML Foundations Updated"


def test_product_update_updates_chroma(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Deep Learning 101", "Intro to DL.", "dl", "deep learning")
    product = db_session.query(Product).filter(Product.title == "Deep Learning 101").one()

    client.post(
        f"/admin/products/{product.id}/update",
        data={
            "title": "Deep Learning 201",
            "description": "Advanced DL.",
            "category": "dl",
            "subcategory": "advanced",
            "price": "69.0",
            "difficulty": "advanced",
            "tags": "deep learning, advanced",
            "duration": "6h",
            "instructor": "Instructor",
            "active": "on",
        },
        follow_redirects=False,
    )

    chroma_record = ProductVectorStore().get(product.id)
    assert chroma_record is not None
    assert "Deep Learning 201" in chroma_record["document"]
    assert chroma_record["metadata"]["title"] == "Deep Learning 201"


def test_deactivation_updates_sqlite(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "RAG Lab", "Hands-on RAG.", "llm", "rag")
    product = db_session.query(Product).filter(Product.title == "RAG Lab").one()

    response = client.post(f"/admin/products/{product.id}/deactivate", follow_redirects=False)

    assert response.status_code == 303
    db_session.expire_all()
    updated = db_session.get(Product, product.id)
    assert updated is not None
    assert updated.active is False


def test_deactivation_updates_chroma_metadata(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Agent Lab", "Hands-on agents.", "ai", "agents")
    product = db_session.query(Product).filter(Product.title == "Agent Lab").one()

    client.post(f"/admin/products/{product.id}/deactivate", follow_redirects=False)

    chroma_record = ProductVectorStore().get(product.id)
    assert chroma_record is not None
    assert chroma_record["metadata"]["active"] is False


def test_inactive_products_are_excluded_from_public_listing(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Invisible Product", "Will be hidden.", "ai", "agent")
    product = db_session.query(Product).filter(Product.title == "Invisible Product").one()
    client.post(f"/admin/products/{product.id}/deactivate", follow_redirects=False)

    response = client.get("/products")

    assert response.status_code == 200
    assert "Invisible Product" not in response.text


def test_normal_user_cannot_access_admin_product_management(client, db_session):
    create_user(db_session, "user@example.com", "password123", role=UserRole.USER)
    client.post("/login", data={"email": "user@example.com", "password": "password123"})

    response = client.get("/admin/products")

    assert response.status_code == 403


def test_admin_can_access_product_management(client, db_session):
    _admin_login(client, db_session)

    response = client.get("/admin/products")

    assert response.status_code == 200


def test_chroma_retrieval_returns_actual_stored_products(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Python for ML", "Learn python for machine learning.", "ml", "python, machine learning")
    _create_product_via_admin(client, "LLM Agents", "Build llm agents and orchestration.", "ai", "llm, agents, orchestration")
    _create_product_via_admin(client, "RAG Systems", "Retrieval augmented generation.", "llm", "rag, llm")

    vector_store = ProductVectorStore()
    results = vector_store.search("agent orchestration for llms", filters={"active": True}, top_k=3)
    returned_ids = [result.product_id for result in results]

    assert returned_ids
    assert all(db_session.get(Product, product_id) is not None for product_id in returned_ids)
    assert returned_ids[0] == db_session.query(Product).filter(Product.title == "LLM Agents").one().id


def test_missing_chroma_synchronization_is_detected(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Sync Check", "Check missing vectors.", "ai", "agents")
    product = db_session.query(Product).filter(Product.title == "Sync Check").one()
    vector_store = ProductVectorStore()
    vector_store.delete_product(product.id)

    report = verify_product_sync(product.id, db_session, vector_store=vector_store)

    assert report.is_in_sync is False
    assert report.reason == "missing_chroma_record"


def test_failed_vector_synchronization_is_not_silently_treated_as_success(client, db_session, monkeypatch: pytest.MonkeyPatch):
    _admin_login(client, db_session)

    def fail_update(self, product):  # noqa: ANN001
        raise RuntimeError("vector sync failed")

    monkeypatch.setattr(ProductVectorStore, "update_product", fail_update)

    response = client.post(
        "/admin/products",
        data={
            "title": "Broken Sync",
            "description": "Should fail sync.",
            "category": "ai",
            "subcategory": "",
            "price": "49.0",
            "difficulty": "intermediate",
            "tags": "agents",
            "duration": "4h",
            "instructor": "Instructor",
            "active": "on",
        },
        follow_redirects=False,
    )

    assert response.status_code == 503
    product = db_session.query(Product).filter(Product.title == "Broken Sync").one()
    assert product.vector_sync_status == "FAILED"


def test_product_reconciliation_helper_syncs_missing_vector(client, db_session):
    _admin_login(client, db_session)
    _create_product_via_admin(client, "Reconcile Me", "Needs repair.", "ai", "agents")
    product = db_session.query(Product).filter(Product.title == "Reconcile Me").one()
    vector_store = ProductVectorStore()
    vector_store.delete_product(product.id)

    report = sync_product(product.id, db_session, vector_store=vector_store)

    assert report.is_in_sync is True
    assert vector_store.get(product.id) is not None