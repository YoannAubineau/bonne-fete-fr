"""Generate the .ics calendar."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Callable

# --- Configuration ---

PUBLIC_URL = "https://yoannaubineau.github.io/bonne-fete-fr/bonne-fete-fr.ics"
FUTURE_YEARS = 30
MIN_START_YEAR = 1950
FROZEN_DTSTAMP = "19500101T000000Z"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICS_PATH = PROJECT_ROOT / "artefacts" / "bonne-fete-fr.ics"
README_PATH = PROJECT_ROOT / "README.md"
README_NEXT_DATES_BEGIN = "<!-- BEGIN: next-dates -->"
README_NEXT_DATES_END = "<!-- END: next-dates -->"


# --- Date helpers ---


def easter(year: int) -> date:
    """Easter Sunday via the Meeus/Jones/Butcher Gregorian computus."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 — variable names match Meeus's published formula.
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_sunday(year: int, month: int, n: int) -> date:
    """Return the n-th Sunday of the month. n in {1, 2, 3, 4, -1 (last)}."""
    if n == -1:
        last = date(year, 12, 31) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
        # weekday(): Monday=0, Sunday=6
        offset_back = (last.weekday() - 6) % 7
        return last - timedelta(days=offset_back)
    if n in (1, 2, 3, 4):
        first = date(year, month, 1)
        offset_forward = (6 - first.weekday()) % 7
        first_sunday = first + timedelta(days=offset_forward)
        return first_sunday + timedelta(weeks=n - 1)
    raise ValueError(f"Unsupported nth: {n}")


# --- Celebration rules ---


def valentines_day(year: int) -> date:
    return date(year, 2, 14)


def grandmothers_day(year: int) -> date:
    # First edition was Saturday 28 March 1987 (last Saturday of the month).
    if year == 1987:
        return date(1987, 3, 28)
    return nth_sunday(year, 3, 1)


def mothers_day(year: int) -> date:
    last_sunday_may = nth_sunday(year, 5, -1)
    pentecost = easter(year) + timedelta(days=49)
    if last_sunday_may == pentecost:
        return nth_sunday(year, 6, 1)
    return last_sunday_may


def fathers_day(year: int) -> date:
    return nth_sunday(year, 6, 3)


def grandparents_day(year: int) -> date:
    return nth_sunday(year, 7, 4)


def grandfathers_day(year: int) -> date:
    return nth_sunday(year, 10, 1)


# --- Celebration catalog ---


@dataclass(frozen=True)
class Celebration:
    # `key` is part of the immutable UID — never change it.
    key: str
    name: str
    start_year: int
    rule: Callable[[int], date]
    description: str


CELEBRATIONS: list[Celebration] = [
    Celebration(
        "saint-valentin",
        "Saint-Valentin",
        1950,
        valentines_day,
        "Saint-Valentin — fête des amoureux (14 février).",
    ),
    Celebration(
        "grands-meres",
        "Fête des Grands-Mères",
        1987,
        grandmothers_day,
        "Fête des Grands-Mères — 1ᵉʳ dimanche de mars.",
    ),
    Celebration(
        "meres",
        "Fête des Mères",
        1950,
        mothers_day,
        (
            "Fête des Mères — dernier dimanche de mai, "
            "ou 1ᵉʳ dimanche de juin si coïncidence avec la Pentecôte."
        ),
    ),
    Celebration(
        "peres",
        "Fête des Pères",
        1952,
        fathers_day,
        "Fête des Pères — 3ᵉ dimanche de juin.",
    ),
    Celebration(
        "grands-parents",
        "Journée mondiale des grands-parents",
        2021,
        grandparents_day,
        "Journée mondiale des grands-parents — 4ᵉ dimanche de juillet.",
    ),
    Celebration(
        "grands-peres",
        "Fête des Grands-Pères",
        2008,
        grandfathers_day,
        "Fête des Grands-Pères — 1ᵉʳ dimanche d'octobre.",
    ),
]


# --- iCalendar serialization ---

CALENDAR_HEADER = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Bonne Fete//Calendrier des fetes affectives FR//FR",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Bonne Fête (France)",
    (
        "X-WR-CALDESC:Dates annuelles des fêtes affectives en France — "
        "Saint-Valentin\\, fêtes des mères\\, pères\\, grands-mères\\, "
        "grands-pères\\, et Journée mondiale des grands-parents."
    ),
    "X-WR-TIMEZONE:Europe/Paris",
]

CALENDAR_FOOTER = ["END:VCALENDAR"]


def escape_ical_text(s: str) -> str:
    """Escape an iCalendar TEXT value (RFC 5545 §3.3.11)."""
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def vevent_lines(celebration: Celebration, year: int, event_date: date, sequence: int) -> list[str]:
    """Ordered, unfolded lines of a single VEVENT block."""
    dtend = event_date + timedelta(days=1)
    return [
        "BEGIN:VEVENT",
        f"UID:{celebration.key}-{year}@bonne-fete-fr",
        f"DTSTAMP:{FROZEN_DTSTAMP}",
        f"SEQUENCE:{sequence}",
        f"DTSTART;VALUE=DATE:{event_date.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{dtend.strftime('%Y%m%d')}",
        f"SUMMARY:{escape_ical_text(celebration.name)}",
        f"DESCRIPTION:{escape_ical_text(celebration.description)}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]


def significant_lines(lines: list[str]) -> list[str]:
    """Lines that count for change detection (everything except DTSTAMP and SEQUENCE)."""
    return [ln for ln in lines if not ln.startswith("DTSTAMP") and not ln.startswith("SEQUENCE")]


def fold_line(line: str, max_octets: int = 75) -> str:
    """Fold a long line per RFC 5545 §3.1 (75 octets max, continuation prefixed by a space)."""
    encoded = line.encode("utf-8")
    if len(encoded) <= max_octets:
        return line
    parts: list[bytes] = []
    pos = 0
    first = True
    while pos < len(encoded):
        budget = max_octets if first else (max_octets - 1)
        end = min(pos + budget, len(encoded))
        # Never cut in the middle of a UTF-8 sequence.
        while end < len(encoded) and (encoded[end] & 0xC0) == 0x80:
            end -= 1
        chunk = encoded[pos:end]
        parts.append(chunk if first else (b" " + chunk))
        first = False
        pos = end
    return "\r\n".join(p.decode("utf-8") for p in parts)


# --- Read previous .ics (date preservation + SEQUENCE tracking) ---


@dataclass
class PreviousEvent:
    event_date: date
    sequence: int
    significant: list[str]


def _unfold(text: str) -> list[str]:
    """Normalize line endings and unfold continuation lines per RFC 5545 §3.1."""
    normalized = text.replace("\r\n", "\n")
    unfolded = normalized.replace("\n ", "").replace("\n\t", "")
    return unfolded.split("\n")


def read_previous(path: Path) -> dict[tuple[str, int], PreviousEvent]:  # noqa: C901 — single-pass RFC 5545 parser; splitting would obscure block-state logic.
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    lines = _unfold(text)
    previous: dict[tuple[str, int], PreviousEvent] = {}
    inside = False
    block: list[str] = []
    for line in lines:
        if line == "BEGIN:VEVENT":
            inside = True
            block = ["BEGIN:VEVENT"]
            continue
        if not inside:
            continue
        block.append(line)
        if line != "END:VEVENT":
            continue
        inside = False
        uid_line = next((b for b in block if b.startswith("UID:")), None)
        dtstart_line = next((b for b in block if b.startswith("DTSTART")), None)
        if uid_line is None or dtstart_line is None:
            continue
        uid = uid_line[len("UID:") :]
        if not uid.endswith("@bonne-fete-fr"):
            continue
        base = uid[: -len("@bonne-fete-fr")]
        sep = base.rfind("-")
        if sep < 0:
            continue
        key = base[:sep]
        try:
            year = int(base[sep + 1 :])
        except ValueError:
            continue
        dt_value = dtstart_line.split(":", 1)[1]
        try:
            event_date = date(int(dt_value[:4]), int(dt_value[4:6]), int(dt_value[6:8]))
        except ValueError:
            continue
        seq_line = next((b for b in block if b.startswith("SEQUENCE:")), None)
        seq = 0
        if seq_line is not None:
            try:
                seq = int(seq_line[len("SEQUENCE:") :])
            except ValueError:
                seq = 0
        previous[(key, year)] = PreviousEvent(
            event_date=event_date,
            sequence=seq,
            significant=significant_lines(block),
        )
    return previous


# --- Build VEVENTs ---


def build_events(
    today: date, previous: dict[tuple[str, int], PreviousEvent]
) -> list[tuple[date, list[str]]]:
    """Return (date, vevent_lines) tuples sorted chronologically by DTSTART."""
    end_year = today.year + FUTURE_YEARS
    events: list[tuple[date, list[str]]] = []
    for celebration in CELEBRATIONS:
        for year in range(celebration.start_year, end_year + 1):
            computed = celebration.rule(year)
            prev = previous.get((celebration.key, year))
            # Past events keep their historical date — never rewrite history.
            event_date = prev.event_date if prev is not None and computed < today else computed
            candidate = vevent_lines(celebration, year, event_date, sequence=0)
            candidate_sig = significant_lines(candidate)
            if prev is None:
                sequence = 0
            elif prev.significant == candidate_sig:
                sequence = prev.sequence
            else:
                sequence = prev.sequence + 1
            final = vevent_lines(celebration, year, event_date, sequence=sequence)
            events.append((event_date, final))
    events.sort(key=lambda x: x[0])
    return events


def serialize_calendar(events: list[tuple[date, list[str]]]) -> bytes:
    all_lines: list[str] = []
    all_lines.extend(CALENDAR_HEADER)
    for _, ev_lines in events:
        all_lines.extend(ev_lines)
    all_lines.extend(CALENDAR_FOOTER)
    folded = [fold_line(ln) for ln in all_lines]
    body = "\r\n".join(folded) + "\r\n"
    return body.encode("utf-8")


def write_ics(today: date) -> int:
    previous = read_previous(ICS_PATH)
    events = build_events(today, previous)
    ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ICS_PATH.write_bytes(serialize_calendar(events))
    return len(events)


EN_WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
EN_MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def format_english_date(d: date) -> str:
    return f"{EN_WEEKDAYS[d.weekday()]}, {EN_MONTHS[d.month - 1]} {d.day}, {d.year}"


def next_occurrences(today: date) -> list[tuple[Celebration, date]]:
    """For each celebration, the next occurrence on or after `today`, sorted chronologically."""
    result: list[tuple[Celebration, date]] = []
    for celebration in CELEBRATIONS:
        year = max(today.year, celebration.start_year)
        while True:
            d = celebration.rule(year)
            if d >= today:
                result.append((celebration, d))
                break
            year += 1
    result.sort(key=lambda x: x[1])
    return result


def render_next_dates_markdown(today: date) -> str:
    rows = next_occurrences(today)
    lines = [f"- **{celebration.name}** — {format_english_date(d)}" for celebration, d in rows]
    return "\n".join(lines)


def write_readme(today: date) -> None:
    text = README_PATH.read_text(encoding="utf-8")
    begin = text.index(README_NEXT_DATES_BEGIN) + len(README_NEXT_DATES_BEGIN)
    end = text.index(README_NEXT_DATES_END, begin)
    new_block = "\n" + render_next_dates_markdown(today) + "\n"
    README_PATH.write_text(text[:begin] + new_block + text[end:], encoding="utf-8")


def main() -> int:
    today = datetime.now(tz=ZoneInfo("Europe/Paris")).date()
    n = write_ics(today)
    write_readme(today)
    print(f"✓ wrote {n} VEVENT to {ICS_PATH.relative_to(PROJECT_ROOT)}")
    print(f"✓ updated README at {README_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
