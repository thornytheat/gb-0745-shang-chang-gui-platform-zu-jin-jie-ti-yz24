from datetime import date

import pytest
from app.errors import InputError
from app.modules.m3_calendar.month import month_window
from app.modules.m3_calendar.service import exempt_days, prorated_floor


def test_two_distinct_exempt_days(mall_run):
    assert [
        (row["日期"], row["状态"])
        for row in mall_run["日历例外"]
        if row["柜台"] == "002" and row["状态"] == "免保底"
    ] == [("2026-11-18", "免保底"), ("2026-11-28", "免保底")]


def test_calendar_deduplicates_exemptions(mall_rows):
    assert len(exempt_days(mall_rows["holidays"])) == 2


def test_guarantee_uses_full_calendar_denominator(mall_run):
    row = next(row for row in mall_run["分段核算"] if row["柜台"] == "002")
    assert (row["计租日"], row["保底分"]) == (13, 13000)


def test_leap_month():
    assert (month_window("2028-02")[1] - month_window("2028-02")[0]).days == 29


def test_year_change():
    assert month_window("2026-12")[1] == date(2027, 1, 1)


def test_invalid_period():
    with pytest.raises(InputError) as exc:
        month_window("2026-13")
    assert exc.value.code == "BAD_PERIOD"


def test_half_cent_rounding():
    assert prorated_floor(3, 15, 30) == 2
