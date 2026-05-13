"""Coverage tests for the helpers, serializer, parser, builder and README writer."""
# pyright: basic, reportAttributeAccessIssue=false
# Test scaffolding relies on pytest fixtures whose type stubs are not strict-mode
# friendly (e.g. MonkeyPatch.setattr returning Any); basic mode is appropriate.

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from icalendar import Calendar

import generate
from generate import (
    FROZEN_DTSTAMP,
    FUTURE_YEARS,
    MIN_START_YEAR,
    OBSERVANCES,
    PreviousEvent,
    build_events,
    easter,
    escape_ical_text,
    fold_line,
    format_english_date,
    next_occurrences,
    nth_sunday,
    read_previous,
    render_next_dates_markdown,
    serialize_calendar,
    significant_lines,
    vevent_lines,
    write_ics,
    write_readme,
)

if TYPE_CHECKING:
    from pathlib import Path

# --- Date helpers ---

EASTER_CASES = [
    (1950, date(1950, 4, 9)),
    (1987, date(1987, 4, 19)),
    (2008, date(2008, 3, 23)),
    (2020, date(2020, 4, 12)),
    (2024, date(2024, 3, 31)),
    (2025, date(2025, 4, 20)),
    (2026, date(2026, 4, 5)),
    (2038, date(2038, 4, 25)),
]


@pytest.mark.parametrize(("year", "expected"), EASTER_CASES)
def test_easter(year: int, expected: date) -> None:
    """Easter Sunday matches well-known pinned dates."""
    assert easter(year) == expected


NTH_SUNDAY_CASES = [
    (2025, 6, 1, date(2025, 6, 1)),
    (2025, 6, 2, date(2025, 6, 8)),
    (2025, 6, 3, date(2025, 6, 15)),
    (2025, 6, 4, date(2025, 6, 22)),
    (2025, 6, -1, date(2025, 6, 29)),
    (2025, 12, -1, date(2025, 12, 28)),
]


@pytest.mark.parametrize(("year", "month", "n", "expected"), NTH_SUNDAY_CASES)
def test_nth_sunday(year: int, month: int, n: int, expected: date) -> None:
    """nth_sunday returns the expected Sunday for supported `n` values."""
    assert nth_sunday(year, month, n) == expected


@pytest.mark.parametrize("bad_n", [0, 5, -2, -10, 100])
def test_nth_sunday_invalid_n(bad_n: int) -> None:
    """nth_sunday rejects unsupported `n` values."""
    with pytest.raises(ValueError, match="Unsupported nth"):
        nth_sunday(2025, 6, bad_n)


# --- iCalendar serialization ---

ESCAPE_CASES = [
    ("", ""),
    ("plain", "plain"),
    ("a;b", "a\\;b"),
    ("a,b", "a\\,b"),
    ("a\nb", "a\\nb"),
    ("a\\b", "a\\\\b"),
    # Combined: backslash is doubled first, then the other separators are
    # prefixed with a single backslash. The final newline becomes a literal `\n`.
    ("a;b,c\nd\\e", "a\\;b\\,c\\nd\\\\e"),
]


@pytest.mark.parametrize(("raw", "expected"), ESCAPE_CASES)
def test_escape_ical_text(raw: str, expected: str) -> None:
    """RFC 5545 §3.3.11 escapes are applied to every reserved character."""
    assert escape_ical_text(raw) == expected


def test_vevent_lines_structure() -> None:
    """vevent_lines produces a 10-line VEVENT in the documented order."""
    obs = OBSERVANCES[0]  # saint-valentin
    lines = vevent_lines(obs, 2025, date(2025, 2, 14), sequence=3)
    assert len(lines) == 10
    assert lines[0] == "BEGIN:VEVENT"
    assert lines[-1] == "END:VEVENT"
    assert lines[1] == f"UID:{obs.key}-2025@bonne-fete-fr"
    assert lines[2] == f"DTSTAMP:{FROZEN_DTSTAMP}"
    assert lines[3] == "SEQUENCE:3"
    assert lines[4] == "DTSTART;VALUE=DATE:20250214"
    assert lines[5] == "DTEND;VALUE=DATE:20250215"
    assert lines[6].startswith("SUMMARY:")
    assert lines[7].startswith("DESCRIPTION:")
    assert lines[8] == "TRANSP:TRANSPARENT"


def test_significant_lines_strips_dtstamp_and_sequence() -> None:
    """significant_lines drops DTSTAMP and SEQUENCE but keeps every other line."""
    lines = [
        "BEGIN:VEVENT",
        "UID:test",
        "DTSTAMP:20250101T000000Z",
        "SEQUENCE:42",
        "SUMMARY:hi",
        "END:VEVENT",
    ]
    assert significant_lines(lines) == [
        "BEGIN:VEVENT",
        "UID:test",
        "SUMMARY:hi",
        "END:VEVENT",
    ]


def test_fold_line_short_unchanged() -> None:
    """A line within the 75-octet budget is returned unchanged."""
    line = "SHORT:value"
    assert fold_line(line) == line


def test_fold_line_long_ascii() -> None:
    """A long ASCII line folds with CRLF + space continuation."""
    line = "X" * 200
    folded = fold_line(line)
    parts = folded.split("\r\n")
    assert len(parts) > 1
    assert not parts[0].startswith(" ")
    for part in parts[1:]:
        assert part.startswith(" ")
    rebuilt = parts[0] + "".join(p[1:] for p in parts[1:])
    assert rebuilt == line
    for part in parts:
        assert len(part.encode("utf-8")) <= 75


def test_fold_line_preserves_utf8_codepoints() -> None:
    """Multi-byte UTF-8 sequences are never split mid-codepoint."""
    # Position the 2-byte 'é' so it would straddle the 75-octet boundary
    # if the folder cut blindly on a byte count.
    line = "X" * 74 + "é" + "Y" * 50
    folded = fold_line(line)
    rebuilt = folded.replace("\r\n ", "")
    assert rebuilt == line
    for part in folded.split("\r\n"):
        assert len(part.encode("utf-8")) <= 75


# --- _unfold and read_previous ---

def test_unfold_handles_crlf_and_continuations() -> None:
    """_unfold normalises CRLF and joins space- or tab-prefixed continuation lines."""
    text = "BEGIN:VEVENT\r\nDESCRIPTION:long\r\n more\r\n\tand more\r\nEND:VEVENT\r\n"
    lines = generate._unfold(text)
    assert lines == [
        "BEGIN:VEVENT",
        "DESCRIPTION:longmoreand more",
        "END:VEVENT",
        "",
    ]


def test_read_previous_missing_path(tmp_path: Path) -> None:
    """A non-existent path yields an empty mapping."""
    assert read_previous(tmp_path / "nope.ics") == {}


def test_read_previous_valid_event(tmp_path: Path) -> None:
    """A well-formed VEVENT round-trips to a PreviousEvent."""
    ics = tmp_path / "test.ics"
    ics.write_text(
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:saint-valentin-2025@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:20250214\r\n"
        "DTEND;VALUE=DATE:20250215\r\n"
        "SEQUENCE:7\r\n"
        "SUMMARY:Saint-Valentin\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n",
        encoding="utf-8",
    )
    result = read_previous(ics)
    assert ("saint-valentin", 2025) in result
    prev = result[("saint-valentin", 2025)]
    assert prev.event_date == date(2025, 2, 14)
    assert prev.sequence == 7


def test_read_previous_defaults_sequence(tmp_path: Path) -> None:
    """A VEVENT with no or non-integer SEQUENCE falls back to 0."""
    ics = tmp_path / "test.ics"
    ics.write_text(
        "BEGIN:VEVENT\r\n"
        "UID:meres-2030@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:20300526\r\n"
        "SEQUENCE:not-a-number\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:peres-2030@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:20300616\r\n"
        "END:VEVENT\r\n",
        encoding="utf-8",
    )
    result = read_previous(ics)
    assert result[("meres", 2030)].sequence == 0
    assert result[("peres", 2030)].sequence == 0


MALFORMED_VEVENTS = [
    "BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20250101\r\nEND:VEVENT\r\n",
    "BEGIN:VEVENT\r\nUID:foo-2025@bonne-fete-fr\r\nEND:VEVENT\r\n",
    "BEGIN:VEVENT\r\nUID:foo-2025@elsewhere\r\n"
        "DTSTART;VALUE=DATE:20250101\r\nEND:VEVENT\r\n",
    "BEGIN:VEVENT\r\nUID:foobar@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:20250101\r\nEND:VEVENT\r\n",
    "BEGIN:VEVENT\r\nUID:foo-abcd@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:20250101\r\nEND:VEVENT\r\n",
    "BEGIN:VEVENT\r\nUID:foo-2025@bonne-fete-fr\r\n"
        "DTSTART;VALUE=DATE:nope9999\r\nEND:VEVENT\r\n",
]


@pytest.mark.parametrize("vevent", MALFORMED_VEVENTS)
def test_read_previous_skips_malformed(tmp_path: Path, vevent: str) -> None:
    """Malformed VEVENT blocks are silently skipped during parsing."""
    ics = tmp_path / "test.ics"
    ics.write_text(vevent, encoding="utf-8")
    assert read_previous(ics) == {}


# --- Event builder ---

def test_build_events_count_with_empty_previous() -> None:
    """With no previous events, build_events emits one VEVENT per (observance, year)."""
    today = date(2025, 6, 1)
    end_year = today.year + FUTURE_YEARS
    expected = sum(end_year - obs.start_year + 1 for obs in OBSERVANCES)
    events = build_events(today, {})
    assert len(events) == expected


def test_build_events_ordering() -> None:
    """Future events come first ascending; past events follow descending."""
    today = date(2025, 6, 1)
    events = build_events(today, {})
    dates = [d for d, _ in events]
    future = [d for d in dates if d >= today]
    past = [d for d in dates if d < today]
    assert dates == future + past
    assert future == sorted(future)
    assert past == sorted(past, reverse=True)


def test_build_events_sequence_zero_when_no_previous() -> None:
    """Sequence defaults to 0 for every event when previous is empty."""
    events = build_events(date(2025, 6, 1), {})
    for _, lines in events:
        seq_line = next(ln for ln in lines if ln.startswith("SEQUENCE:"))
        assert seq_line == "SEQUENCE:0"


def _find_event_lines(
    events: list[tuple[date, list[str]]],
    key: str,
    year: int,
) -> list[str]:
    """Return the VEVENT block for the given key/year in build_events output."""
    needle = f"UID:{key}-{year}@bonne-fete-fr"
    return next(lines for _, lines in events if needle in lines)


def test_build_events_preserves_sequence_when_unchanged() -> None:
    """When previous.significant matches the candidate, the prior sequence is kept."""
    today = date(2025, 6, 1)
    obs = OBSERVANCES[0]
    year = 2030
    event_date = obs.rule(year)
    candidate = vevent_lines(obs, year, event_date, sequence=0)
    prev = {
        (obs.key, year): PreviousEvent(
            event_date=event_date,
            sequence=4,
            significant=significant_lines(candidate),
        ),
    }
    events = build_events(today, prev)
    target = _find_event_lines(events, obs.key, year)
    assert "SEQUENCE:4" in target


def test_build_events_increments_sequence_on_change() -> None:
    """When the candidate's significant lines differ, sequence is prior + 1."""
    today = date(2025, 6, 1)
    obs = OBSERVANCES[0]
    year = 2030
    event_date = obs.rule(year)
    stale = vevent_lines(obs, year, event_date + timedelta(days=7), sequence=0)
    prev = {
        (obs.key, year): PreviousEvent(
            event_date=event_date + timedelta(days=7),
            sequence=4,
            significant=significant_lines(stale),
        ),
    }
    events = build_events(today, prev)
    target = _find_event_lines(events, obs.key, year)
    assert "SEQUENCE:5" in target


def test_build_events_preserves_past_date() -> None:
    """For past years, the previous event_date wins over the computed one."""
    today = date(2025, 6, 1)
    obs = OBSERVANCES[0]
    year = 2000
    historical = date(2000, 2, 15)
    stale = vevent_lines(obs, year, historical, sequence=0)
    prev = {
        (obs.key, year): PreviousEvent(
            event_date=historical,
            sequence=2,
            significant=significant_lines(stale),
        ),
    }
    events = build_events(today, prev)
    target_date, target_lines = next(
        (d, lines) for d, lines in events
        if f"UID:{obs.key}-{year}@bonne-fete-fr" in lines
    )
    assert target_date == historical
    assert "DTSTART;VALUE=DATE:20000215" in target_lines


# --- Calendar serialization and file I/O ---

def test_serialize_calendar_structure() -> None:
    """serialize_calendar wraps events with VCALENDAR header/footer and CRLF terminators."""
    today = date(2025, 6, 1)
    events = build_events(today, {})
    raw = serialize_calendar(events)
    assert raw.startswith(b"BEGIN:VCALENDAR\r\n")
    assert raw.endswith(b"END:VCALENDAR\r\n")
    text = raw.decode("utf-8")
    # Every newline must be a CRLF: no orphan LF without a preceding CR.
    for offset, ch in enumerate(text):
        if ch == "\n":
            assert offset > 0
            assert text[offset - 1] == "\r"


def test_write_ics_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """write_ics produces a parseable .ics file that read_previous can re-read."""
    out = tmp_path / "out.ics"
    monkeypatch.setattr(generate, "ICS_PATH", out)
    today = date(2025, 6, 1)
    count = write_ics(today)
    assert count > 0
    assert out.exists()
    cal = Calendar.from_ical(out.read_bytes())
    parsed_events = list(cal.walk("VEVENT"))
    assert len(parsed_events) == count
    parsed_back = read_previous(out)
    assert len(parsed_back) == count


def test_write_ics_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two consecutive write_ics calls produce byte-identical output."""
    out = tmp_path / "out.ics"
    monkeypatch.setattr(generate, "ICS_PATH", out)
    today = date(2025, 6, 1)
    write_ics(today)
    first = out.read_bytes()
    write_ics(today)
    second = out.read_bytes()
    assert first == second


# --- Markdown rendering and README writer ---

FORMAT_DATE_CASES = [
    (date(2025, 6, 1), "Sunday, June 1, 2025"),
    (date(2024, 1, 15), "Monday, January 15, 2024"),
    (date(2026, 12, 31), "Thursday, December 31, 2026"),
]


@pytest.mark.parametrize(("d", "expected"), FORMAT_DATE_CASES)
def test_format_english_date(d: date, expected: str) -> None:
    """An English-locale formatter renders weekday, month name, day, year."""
    assert format_english_date(d) == expected


def test_next_occurrences_returns_one_per_observance() -> None:
    """next_occurrences returns one entry per observance, all >= today, sorted ascending."""
    today = date(2025, 6, 10)
    results = next_occurrences(today)
    assert len(results) == len(OBSERVANCES)
    for _, d in results:
        assert d >= today
    dates = [d for _, d in results]
    assert dates == sorted(dates)


def test_render_next_dates_markdown_format() -> None:
    """render_next_dates_markdown produces one bullet line per observance."""
    today = date(2025, 6, 10)
    text = render_next_dates_markdown(today)
    lines = text.split("\n")
    assert len(lines) == len(OBSERVANCES)
    for line in lines:
        assert line.startswith("- **")
        assert "**:" in line


def test_write_readme_replaces_only_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """write_readme updates only the content between the BEGIN and END markers."""
    readme = tmp_path / "README.md"
    readme.write_text(
        "Preface text.\n"
        "<!-- BEGIN: next-dates -->\n"
        "stale content\n"
        "<!-- END: next-dates -->\n"
        "Trailing text.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(generate, "README_PATH", readme)
    write_readme(date(2025, 6, 10))
    new = readme.read_text(encoding="utf-8")
    assert new.startswith("Preface text.\n")
    assert new.endswith("Trailing text.\n")
    assert "<!-- BEGIN: next-dates -->" in new
    assert "<!-- END: next-dates -->" in new
    assert "stale content" not in new
    assert "- **" in new


# --- Catalog sanity ---

def test_observances_count_and_unique_keys() -> None:
    """The catalog declares six observances with unique keys."""
    assert len(OBSERVANCES) == 6
    keys = [o.key for o in OBSERVANCES]
    assert len(keys) == len(set(keys))


def test_observances_start_years_within_supported_range() -> None:
    """Every observance's start_year is at or after MIN_START_YEAR."""
    for obs in OBSERVANCES:
        assert obs.start_year >= MIN_START_YEAR


def test_observance_rules_return_a_date() -> None:
    """Every observance rule returns a date for an arbitrary supported year."""
    for obs in OBSERVANCES:
        result = obs.rule(2030)
        assert isinstance(result, date)
