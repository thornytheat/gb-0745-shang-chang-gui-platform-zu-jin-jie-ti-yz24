from pathlib import Path

import pytest
from app.main import create_app
from app.modules.m1_intake.reader import open_payload
from app.modules.m7_publish.service import calculate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def clean():
    return (ROOT / "sample_data" / "clean.json").read_bytes()


@pytest.fixture(scope="session")
def dirty():
    return (ROOT / "sample_data" / "mall.json").read_bytes()


@pytest.fixture(scope="session")
def clean_run(clean):
    return calculate(clean, "2026-11")


@pytest.fixture(scope="session")
def mall_run(dirty):
    return calculate(dirty, "2026-11")


@pytest.fixture
def mall_rows(dirty):
    return open_payload(dirty)


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": tmp_path / "rent.sqlite"})


@pytest.fixture
def client(app):
    return app.test_client()
