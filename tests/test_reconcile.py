import pytest
from app.errors import InputError
from app.modules.m6_reconcile.service import parse_statement, reconcile


def test_clean_statement_cleared(clean_run):
    assert clean_run["柜台对账"] == [
        {
            "柜台": "001",
            "本期分": 18000,
            "历史调整分": -2000,
            "应缴分": 16000,
            "实缴分": 16000,
            "差额分": 0,
            "对账": "已平",
        }
    ]


def test_row_conservation(mall_run):
    assert mall_run["行数勾稽"] == {
        "收到": 48,
        "销售": 34,
        "退单": 3,
        "隔离": 9,
        "重复": 1,
        "截止后": 1,
        "差额行": 0,
    }


def test_null_paid_is_not_zero(mall_run):
    assert [
        (row["柜台"], row["实缴分"], row["对账"])
        for row in mall_run["柜台对账"]
        if row["柜台"] in ("002", "003")
    ] == [("002", 0, "应补"), ("003", None, "缺缴款单")]


def test_distinguish_unmatched_statement():
    assert reconcile([], [], {"099": 880})[0]["差额分"] == -880


def test_aggregate_amount_conserves(mall_run):
    totals = mall_run["金额勾稽"]
    assert totals["应缴分"] == totals["实缴分"] + totals["差额分"] + totals["缺单应缴分"]


def test_duplicate_statement_rejected():
    with pytest.raises(InputError) as exc:
        parse_statement([{"shop": "001", "paid": "1"}, {"shop": "001", "paid": "2"}])
    assert exc.value.code == "BAD_STATEMENT"
