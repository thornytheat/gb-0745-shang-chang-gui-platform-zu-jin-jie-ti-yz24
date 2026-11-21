import re
from decimal import Decimal
from unicodedata import normalize

from app.config import MISSING


def cents(raw, unit="元"):
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise ValueError("金额须为精确字符串或整数")
    text = normalize("NFKC", str(raw)).strip()
    if text.upper() in MISSING or not re.fullmatch(
        r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?", text
    ):
        raise ValueError("金额格式无效")
    if unit not in ("元", "分"):
        raise ValueError("金额单位无效")
    value = Decimal(text.replace(",", "")) * (100 if unit == "元" else 1)
    if value != value.to_integral_value() or value > 10**13:
        raise ValueError("超出精度或金额限制")
    return int(value)
