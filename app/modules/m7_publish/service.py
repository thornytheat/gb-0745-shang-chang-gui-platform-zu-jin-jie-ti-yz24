from time import perf_counter

from app.manifest import input_identity, manifest
from app.modules.m1_intake.reader import open_payload
from app.modules.m1_intake.service import parse_events
from app.modules.m2_contracts.service import bind_sales, version_conflicts
from app.modules.m2_contracts.versions import normalize_contracts
from app.modules.m3_calendar.month import month_window
from app.modules.m3_calendar.service import exempt_days
from app.modules.m4_tiers.service import calculate_period
from app.modules.m5_refunds.credits import deduction_map, match_refunds
from app.modules.m5_refunds.service import previous_period_credits
from app.modules.m6_reconcile.service import parse_statement, reconcile, row_balance
from app.modules.m6_reconcile.totals import summary
from app.reasons import issue


def pipeline(raw_data, period, run_id, parameters, started=None):
    """对已解析的账簿字典执行 M1–M6 全链路，生成运行结果。"""
    if started is None:
        started = perf_counter()
    start, end = month_window(period)
    contracts = normalize_contracts(raw_data["contracts"])
    exempt = exempt_days(raw_data["holidays"])
    statement = parse_statement(raw_data["statement"])
    events, isolated, duplicates = parse_events(raw_data["events"])
    after_cut = [issue(e["line"], "AFTER_CUT", e["id"]) for e in events if e["day"] >= end]
    in_cut = [e for e in events if e["day"] < end]
    sales, invalid_sales = bind_sales(contracts, in_cut)
    refunds, invalid_refunds = match_refunds(in_cut, sales)
    isolated = sorted(isolated + invalid_sales + invalid_refunds, key=lambda item: item["行号"])
    current, exceptions = calculate_period(sales, deduction_map(refunds, end), contracts, exempt, period)
    credits = previous_period_credits(sales, refunds, contracts, exempt, start, end)
    rows = reconcile(current, credits, statement)
    balance = row_balance(len(raw_data["events"]), sales, refunds, isolated, duplicates, after_cut)
    return {
        "运行清单": manifest(run_id, parameters, round((perf_counter() - started) * 1000)),
        "行数勾稽": balance,
        "金额勾稽": summary(rows),
        "柜台对账": rows,
        "分段核算": current,
        "旧期回冲": credits,
        "收银行": [
            {
                "行号": e["line"],
                "流水号": e["id"],
                "柜台": e["shop"],
                "销售日": e["day"].isoformat(),
                "销售分": e["cents"],
                "版本": e["version"],
            }
            for e in sales.values()
        ],
        "合同版本": [
            {
                "柜台": c["shop"],
                "版本": c["version"],
                "起始": c["start"].isoformat(),
                "截止": c["end"].isoformat(),
                "月保底分": c["floor"],
            }
            for c in contracts
        ],
        "合同时窗冲突": version_conflicts(contracts),
        "日历例外": exceptions,
        "隔离": isolated,
        "重复": duplicates,
        "截止后": after_cut,
        "退单证据": [
            {
                "行号": r["line"],
                "流水号": r["id"],
                "柜台": r["shop"],
                "原单号": r["origin"],
                "入账日": r["day"].isoformat(),
                "退单分": r["cents"],
            }
            for r in refunds
        ],
    }


def calculate(raw, period):
    run_id, parameters = input_identity(raw, period)
    started = perf_counter()
    return pipeline(open_payload(raw), period, run_id, parameters, started)


def run_once(store, raw, period):
    key, _ = input_identity(raw, period)
    existing = store.get(key)
    if existing is not None:
        return existing, True
    return store.save(key, calculate(raw, period))
