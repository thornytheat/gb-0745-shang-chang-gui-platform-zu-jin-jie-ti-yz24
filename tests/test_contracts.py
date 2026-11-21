from datetime import date

import pytest
from app.errors import InputError
from app.modules.m2_contracts.service import version_conflicts
from app.modules.m2_contracts.versions import normalize_contracts, version_on


# TRAP-25
def test_overlap_not_guessed(mall_run):
    assert [(row["流水号"], row["原因码"]) for row in mall_run["隔离"] if row["流水号"] == "SM04"] == [
        ("SM04", "OVERLAP")
    ]


# TRAP-23
def test_adjacent_boundaries(mall_run):
    assert next(row["版本"] for row in mall_run["收银行"] if row["流水号"] == "SM06") == "N-D2"


def test_missing_active_version(mall_run):
    assert any(row["流水号"] == "SM08" and row["原因码"] == "NO_CONTRACT" for row in mall_run["隔离"])


def test_conflict_evidence(mall_rows):
    assert version_conflicts(normalize_contracts(mall_rows["contracts"])) == [
        {"柜台": "003", "版本甲": "N-C1", "版本乙": "N-C2", "起始": "2026-11-16", "截止": "2026-11-19"}
    ]


def test_last_day_excluded(mall_rows):
    assert version_on(normalize_contracts(mall_rows["contracts"]), "001", date(2027, 1, 1)) == (
        None,
        "NO_CONTRACT",
    )


def test_missing_unbounded_tier(mall_rows):
    mall_rows["contracts"][0]["tiers"].pop()
    with pytest.raises(InputError) as exc:
        normalize_contracts(mall_rows["contracts"])
    assert exc.value.code == "BAD_CONTRACT"
