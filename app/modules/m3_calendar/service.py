from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.errors import InputError
from app.modules.m1_intake.service import transaction_key
from app.modules.m2_contracts.versions import version_on
from app.modules.m3_calendar.month import days_between, month_window


def exempt_days(rows):
    try:
        return {(transaction_key(row, "shop"), date.fromisoformat(row["day"])) for row in rows}
    except (ValueError, KeyError, TypeError) as exc:
        raise InputError("BAD_HOLIDAY", "免租日期或柜台无效") from exc


def billable_days(contracts, exempt, period):
    days = Counter()
    exceptions = []
    start, end = month_window(period)
    shops = sorted({c["shop"] for c in contracts if c["start"] < end and c["end"] > start})
    for shop in shops:
        for day in days_between(start, end):
            if (shop, day) in exempt:
                exceptions.append({"柜台": shop, "日期": day.isoformat(), "状态": "免保底"})
                continue
            contract, error = version_on(contracts, shop, day)
            if error:
                exceptions.append(
                    {
                        "柜台": shop,
                        "日期": day.isoformat(),
                        "状态": "版本冲突" if error == "OVERLAP" else "合同空档",
                    }
                )
                continue
            days[(shop, contract["version"])] += 1
    return days, exceptions, (end - start).days


def prorated_floor(monthly_floor, billable, month_days):
    return int(
        (Decimal(monthly_floor) * billable / month_days).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )
