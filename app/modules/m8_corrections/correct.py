import hashlib
import json
from time import perf_counter

from app.config import RULE_VERSION
from app.modules.m1_intake.reader import open_payload
from app.modules.m7_publish.service import pipeline
from app.modules.m8_corrections.reader import open_corrections
from app.modules.m8_corrections.service import apply_corrections
from app.modules.m6_reconcile.totals import summary


def correction_identity(base_raw, correction_raw, period):
    digest = hashlib.sha256(
        hashlib.sha256(base_raw).digest() + hashlib.sha256(correction_raw).digest()
    ).hexdigest()
    parameters = {"规则": RULE_VERSION, "账期": period, "补正摘要": digest}
    encoded = json.dumps(parameters, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:24], parameters


def _blocked_shops(run, id_shop):
    """汇总仍未解决的原账簿问题所归属的柜台。

    被拒绝的补正不改写原账簿，因此不参与出账挂起；挂起只由修正后仍存在的
    隔离行与合同交叠决定，保证补正文件里的无关差异不会拖住已核对柜台。
    """
    blocked = set()
    for row in run["隔离"]:
        shop = id_shop.get(row["流水号"])
        if shop:
            blocked.add(shop)
    for row in run["合同时窗冲突"]:
        blocked.add(row["柜台"])
    return blocked


def _bill_sections(run, blocked):
    billable, suspended, bill_rows = [], [], []
    for row in run["柜台对账"]:
        if row["柜台"] in blocked:
            suspended.append(
                {
                    "柜台": row["柜台"],
                    "应缴分": row["应缴分"],
                    "实缴分": row["实缴分"],
                    "状态": "挂起-未核清",
                    "原因": "修正后仍有隔离行或合同交叠",
                }
            )
        else:
            billable.append(row["柜台"])
            bill_rows.append(
                {
                    "柜台": row["柜台"],
                    "本期分": row["本期分"],
                    "历史调整分": row["历史调整分"],
                    "应缴分": row["应缴分"],
                    "实缴分": row["实缴分"],
                    "差额分": row["差额分"],
                    "对账": row["对账"],
                    "状态": "可出账",
                }
            )
    return billable, suspended, bill_rows


def calculate_corrected(base_raw, correction_raw, period):
    run_id, parameters = correction_identity(base_raw, correction_raw, period)
    started = perf_counter()
    base_data = open_payload(base_raw)
    correction_rows = open_corrections(correction_raw)
    corrected_data, decision, id_shop = apply_corrections(base_data, correction_rows)
    run = pipeline(corrected_data, period, run_id, parameters, started)

    blocked = _blocked_shops(run, id_shop)
    billable, suspended, bill_rows = _bill_sections(run, blocked)
    bill_totals = summary(bill_rows)

    run.update(
        {
            "补正参数": {
                "原账簿摘要": hashlib.sha256(base_raw).hexdigest(),
                "补正文件摘要": hashlib.sha256(correction_raw).hexdigest(),
                "补正收到行": len(correction_rows),
                "采信": len(decision["补正采信"]),
                "隔离": len(decision["补正隔离"]),
                "重传": len(decision["补正重传"]),
            },
            **decision,
            "柜台出账": [
                {
                    "柜台": shop,
                    "出账状态": "可出账" if shop in billable else "挂起",
                }
                for shop in sorted({row["柜台"] for row in run["柜台对账"]})
            ],
            "正式账单": bill_rows,
            "正式账单合计": bill_totals,
            "挂起柜台": suspended,
        }
    )
    return run


def run_correction(store, base_raw, correction_raw, period):
    key, _ = correction_identity(base_raw, correction_raw, period)
    existing = store.get(key)
    if existing is not None:
        return existing, True
    return store.save(key, calculate_corrected(base_raw, correction_raw, period))
