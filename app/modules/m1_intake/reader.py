import json

from app.config import MAX_SECTION_ROWS, MAX_SOURCE_BYTES
from app.errors import InputError

SECTIONS = ("contracts", "holidays", "events", "statement")


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"字段重复 {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"不支持数值 {value}")


def open_payload(raw):
    if not raw.strip():
        raise InputError("EMPTY_FILE", "上传文件为空")
    if len(raw) > MAX_SOURCE_BYTES:
        raise InputError("TOO_LARGE", "文件超过 256 KiB")
    try:
        data = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=unique_fields, parse_constant=reject_constant
        )
    except (ValueError, RecursionError) as exc:
        raise InputError("BAD_JSON", "JSON、编码或字段无效") from exc
    if not isinstance(data, dict) or set(data) != set(SECTIONS):
        raise InputError("BAD_SECTIONS", "四个账簿字段须完整")
    for section in SECTIONS:
        if not isinstance(data[section], list) or len(data[section]) > MAX_SECTION_ROWS:
            raise InputError("BAD_SECTION", f"{section} 需要不超过 1000 行")
    return data
