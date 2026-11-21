def test_prior_month_adjustment(clean_run):
    assert clean_run["旧期回冲"] == [
        {
            "原账期": "2026-10",
            "柜台": "001",
            "版本": "N-A",
            "回冲前分": 13000,
            "回冲后分": 11000,
            "调整分": -2000,
            "退单号": ["R011"],
        }
    ]


# TRAP-13
def test_out_of_order_matched(mall_run):
    assert any(row["行号"] == 1 and row["原单号"] == "S010" for row in mall_run["退单证据"])


def test_over_original_amount(mall_run):
    assert any(row["流水号"] == "RM01" and row["原因码"] == "REFUND_LIMIT" for row in mall_run["隔离"])


def test_reject_orphan(mall_run):
    assert any(row["流水号"] == "RM02" and row["原因码"] == "ORPHAN_REFUND" for row in mall_run["隔离"])


def test_reject_wrong_shop(mall_run):
    assert any(row["流水号"] == "RM03" and row["原因码"] == "REFUND_SHOP" for row in mall_run["隔离"])


def test_reject_early_refund(mall_run):
    assert any(row["流水号"] == "RM04" and row["原因码"] == "REFUND_EARLY" for row in mall_run["隔离"])


def test_month_cut_preserves_future_rows(mall_run):
    assert [row["流水号"] for row in mall_run["截止后"]] == ["SM07"]
