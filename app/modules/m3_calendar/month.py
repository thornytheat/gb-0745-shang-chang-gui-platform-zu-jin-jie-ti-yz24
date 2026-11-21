import re
from calendar import monthrange
from datetime import date, timedelta

from app.errors import InputError


def month_window(period):
    if not isinstance(period, str) or not re.fullmatch(r"20[0-9]{2}-(?:0[1-9]|1[0-2])", period):
        raise InputError("BAD_PERIOD", "账期须为 YYYY-MM")
    start = date.fromisoformat(period + "-01")
    return start, start + timedelta(days=monthrange(start.year, start.month)[1])


def days_between(begin, end):
    return (begin + timedelta(days=offset) for offset in range((end - begin).days))
