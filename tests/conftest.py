import os
import sys

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from app.db import get_db


@pytest.fixture()
def application(tmp_path):
    database_path = tmp_path / "test.sqlite"
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "DATABASE": str(database_path),
        }
    )

    yield app


@pytest.fixture()
def client(application):
    return application.test_client()


@pytest.fixture()
def database(application):
    with application.app_context():
        yield get_db()
