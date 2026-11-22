import json

from app.config import MAX_CORRECTION_ROWS, MAX_SOURCE_BYTES
from app.errors import InputError
from app.modules.m1_intake.reader import unique_fields, reject_constant

CORRECTION_FIELDS = ("id", "target", "shop", "day", "kind", "amount")


def open_corrections(raw):
    """解析收银补正文件。结构损坏时抛 InputError，保留旧批次。"""
    if not raw.strip():
        raise InputError("EMPTY_FILE", "补正文件为空")
    if len(raw) > MAX_SOURCE_BYTES:
        raise InputError("TOO_LARGE", "补正文件超过 256 KiB")
    try:
        data = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=unique_fields, parse_constant=reject_constant
        )
    except (ValueError, RecursionError) as exc:
        raise InputError("BAD_JSON", "补正 JSON、编码或字段无效") from exc
    if not isinstance(data, dict) or set(data) != {"corrections"}:
        raise InputError("BAD_SECTIONS", "补正文件须仅含 corrections 区块")
    rows = data["corrections"]
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CORRECTION_ROWS:
        raise InputError("BAD_SECTION", "corrections 需要 1 至 1000 行")
    return rows
