import pytest
from app.errors import InputError
from app.modules.m1_intake.amounts import cents
from app.modules.m1_intake.reader import open_payload
from app.modules.m1_intake.service import parse_events


# TRAP-06
def test_normalized_thousands(mall_run):
    assert next(row["销售分"] for row in mall_run["收银行"] if row["流水号"] == "SM01") == 123450


# TRAP-07
def test_missing_amount_isolated(mall_run):
    assert any(row["流水号"] == "SM03" and row["原因码"] == "BAD_CASH" for row in mall_run["隔离"])


# TRAP-08
def test_leading_zero_and_long_id(mall_run):
    assert ("001", "S009007199254740993") == (
        mall_run["收银行"][0]["柜台"],
        next(row["流水号"] for row in mall_run["收银行"] if row["流水号"].startswith("S009")),
    )


# TRAP-17
def test_legacy_alias(mall_run):
    assert next(row["销售分"] for row in mall_run["收银行"] if row["流水号"] == "S009007199254740993") == 1


# TRAP-14
def test_conflicts_quarantine_both(mall_run):
    assert [(row["行号"], row["原因码"]) for row in mall_run["隔离"] if row["流水号"] == "SM05"] == [
        (12, "CONFLICT"),
        (13, "CONFLICT"),
    ]


# TRAP-15
def test_unit_is_applied(mall_run):
    assert next(row["销售分"] for row in mall_run["收银行"] if row["流水号"] == "SM02") == 12050


def test_bom(clean):
    assert len(open_payload(b"\xef\xbb\xbf" + clean)["events"]) == 6


def test_bad_grouping():
    with pytest.raises(ValueError):
        cents("12,34.50")


# TRAP-16
def test_truncated_source(clean):
    with pytest.raises(InputError) as exc:
        open_payload(clean.rstrip()[:-2])
    assert exc.value.code == "BAD_JSON"


def test_duplicate_preserves_original(mall_rows):
    events, _, duplicates = parse_events(mall_rows["events"])
    assert [e["line"] for e in events if e["id"] == "S012"] == [5]
    assert [row["行号"] for row in duplicates] == [7]
