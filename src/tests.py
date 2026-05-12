"""Pinned regression tests for the date-computation rules."""

from __future__ import annotations

from datetime import date

import pytest

from generate import (
    fathers_day,
    grandfathers_day,
    grandmothers_day,
    grandparents_day,
    mothers_day,
    valentines_day,
)


def _case(label, fn, year, expected):
    return pytest.param(fn, year, expected, id=f"{label}-{year}")


CASES = [
    # Valentine's Day (fixed date).
    _case("valentines", valentines_day, 2020, date(2020, 2, 14)),
    _case("valentines", valentines_day, 2026, date(2026, 2, 14)),
    _case("valentines", valentines_day, 2100, date(2100, 2, 14)),

    # Grandmothers' Day.
    _case("grandmothers", grandmothers_day, 1987, date(1987, 3, 28)),  # 1st edition (Saturday)
    _case("grandmothers", grandmothers_day, 2022, date(2022, 3, 6)),
    _case("grandmothers", grandmothers_day, 2024, date(2024, 3, 3)),
    _case("grandmothers", grandmothers_day, 2026, date(2026, 3, 1)),
    _case("grandmothers", grandmothers_day, 2027, date(2027, 3, 7)),
    _case("grandmothers", grandmothers_day, 2028, date(2028, 3, 5)),

    # Mothers' Day (includes Pentecost-shift cases).
    _case("mothers", mothers_day, 2008, date(2008, 5, 25)),
    _case("mothers", mothers_day, 2012, date(2012, 6, 3)),    # Pentecost shift
    _case("mothers", mothers_day, 2018, date(2018, 5, 27)),
    _case("mothers", mothers_day, 2023, date(2023, 6, 4)),    # Pentecost shift
    _case("mothers", mothers_day, 2025, date(2025, 5, 25)),
    _case("mothers", mothers_day, 2026, date(2026, 5, 31)),
    _case("mothers", mothers_day, 2034, date(2034, 6, 4)),    # future Pentecost shift
    _case("mothers", mothers_day, 2045, date(2045, 6, 4)),    # future Pentecost shift

    # Fathers' Day.
    _case("fathers", fathers_day, 2020, date(2020, 6, 21)),
    _case("fathers", fathers_day, 2023, date(2023, 6, 18)),
    _case("fathers", fathers_day, 2024, date(2024, 6, 16)),
    _case("fathers", fathers_day, 2025, date(2025, 6, 15)),
    _case("fathers", fathers_day, 2026, date(2026, 6, 21)),
    _case("fathers", fathers_day, 2030, date(2030, 6, 16)),

    # World Grandparents' Day.
    _case("grandparents", grandparents_day, 2021, date(2021, 7, 25)),  # 1st edition
    _case("grandparents", grandparents_day, 2022, date(2022, 7, 24)),
    _case("grandparents", grandparents_day, 2023, date(2023, 7, 23)),
    _case("grandparents", grandparents_day, 2024, date(2024, 7, 28)),
    _case("grandparents", grandparents_day, 2025, date(2025, 7, 27)),

    # Grandfathers' Day.
    _case("grandfathers", grandfathers_day, 2024, date(2024, 10, 6)),
    _case("grandfathers", grandfathers_day, 2025, date(2025, 10, 5)),
    _case("grandfathers", grandfathers_day, 2026, date(2026, 10, 4)),
    _case("grandfathers", grandfathers_day, 2027, date(2027, 10, 3)),
    _case("grandfathers", grandfathers_day, 2028, date(2028, 10, 1)),
]


@pytest.mark.parametrize(("fn", "year", "expected"), CASES)
def test_celebration_date(fn, year, expected):
    assert fn(year) == expected
