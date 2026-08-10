import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("CHROMA_PATH", "./data/chroma-test")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("MESH_API_KEY", "")
os.environ.setdefault("MESH_MODEL", "gpt-4o-mini")
os.environ.setdefault("ENVIRONMENT", "testing")

from fastapi.testclient import TestClient

from app.main import app


def test_root_endpoint_returns_running_status() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "app": "SmartReco",
        "status": "running",
        "message": "Behavioral recommendation engine is online.",
    }