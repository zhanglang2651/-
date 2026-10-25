"""pytest 公共装置：把数据库指向临时目录，避免污染真实数据。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session", autouse=True)
def temp_db(tmp_path_factory):
    import app.services.db as db

    db.DB_PATH = tmp_path_factory.mktemp("data") / "test.db"
    db.init_db()
    yield db.DB_PATH


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
