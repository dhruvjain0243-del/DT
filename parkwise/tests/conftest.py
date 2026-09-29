from __future__ import annotations

import os
from collections.abc import Generator

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-longer-than-thirty-two-characters")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app import models  # noqa: F401


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
