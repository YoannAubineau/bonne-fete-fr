"""Strict RFC 5545 validation of the generated .ics file."""

from __future__ import annotations

import sys
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

from icalendar import Calendar

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICS_PATH = PROJECT_ROOT / "artefacts" / "bonne-fete-fr.ics"

MAX_PROBLEMS = 20
YEAR_MIN = 1900
YEAR_MAX = 9999


def _year_of(value: object) -> int | None:
    """Return the year of `value` if it is a date or datetime, else None."""
    if isinstance(value, datetime):
        return value.year
    if isinstance(value, date_cls):
        return value.year
    return None


def main() -> int:  # noqa: C901, PLR0912, PLR0915 — linear validator; each branch reports a distinct problem.
    """Validate the generated .ics file. Return 0 on success, 1 on any problem."""
    if not ICS_PATH.exists():
        print(f"✗ file not found: {ICS_PATH}")
        return 1

    raw = ICS_PATH.read_bytes()

    try:
        cal = Calendar.from_ical(raw)
        print("✓ iCalendar parsing")
    except Exception as exc:  # noqa: BLE001 — catch-all to report cleanly.
        print(f"✗ iCalendar parsing: {exc}")
        return 1

    problems: list[str] = []

    if cal.get("prodid"):
        print("✓ PRODID present")
    else:
        problems.append("PRODID missing")
    if cal.get("version"):
        print("✓ VERSION present")
    else:
        problems.append("VERSION missing")

    uids: set[str] = set()
    duplicates: list[str] = []
    count = 0
    for component in cal.walk("VEVENT"):
        count += 1

        uid = component.get("uid")
        uid_str = str(uid) if uid is not None else f"<event #{count}>"
        if uid is None:
            problems.append(f"{uid_str}: UID missing")
        elif uid_str in uids:
            duplicates.append(uid_str)
            problems.append(f"duplicate UID: {uid_str}")
        else:
            uids.add(uid_str)

        for prop in ("summary", "dtstart", "dtend", "sequence", "dtstamp"):
            if component.get(prop) is None:
                problems.append(f"{uid_str}: property {prop.upper()} missing")

        dtstart = component.get("dtstart")
        dtend = component.get("dtend")
        if dtstart is not None and dtend is not None:
            if not (dtend.dt > dtstart.dt):
                problems.append(f"{uid_str}: DTEND ≤ DTSTART")
            year = _year_of(dtstart.dt)
            if year is None or not (YEAR_MIN <= year <= YEAR_MAX):
                problems.append(f"{uid_str}: year out of [{YEAR_MIN}, {YEAR_MAX}]")

        seq = component.get("sequence")
        if seq is not None:
            try:
                seq_int = int(seq)
                if seq_int < 0:
                    problems.append(f"{uid_str}: SEQUENCE < 0")
            except (TypeError, ValueError):
                problems.append(f"{uid_str}: SEQUENCE is not an integer")

        if len(problems) >= MAX_PROBLEMS:
            break

    print(f"✓ {count} VEVENT analyzed")
    if not duplicates:
        print(f"✓ UIDs unique ({len(uids)} distinct)")

    if problems:
        print()
        capped = min(len(problems), MAX_PROBLEMS)
        print(f"✗ {capped} problem(s) (capped at {MAX_PROBLEMS}):")
        for p in problems[:MAX_PROBLEMS]:
            print(f"  - {p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
