from collections import defaultdict

from app.modules.m4_tiers.service import calculate_period
from app.modules.m5_refunds.credits import deduction_map


def previous_period_credits(sales, refunds, contracts, exempt, start, end):
    before, after = deduction_map(refunds, start), deduction_map(refunds, end)
    touched = defaultdict(list)
    for row in refunds:
        if start <= row["day"] < end and row["source_period"] < start.isoformat()[:7]:
            source = sales[row["origin"]]
            touched[row["source_period"], source["shop"], source["version"]].append(row["id"])
    before_by_period, after_by_period = {}, {}
    for period, _, _ in touched:
        if period in before_by_period:
            continue
        before_by_period[period] = bill_map(calculate_period(sales, before, contracts, exempt, period)[0])
        after_by_period[period] = bill_map(calculate_period(sales, after, contracts, exempt, period)[0])
    return [
        {
            "原账期": period,
            "柜台": shop,
            "版本": version,
            "回冲前分": before_by_period[period].get((shop, version), 0),
            "回冲后分": after_by_period[period].get((shop, version), 0),
            "调整分": after_by_period[period].get((shop, version), 0)
            - before_by_period[period].get((shop, version), 0),
            "退单号": ids,
        }
        for (period, shop, version), ids in sorted(touched.items())
    ]


def bill_map(rows):
    return {(row["柜台"], row["版本"]): row["应计分"] for row in rows}
