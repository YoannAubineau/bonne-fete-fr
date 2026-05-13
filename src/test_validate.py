"""Coverage tests for the RFC 5545 validator in validate.py."""
# pyright: basic, reportAttributeAccessIssue=false
# Test scaffolding relies on pytest fixtures whose type stubs are not strict-mode
# friendly (e.g. MonkeyPatch.setattr returning Any); basic mode is appropriate.

from datetime import date, datetime
from typing import TYPE_CHECKING

import pytest

import validate

if TYPE_CHECKING:
    from pathlib import Path

# --- VCALENDAR builders ---


def make_vevent(
    *,
    uid: str | None = "test-2025@bonne-fete-fr",
    dtstamp: str | None = "20250101T000000Z",
    sequence: str | None = "0",
    dtstart: str | None = "20250101",
    dtend: str | None = "20250102",
    summary: str | None = "Test event",
) -> str:
    """Build a single VEVENT block; pass None for any field to omit it."""
    lines: list[str] = ["BEGIN:VEVENT"]
    if uid is not None:
        lines.append(f"UID:{uid}")
    if dtstamp is not None:
        lines.append(f"DTSTAMP:{dtstamp}")
    if sequence is not None:
        lines.append(f"SEQUENCE:{sequence}")
    if dtstart is not None:
        lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
    if dtend is not None:
        lines.append(f"DTEND;VALUE=DATE:{dtend}")
    if summary is not None:
        lines.append(f"SUMMARY:{summary}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines) + "\r\n"


def make_vcalendar(
    body: str = "",
    *,
    version: str | None = "2.0",
    prodid: str | None = "-//Test//Test//EN",
) -> bytes:
    """Assemble a VCALENDAR wrapper around the given pre-joined VEVENT body."""
    lines: list[str] = ["BEGIN:VCALENDAR"]
    if version is not None:
        lines.append(f"VERSION:{version}")
    if prodid is not None:
        lines.append(f"PRODID:{prodid}")
    head = "\r\n".join(lines) + "\r\n"
    return (head + body + "END:VCALENDAR\r\n").encode("utf-8")


def _install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> Path:
    """Write `payload` to tmp_path and point validate.ICS_PATH at it."""
    ics = tmp_path / "test.ics"
    ics.write_bytes(payload)
    monkeypatch.setattr(validate, "ICS_PATH", ics)
    return ics


# --- _year_of ---


def test_year_of_datetime() -> None:
    """A datetime returns its year."""
    assert validate._year_of(datetime(2025, 6, 1, 12, 0, 0)) == 2025  # noqa: DTZ001


def test_year_of_date() -> None:
    """A date returns its year."""
    assert validate._year_of(date(2025, 6, 1)) == 2025


def test_year_of_other() -> None:
    """A non-date object returns None."""
    assert validate._year_of("not a date") is None
    assert validate._year_of(123) is None
    assert validate._year_of(None) is None


# --- main() happy path ---


def test_main_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A minimal-but-valid .ics passes every check and main returns 0."""
    body = (
        make_vevent()
        + make_vevent(uid="test-2026@bonne-fete-fr", dtstart="20260101", dtend="20260102")
    )
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert "✓ iCalendar parsing" in out
    assert "✓ PRODID present" in out
    assert "✓ VERSION present" in out
    assert "✓ 2 VEVENT analyzed" in out
    assert "✓ UIDs unique" in out


# --- main() failure paths ---


def test_main_file_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the file does not exist, main returns 1 with a clear message."""
    missing = tmp_path / "absent.ics"
    monkeypatch.setattr(validate, "ICS_PATH", missing)
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "✗ file not found" in out


def test_main_parsing_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When the iCalendar parser raises, main returns 1 and prints the error."""
    _install(tmp_path, monkeypatch, b"placeholder")

    def boom(_raw: bytes) -> object:
        msg = "synthetic parse failure"
        raise ValueError(msg)

    monkeypatch.setattr(validate.Calendar, "from_ical", boom)
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "✗ iCalendar parsing" in out
    assert "synthetic parse failure" in out


def test_main_missing_prodid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A calendar without PRODID is reported as a problem."""
    _install(tmp_path, monkeypatch, make_vcalendar(make_vevent(), prodid=None))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "PRODID missing" in out


def test_main_missing_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A calendar without VERSION is reported as a problem."""
    _install(tmp_path, monkeypatch, make_vcalendar(make_vevent(), version=None))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "VERSION missing" in out


def test_main_missing_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A VEVENT without UID is flagged via a synthetic placeholder identifier."""
    _install(tmp_path, monkeypatch, make_vcalendar(make_vevent(uid=None)))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "UID missing" in out


def test_main_duplicate_uid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Two VEVENTs sharing a UID are flagged as a duplicate."""
    body = make_vevent() + make_vevent()
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "duplicate UID" in out


MISSING_PROPERTY_CASES = [
    ("summary", "SUMMARY"),
    ("dtstart", "DTSTART"),
    ("dtend", "DTEND"),
    ("sequence", "SEQUENCE"),
    ("dtstamp", "DTSTAMP"),
]


@pytest.mark.parametrize(("field", "marker"), MISSING_PROPERTY_CASES)
def test_main_missing_required_property(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    marker: str,
) -> None:
    """Each required VEVENT property is reported when absent."""
    body = make_vevent(**{field: None})
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert f"property {marker} missing" in out


def test_main_dtend_not_after_dtstart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A VEVENT whose DTEND equals DTSTART is reported."""
    body = make_vevent(dtstart="20250101", dtend="20250101")
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "DTEND" in out


def test_main_year_out_of_range_below(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A DTSTART year below 1900 is rejected."""
    body = make_vevent(dtstart="18990101", dtend="18990102")
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "year out of" in out


def test_main_negative_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A negative SEQUENCE value is rejected."""
    body = make_vevent(sequence="-1")
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "SEQUENCE < 0" in out


def test_main_non_integer_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A non-integer SEQUENCE value is rejected (icalendar surfaces it as vBroken)."""
    body = make_vevent(sequence="abc")
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "SEQUENCE is not an integer" in out


def test_main_problem_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The reported problem list is capped at MAX_PROBLEMS entries."""
    # Each malformed VEVENT (only BEGIN/END) yields six problems
    # (UID + the five required-property checks), so ten of them comfortably
    # exceed the MAX_PROBLEMS=20 cap.
    body = (
        "".join(
            make_vevent(
                uid=None, dtstamp=None, sequence=None,
                dtstart=None, dtend=None, summary=None,
            )
            for _ in range(10)
        )
    )
    _install(tmp_path, monkeypatch, make_vcalendar(body))
    rc = validate.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert f"capped at {validate.MAX_PROBLEMS}" in out
    # The bullet count in the report is bounded by MAX_PROBLEMS.
    bullet_count = sum(1 for line in out.splitlines() if line.startswith("  - "))
    assert bullet_count == validate.MAX_PROBLEMS
