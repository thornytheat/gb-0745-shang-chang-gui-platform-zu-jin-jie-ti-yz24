import io

import pytest

from app.errors import InputError
from app.modules.m8_corrections.correct import (
    calculate_corrected,
    correction_identity,
    run_correction,
)
from app.modules.m8_corrections.reader import open_corrections
from app.modules.m8_corrections.service import apply_corrections
from app.store import RunStore


def _corr(client, payload, sample="mall", period="2026-11"):
    return client.post(
        "/api/corrections",
        data={"period": period, "sample": sample, "file": (io.BytesIO(payload), "c.json")},
    )


@pytest.fixture
def base(dirty):
    return dirty


@pytest.fixture
def sample_corrections():
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "sample_data" / "mall_corrections.json").read_bytes()


@pytest.fixture
def corrected_run(base, sample_corrections):
    return calculate_corrected(base, sample_corrections, "2026-11")


# ---- 采信结果：补正落到哪条原流水 -----------------------------------------
def test_accepted_corrections_name_target(base, sample_corrections):
    run = calculate_corrected(base, sample_corrections, "2026-11")
    mapping = {row["补正单号"]: row["原流水号"] for row in run["补正采信"]}
    assert mapping == {
        "C001": "SM03",
        "C003": "SM05",
        "C004": "SM08",
        "C005": "RM02",
        "C006": "RM03",
        "C907": "RM04",
    }
    assert run["补正参数"]["采信"] == 6


def test_replacement_records_each_line(corrected_run):
    for row in corrected_run["补正采信"]:
        assert row["替换原行"], "采信补正必须记录被替换的原行号"
        assert row["柜台"] and row["补正分"] >= 0


# ---- 原行与补正不能并存；同一条收银只算一次 -------------------------------
def test_original_and_correction_never_coexist(base, sample_corrections):
    from collections import Counter

    base_data, correction_rows = _open(base, sample_corrections)
    corrected, decision, _ = apply_corrections(base_data, correction_rows)
    targets = {row["原流水号"] for row in decision["补正采信"]}
    counts = Counter(str(row.get("id")) for row in corrected["events"])
    assert all(counts[target] == 1 for target in targets)


def test_one_correction_per_original(base, sample_corrections):
    # C002 与 C904 同时指向 SM04，二者都不能采信
    run = calculate_corrected(base, sample_corrections, "2026-11")
    busy = {row["补正单号"] for row in run["补正隔离"] if row["原因码"] == "CORR_TARGET_BUSY"}
    assert busy == {"C002", "C904"}
    assert not any(row["原流水号"] == "SM04" for row in run["补正采信"])


def test_identical_correction_is_retried_once(base):
    payload = b'{"corrections":['
    payload += b'{"id":"C1","target":"SM03","shop":"002","day":"2026-11-19","kind":"sale","amount":"660"},'
    payload += b'{"id":"C1","target":"SM03","shop":"002","day":"2026-11-19","kind":"sale","amount":"660"}]}'
    run = calculate_corrected(base, payload, "2026-11")
    assert len([r for r in run["补正采信"] if r["补正单号"] == "C1"]) == 1
    assert [r["原因码"] for r in run["补正重传"]] == ["DUPLICATE"]


def test_conflicting_same_id_corrections_both_isolated(base):
    payload = b'{"corrections":['
    payload += b'{"id":"CX","target":"SM03","shop":"002","day":"2026-11-19","kind":"sale","amount":"660"},'
    payload += b'{"id":"CX","target":"SM03","shop":"002","day":"2026-11-19","kind":"sale","amount":"661"}]}'
    run = calculate_corrected(base, payload, "2026-11")
    assert [r["原因码"] for r in run["补正隔离"] if r["补正单号"] == "CX"] == [
        "CORR_CONFLICT",
        "CORR_CONFLICT",
    ]
    assert not any(r["补正单号"] == "CX" for r in run["补正采信"])


# ---- 失败的补正保留旧版、不改写已核对柜台 ---------------------------------
def test_rejected_corrections_keep_original(base, sample_corrections):
    import json

    base_data, correction_rows = _open(base, sample_corrections)
    corrected, decision, _ = apply_corrections(base_data, correction_rows)
    targets = {row["原流水号"] for row in decision["补正采信"]}
    before = {
        str(row["id"]): json.dumps(row, sort_keys=True, ensure_ascii=False)
        for row in base_data["events"]
    }
    after = {
        str(row["id"]): json.dumps(row, sort_keys=True, ensure_ascii=False)
        for row in corrected["events"]
    }
    for original_id, serialized in before.items():
        if original_id not in targets:
            assert after.get(original_id) == serialized


@pytest.mark.parametrize(
    "correction,code",
    [
        (
            {"id": "X1", "target": "GHOST", "shop": "002", "day": "2026-11-19", "kind": "sale", "amount": "1"},
            "CORR_NO_TARGET",
        ),
        (
            {"id": "X2", "target": "SM01", "shop": "004", "day": "2026-11-18", "kind": "sale", "amount": "1"},
            "CORR_SHOP",
        ),
        (
            {"id": "X3", "target": "S011", "shop": "001", "day": "2026-11-09", "kind": "refund",
             "amount": "1", "origin": "S011"},
            "CORR_KIND",
        ),
        (
            {"id": "X4", "target": "SM02", "shop": "002", "day": "2026-11-19", "kind": "sale", "amount": "N/A"},
            "BAD_CASH",
        ),
        (
            {"id": "X5", "target": "RM01", "shop": "001", "day": "2026-11-14", "kind": "refund",
             "amount": "1", "origin": "MISSING"},
            "CORR_BAD_ORIGIN",
        ),
    ],
)
def test_each_failure_reason(base, correction, code):
    import json

    payload = json.dumps({"corrections": [correction]}).encode()
    run = calculate_corrected(base, payload, "2026-11")
    assert run["补正隔离"][0]["原因码"] == code
    assert run["补正采信"] == []


def test_malformed_row_is_isolated_not_fatal(base):
    payload = (
        b'{"corrections":[{"id":"X","target":"SM03","shop":"002","day":"not-a-date",'
        b'"kind":"sale","amount":"660"}]}'
    )
    run = calculate_corrected(base, payload, "2026-11")
    assert run["补正隔离"][0]["原因码"] == "CORR_BAD_ROW"


# ---- 原流水保留记录 --------------------------------------------------------
def test_archive_keeps_every_original_line(base, sample_corrections):
    base_data, correction_rows = _open(base, sample_corrections)
    _, decision, _ = apply_corrections(base_data, correction_rows)
    assert len(decision["原流水留档"]) == len(base_data["events"])
    replaced_to_correction = {row["原流水号"]: row["补正单号"] for row in decision["补正采信"]}
    for row in decision["原流水留档"]:
        if row["原流水号"] in replaced_to_correction:
            assert row["去向"] == replaced_to_correction[row["原流水号"]]
        else:
            assert row["去向"] == "未补正留用"


# ---- 柜台出账与挂起 --------------------------------------------------------
def test_billable_and_suspended_counters(corrected_run):
    assert {row["柜台"] for row in corrected_run["正式账单"]} == {"002", "004"}
    assert {row["柜台"] for row in corrected_run["挂起柜台"]} == {"001", "003"}
    statuses = {row["柜台"]: row["出账状态"] for row in corrected_run["柜台出账"]}
    assert statuses == {"001": "挂起", "002": "可出账", "003": "挂起", "004": "可出账"}


def test_suspended_counters_absent_from_formal_bill(corrected_run):
    bill_ids = {row["柜台"] for row in corrected_run["正式账单"]}
    for row in corrected_run["挂起柜台"]:
        assert row["柜台"] not in bill_ids


def test_formal_bill_amounts_conserve(corrected_run):
    totals = corrected_run["正式账单合计"]
    assert totals["应缴分"] == 43000
    assert totals["应缴分"] == totals["实缴分"] + totals["差额分"] + totals["缺单应缴分"]
    assert totals["应缴分"] + sum(row["应缴分"] for row in corrected_run["挂起柜台"]) == corrected_run[
        "金额勾稽"
    ]["应缴分"]


def test_unrelated_failed_corrections_do_not_block_cleared_shop(base):
    # 一条必然失败、归因 004 的补正（试图把 002 的单子改到 004）：
    # 必须隔离，且 004 仍可出账，修正后全量勾稽与无补正基线完全一致。
    from app.modules.m7_publish.service import calculate

    payload = (
        b'{"corrections":[{"id":"Z","target":"SM01","shop":"004","day":"2026-11-18",'
        b'"kind":"sale","amount":"999"}]}'
    )
    run = calculate_corrected(base, payload, "2026-11")
    baseline = calculate(base, "2026-11")
    assert run["补正隔离"][0]["原因码"] == "CORR_SHOP"
    assert "004" in {row["柜台"] for row in run["正式账单"]}
    assert run["金额勾稽"] == baseline["金额勾稽"]
    assert run["行数勾稽"] == baseline["行数勾稽"]


# ---- 幂等与失败不入库 ------------------------------------------------------
def test_identity_stable_and_period_sensitive(base, sample_corrections):
    first, params = correction_identity(base, sample_corrections, "2026-11")
    second, _ = correction_identity(base, sample_corrections, "2026-11")
    third, _ = correction_identity(base, b'{"corrections":[]}', "2026-11")
    other_period, _ = correction_identity(base, sample_corrections, "2026-10")
    assert first == second != third != other_period


def test_run_correction_idempotent(tmp_path, base, sample_corrections):
    store = RunStore(tmp_path / "c.sqlite")
    first, reused_first = run_correction(store, base, sample_corrections, "2026-11")
    second, reused_second = run_correction(store, base, sample_corrections, "2026-11")
    assert reused_first is False and reused_second is True
    assert first["运行清单"]["批次"] == second["运行清单"]["批次"]
    assert len(store.history()) == 1


def test_concurrent_corrections_create_one_batch(tmp_path, base, sample_corrections):
    from concurrent.futures import ThreadPoolExecutor

    store = RunStore(tmp_path / "c.sqlite")
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(
            executor.map(
                lambda _: run_correction(store, base, sample_corrections, "2026-11"), range(5)
            )
        )
    assert sum(not reused for _, reused in results) == 1
    assert len(store.history()) == 1


def test_corrected_row_balance_conserves(corrected_run):
    balance = corrected_run["行数勾稽"]
    assert balance["差额行"] == 0
    accounted = sum(
        balance[key]
        for key in ("销售", "退单", "隔离", "重复", "截止后")
    )
    assert balance["收到"] == accounted


def test_structural_failure_preserves_old_batch(tmp_path, base, sample_corrections):
    store = RunStore(tmp_path / "c.sqlite")
    good, _ = run_correction(store, base, sample_corrections, "2026-11")
    with pytest.raises(InputError):
        open_corrections(b"{")
    with pytest.raises(InputError):
        run_correction(store, base, b'{"corrections":[]}', "2026-11")
    assert store.get(good["运行清单"]["批次"]) is not None
    assert len(store.history()) == 1


# ---- HTTP 入口 -------------------------------------------------------------
def test_http_acceptance_and_decision(client, sample_corrections):
    response = _corr(client, sample_corrections)
    assert response.status_code in (200, 201)
    body = response.json
    assert body["accepted"] == 6 and body["isolated"] == 7 and body["retried"] == 1
    assert body["billable"] == ["002", "004"]
    assert body["suspended"] == ["001", "003"]
    assert body["bill_totals"]["应缴分"] == 43000
    detail = client.get(f"/api/corrections/{body['id']}")
    assert detail.status_code == 200 and "补正采信" in detail.json


def test_http_replay_is_idempotent(client, sample_corrections):
    first = _corr(client, sample_corrections)
    second = _corr(client, sample_corrections)
    assert first.json["id"] == second.json["id"]
    assert second.json["reused"] is True


def test_http_missing_file_rejected(client):
    response = client.post("/api/corrections", data={"period": "2026-11", "sample": "mall"})
    assert response.status_code == 422
    assert response.json["code"] == "NO_CORRECTION"


def test_http_bad_correction_writes_nothing(client):
    response = _corr(client, b"{")
    assert response.status_code == 422 and response.json["code"] == "BAD_JSON"
    assert client.get("/api/runs").json == []


def test_corrections_page_renders(client, sample_corrections):
    run_id = _corr(client, sample_corrections).json["id"]
    page = client.get(f"/work/corrections?run={run_id}")
    assert page.status_code == 200
    assert "正式账单".encode() in page.data and "挂起柜台".encode() in page.data


def _open(base, correction_raw):
    from app.modules.m1_intake.reader import open_payload

    return open_payload(base), open_corrections(correction_raw)
