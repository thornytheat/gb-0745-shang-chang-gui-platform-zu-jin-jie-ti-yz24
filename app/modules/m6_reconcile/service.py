from collections import Counter

from app.errors import InputError
from app.modules.m1_intake.amounts import cents
from app.modules.m1_intake.service import transaction_key


def parse_statement(records):
    values = {}
    for row in records:
        try:
            shop = transaction_key(row, "shop")
            if shop in values:
                raise ValueError("柜台重复")
            values[shop] = cents(row["paid"])
        except (ValueError, KeyError, TypeError) as exc:
            raise InputError("BAD_STATEMENT", "缴款账字段有误或柜台重复") from exc
    return values


def reconcile(current, credits, statement):
    base, adjustments = Counter(), Counter()
    for row in current:
        base[row["柜台"]] += row["应计分"]
    for row in credits:
        adjustments[row["柜台"]] += row["调整分"]
    rows = []
    for shop in sorted(base.keys() | adjustments.keys() | statement.keys()):
        due = base[shop] + adjustments[shop]
        paid = statement.get(shop)
        difference = due - paid if paid is not None else None
        status = (
            "缺缴款单"
            if paid is None
            else "应补"
            if difference > 0
            else "应退"
            if difference < 0
            else "已平"
        )
        rows.append(
            {
                "柜台": shop,
                "本期分": base[shop],
                "历史调整分": adjustments[shop],
                "应缴分": due,
                "实缴分": paid,
                "差额分": difference,
                "对账": status,
            }
        )
    return rows


def row_balance(received, sales, refunds, isolated, duplicates, after_cut):
    counts = {
        "收到": received,
        "销售": len(sales),
        "退单": len(refunds),
        "隔离": len(isolated),
        "重复": len(duplicates),
        "截止后": len(after_cut),
    }
    counts["差额行"] = received - sum(value for key, value in counts.items() if key != "收到")
    return counts
