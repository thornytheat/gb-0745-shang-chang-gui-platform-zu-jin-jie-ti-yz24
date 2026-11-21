from app.modules.m4_tiers.progressive import charge


def test_progressive_beats_flat_last_bracket(clean_run):
    row = clean_run["分段核算"][0]
    assert (row["净销售分"], row["抽成分"], row["选择"]) == (140000, 18000, "抽成")
    assert [band["计提销售分"] for band in row["档段"]] == [100000, 40000]
    assert row["抽成分"] != 140000 * 2000 // 10000


def test_floor_dominates_small_sales(mall_run):
    row = next(row for row in mall_run["分段核算"] if row["柜台"] == "002")
    assert (row["应计分"], row["选择"]) == (13000, "保底")


def test_zero_sales_still_has_floor(mall_run):
    assert any(
        row["版本"] == "N-C1" and row["净销售分"] == 0 and row["应计分"] == 15000
        for row in mall_run["分段核算"]
    )


def test_round_only_once():
    assert charge(2, [(1, 5000), (None, 5000)])[0] == 1


def test_exact_tier_edge():
    fee, detail = charge(100000, [(100000, 1000), (None, 2000)])
    assert fee == 10000
    assert len(detail) == 1


# TRAP-10
def test_half_up_precise():
    assert charge(5, [(None, 1000)])[0] == 1
