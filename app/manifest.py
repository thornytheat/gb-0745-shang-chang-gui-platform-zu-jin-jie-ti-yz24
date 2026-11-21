import hashlib
import json
from datetime import datetime, timezone

from app.config import RULE_VERSION


def input_identity(raw, period):
    digest = hashlib.sha256(raw).hexdigest()
    parameters = {"规则": RULE_VERSION, "账期": period, "输入摘要": digest}
    encoded = json.dumps(parameters, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()[:24], parameters


def manifest(run_id, parameters, elapsed_ms):
    return {
        "批次": run_id,
        **parameters,
        "生成时间": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "处理毫秒": elapsed_ms,
        "营业时区": "Asia/Shanghai",
    }
