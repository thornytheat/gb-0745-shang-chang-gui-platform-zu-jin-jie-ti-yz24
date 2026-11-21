from collections import Counter

from app.reasons import issue


def match_refunds(events, sales):
    accum = Counter()
    accepted, isolated = [], []
    for row in events:
        if row["kind"] != "refund":
            continue
        sale = sales.get(row["origin"])
        code = None
        if not sale:
            code = "ORPHAN_REFUND"
        elif sale["shop"] != row["shop"]:
            code = "REFUND_SHOP"
        elif row["day"] < sale["day"]:
            code = "REFUND_EARLY"
        elif accum[sale["id"]] + row["cents"] > sale["cents"]:
            code = "REFUND_LIMIT"
        if code:
            isolated.append(issue(row["line"], code, row["id"]))
            continue
        accum[sale["id"]] += row["cents"]
        accepted.append({**row, "source_period": sale["day"].isoformat()[:7]})
    return accepted, isolated


def deduction_map(refunds, cutoff):
    grouped = Counter()
    for row in refunds:
        if row["day"] < cutoff:
            grouped[row["origin"]] += row["cents"]
    return grouped
