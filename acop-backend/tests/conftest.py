import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///./test_acop.db"
os.environ["K8S_MODE"] = "mock"
os.environ["ANTHROPIC_API_KEY"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()
    yield
    if os.path.exists("test_acop.db"):
        os.remove("test_acop.db")


@pytest.fixture
def client():
    return TestClient(app)
