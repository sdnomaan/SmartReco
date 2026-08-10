from __future__ import annotations

from pathlib import Path
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import database as db_module
from app.db.database import Base


@pytest.fixture()
def isolated_database(tmp_path: Path):
    database_path = tmp_path / "smartreco-test.db"
    chroma_path = tmp_path / "chroma"
    os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
    os.environ["CHROMA_PATH"] = str(chroma_path)
    os.environ["SESSION_SECRET"] = "test-session-secret"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["MESH_API_KEY"] = ""
    get_settings.cache_clear()

    engine = create_engine(f"sqlite:///{database_path}", connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

    original_engine = db_module.engine
    original_session_local = db_module.SessionLocal

    db_module.engine = engine
    db_module.SessionLocal = testing_session_local
    Base.metadata.create_all(bind=engine)

    try:
        yield {
            "engine": engine,
            "session_local": testing_session_local,
        }
    finally:
        db_module.engine = original_engine
        db_module.SessionLocal = original_session_local
        engine.dispose()


@pytest.fixture()
def db_session(isolated_database):
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(isolated_database):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client