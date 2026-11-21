from collections import defaultdict
from datetime import date

from app.modules.m1_intake.amounts import cents
from app.reasons import issue


def transaction_key(record, field):
    value = record[field]
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 100:
        raise ValueError(field)
    return value.strip()


def parse_events(records):
    grouped = defaultdict(list)
    isolated = []
    for line, row in enumerate(records, 1):
        key = ""
        try:
            key = transaction_key(row, "id")
            shop = transaction_key(row, "shop")
            posted = date.fromisoformat(row["day"])
            kind = row["kind"]
            if kind not in ("sale", "refund"):
                raise ValueError("kind")
            if ("amount" in row) == ("gross" in row):
                raise ValueError("amount fields")
            origin = transaction_key(row, "origin") if kind == "refund" else ""
        except (ValueError, KeyError, TypeError):
            isolated.append(issue(line, "BAD_EVENT", key))
            continue
        try:
            amount = cents(row.get("amount", row.get("gross")), row.get("unit", "元"))
        except ValueError:
            isolated.append(issue(line, "BAD_CASH", key))
            continue
        grouped[key].append((line, (shop, posted, kind, amount, origin)))
    duplicates = []
    events = []
    for key, versions in grouped.items():
        if len({fields for _, fields in versions}) > 1:
            isolated.extend(issue(line, "CONFLICT", key) for line, _ in versions)
            continue
        line, (shop, posted, kind, amount, origin) = versions[0]
        events.append(
            dict(id=key, shop=shop, day=posted, kind=kind, cents=amount, origin=origin, line=line)
        )
        duplicates.extend(issue(extra, "DUPLICATE", key) for extra, _ in versions[1:])
    return sorted(events, key=lambda e: (e["day"], e["id"])), isolated, duplicates
