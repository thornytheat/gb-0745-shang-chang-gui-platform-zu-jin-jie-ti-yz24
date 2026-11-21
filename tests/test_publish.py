import hashlib
import io
from concurrent.futures import ThreadPoolExecutor

from app.modules.m7_publish.service import run_once
from app.store import RunStore


def test_atomic_idempotency(client):
    first = client.post("/api/runs", json={"sample": "clean"})
    second = client.post("/api/runs", json={"sample": "clean"})
    assert [first.status_code, second.status_code] == [201, 200]
    assert second.json["id"] == first.json["id"]
    assert len(client.get("/api/runs").json) == 1


def test_record_can_be_reloaded(tmp_path, clean):
    path = tmp_path / "test.sqlite"
    run, _ = run_once(RunStore(path), clean, "2026-11")
    assert RunStore(path).get(run["运行清单"]["批次"])["金额勾稽"]["应缴分"] == 16000


def test_concurrent_attempts_create_one_row(tmp_path, clean):
    store = RunStore(tmp_path / "same.sqlite")
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: run_once(store, clean, "2026-11"), range(5)))
    assert sum(not reused for _, reused in results) == 1
    assert len(store.history()) == 1


def test_export_matches_exact_input(client, clean):
    run = client.post(
        "/api/runs", data={"period": "2026-11", "file": (io.BytesIO(clean), "账簿.json")}
    ).json
    result = client.get(f"/api/export/{run['id']}")
    assert result.headers["Content-Disposition"].startswith("attachment;")
    assert result.json["运行清单"]["输入摘要"] == hashlib.sha256(clean).hexdigest()
    assert result.json["金额勾稽"]["应缴分"] == 16000


def test_failed_input_does_not_write(client):
    response = client.post("/api/runs", data={"file": (io.BytesIO(b"{"), "bad.json")})
    assert response.status_code == 422
    assert response.json["code"] == "BAD_JSON"
    assert client.get("/api/runs").json == []


def test_period_affects_run_identity(client):
    october = client.post("/api/runs", json={"sample": "clean", "period": "2026-10"}).json
    november = client.post("/api/runs", json={"sample": "clean", "period": "2026-11"}).json
    assert october["id"] != november["id"]
    assert october["totals"]["应缴分"] == 13000
