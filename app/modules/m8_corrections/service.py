from collections import defaultdict
from datetime import date

from app.modules.m1_intake.amounts import cents
from app.modules.m1_intake.service import transaction_key
from app.reasons import REASONS


def _reason(code):
    return {"原因码": code, "说明": REASONS[code]}


def _fallback_shop(row):
    try:
        return transaction_key(row, "shop")
    except (ValueError, KeyError, TypeError):
        return ""


def parse_correction_rows(rows):
    """逐行解析补正；结构问题进入补正隔离，不产生采信。"""
    parsed, isolated = [], []
    for line, row in enumerate(rows, 1):
        key = ""
        try:
            key = transaction_key(row, "id")
            target = transaction_key(row, "target")
            shop = transaction_key(row, "shop")
            posted = date.fromisoformat(row["day"])
            kind = row["kind"]
            if kind not in ("sale", "refund"):
                raise ValueError("kind")
            if ("amount" in row) == ("gross" in row):
                raise ValueError("amount fields")
            origin = transaction_key(row, "origin") if kind == "refund" else ""
            if kind == "sale" and str(row.get("origin", "")).strip():
                raise ValueError("sale origin")
        except (ValueError, KeyError, TypeError):
            isolated.append(
                {
                    "补正行号": line,
                    "补正单号": key,
                    "归因柜台": _fallback_shop(row),
                    **_reason("CORR_BAD_ROW"),
                }
            )
            continue
        try:
            amount = cents(row.get("amount", row.get("gross")), row.get("unit", "元"))
        except ValueError:
            isolated.append(
                {
                    "补正行号": line,
                    "补正单号": key,
                    "归因柜台": shop,
                    **_reason("BAD_CASH"),
                }
            )
            continue
        parsed.append(
            {
                "line": line,
                "id": key,
                "target": target,
                "shop": shop,
                "day": posted,
                "kind": kind,
                "cents": amount,
                "origin": origin,
            }
        )
    return parsed, isolated


def _same_content(left, right):
    return (
        left["target"],
        left["shop"],
        left["day"],
        left["kind"],
        left["cents"],
        left["origin"],
    ) == (
        right["target"],
        right["shop"],
        right["day"],
        right["kind"],
        right["cents"],
        right["origin"],
    )


def _to_raw(record):
    row = {
        "id": record["target"],
        "shop": record["shop"],
        "day": record["day"].isoformat(),
        "kind": record["kind"],
        "amount": record["cents"],
        "unit": "分",
    }
    if record["kind"] == "refund":
        row["origin"] = record["origin"]
    return row


def apply_corrections(base_data, correction_rows):
    """对原始账簿套用补正，返回修正后账簿与采信/隔离/留档决策。

    规则：只替换、不改写未被指向的原行；同一原流水至多被一条补正替换；
    原行与补正行不并存；任何单条失败都保留原行并隔离该补正。
    """
    base_events = base_data["events"]
    base_index = defaultdict(list)
    for line, row in enumerate(base_events, 1):
        base_index[str(row.get("id", ""))].append((line, row))
    id_shop = {key: _fallback_shop(rows[0][1]) for key, rows in base_index.items()}
    base_kind = {
        key: rows[0][1].get("kind") for key, rows in base_index.items()
    }

    parsed, isolated = parse_correction_rows(correction_rows)

    # 同号补正：内容一致算重传，内容不同全部隔离，均不参与采信。
    grouped = defaultdict(list)
    for record in parsed:
        grouped[record["id"]].append(record)
    duplicates, unique = [], []
    for key, versions in grouped.items():
        canonical = versions[0]
        if any(not _same_content(canonical, other) for other in versions[1:]):
            for record in versions:
                isolated.append(
                    {
                        "补正行号": record["line"],
                        "补正单号": key,
                        "归因柜台": record["shop"],
                        **_reason("CORR_CONFLICT"),
                    }
                )
            continue
        unique.append(canonical)
        for record in versions[1:]:
            duplicates.append(
                {
                    "补正行号": record["line"],
                    "补正单号": key,
                    "归因柜台": record["shop"],
                    **_reason("DUPLICATE"),
                }
            )

    # 先做单条资格校验；未通过的补正立即隔离，不占用原流水，也不影响其他补正。
    accepted, admissible = [], []

    def reject(record, code, shop):
        isolated.append(
            {
                "补正行号": record["line"],
                "补正单号": record["id"],
                "归因柜台": shop,
                **_reason(code),
            }
        )

    for record in sorted(unique, key=lambda item: item["line"]):
        target_rows = base_index.get(record["target"])
        if not target_rows:
            reject(record, "CORR_NO_TARGET", record["shop"])
            continue
        target_shop = id_shop.get(record["target"], "")
        if base_kind.get(record["target"]) != record["kind"]:
            reject(record, "CORR_KIND", target_shop)
            continue
        if target_shop != record["shop"]:
            reject(record, "CORR_SHOP", target_shop or record["shop"])
            continue
        if record["kind"] == "refund":
            origin_rows = base_index.get(record["origin"])
            if not origin_rows or base_kind.get(record["origin"]) != "sale":
                reject(record, "CORR_BAD_ORIGIN", record["shop"])
                continue
        admissible.append(record)

    # 同一原流水被多条合格补正指向：无法裁决，全部隔离，原流水只算一次。
    claims = defaultdict(list)
    for record in admissible:
        claims[record["target"]].append(record)
    contested = {target for target, items in claims.items() if len(items) > 1}
    for record in admissible:
        if record["target"] in contested:
            target_shop = id_shop.get(record["target"], "")
            reject(record, "CORR_TARGET_BUSY", target_shop or record["shop"])
            continue
        accepted.append(record)

    replaced_lines = defaultdict(list)
    replacement_by_line = {}
    for record in accepted:
        for line, _ in base_index[record["target"]]:
            replaced_lines[record["target"]].append(line)
        replacement_by_line[len(base_events) + len(replacement_by_line) + 1] = record

    corrected_events = []
    for line, row in enumerate(base_events, 1):
        if line in {n for lines in replaced_lines.values() for n in lines}:
            continue
        corrected_events.append(row)
    for line in sorted(replacement_by_line):
        corrected_events.append({**_to_raw(replacement_by_line[line]), "补行号": line})

    accepted_rows = [
        {
            "补正行号": record["line"],
            "补正单号": record["id"],
            "原流水号": record["target"],
            "柜台": record["shop"],
            "销售日": record["day"].isoformat(),
            "交易类型": record["kind"],
            "补正分": record["cents"],
            "退单原号": record["origin"],
            "替换原行": replaced_lines[record["target"]],
        }
        for record in sorted(accepted, key=lambda item: item["line"])
    ]
    archive = _archive(base_events, accepted)
    corrected = {**base_data, "events": corrected_events}
    decision = {
        "补正采信": accepted_rows,
        "补正隔离": sorted(isolated, key=lambda item: item["补正行号"]),
        "补正重传": sorted(duplicates, key=lambda item: item["补正行号"]),
        "原流水留档": archive,
    }
    return corrected, decision, id_shop


def _archive(base_events, accepted):
    target_of = {record["target"]: record["id"] for record in accepted}
    archive = []
    for line, row in enumerate(base_events, 1):
        target = str(row.get("id", ""))
        try:
            amount = cents(row.get("amount", row.get("gross")), row.get("unit", "元"))
        except (ValueError, KeyError, TypeError):
            amount = None
        archive.append(
            {
                "原行号": line,
                "原流水号": target,
                "柜台": _fallback_shop(row),
                "销售日": str(row.get("day", "")),
                "交易类型": row.get("kind", ""),
                "原金额分": amount,
                "去向": target_of.get(target, "未补正留用"),
            }
        )
    return archive
