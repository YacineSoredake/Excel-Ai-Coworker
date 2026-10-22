import pytest

from app.engine.values import classify_cell, parse_date_text, parse_numeric_text, resolve_date


@pytest.mark.parametrize("text,value,kind,cur", [
    ("1 234,50", 1234.5, "number", None),
    ("1.234,50", 1234.5, "number", None),
    ("1,234.50", 1234.5, "number", None),
    ("1,234,567", 1234567.0, "number", None),
    ("3,5", 3.5, "number", None),
    ("12 500 DA", 12500.0, "currency", "DZD"),
    ("$99.90", 99.9, "currency", "USD"),
    ("1 200 DZD", 1200.0, "currency", "DZD"),
    ("15%", 0.15, "percent", None),
    ("15,5 %", 0.155, "percent", None),
    ("(1 200)", -1200.0, "number", None),
    ("-42", -42.0, "number", None),
])
def test_numeric_text(text, value, kind, cur):
    v, k, c = parse_numeric_text(text)
    assert v == pytest.approx(value) and k == kind and c == cur


@pytest.mark.parametrize("text", ["0555123456", "0555 12 34 56", "abc", "12 abc", "2026-01-05", "12/05/2026",
                                  "", "-", "1 23", "DA"])
def test_not_numeric(text):
    assert parse_numeric_text(text) is None


def test_date_text_orders():
    assert parse_date_text("25/12/2026").order == "dmy_certain"
    assert parse_date_text("12/25/2026").order == "mdy_certain"
    assert parse_date_text("03/04/2026").order == "ambiguous"
    assert parse_date_text("2026-03-04").order == "fixed"
    assert parse_date_text("31/31/2026") is None
    d = parse_date_text("03/04/2026")
    assert resolve_date(d, "dmy").month == 4 and resolve_date(d, "mdy").month == 3


def test_date_month_names_fr_en():
    assert resolve_date(parse_date_text("12 janvier 2026")).month == 1
    assert resolve_date(parse_date_text("5 août 2026")).month == 8
    assert resolve_date(parse_date_text("Mar 5, 2026")).month == 3
    assert resolve_date(parse_date_text("15 Déc. 2025")).month == 12


def test_invalid_calendar_date_resolves_to_none():
    assert resolve_date(parse_date_text("31/02/2026")) is None


def test_classify_basics():
    assert classify_cell(None).kind == "empty"
    assert classify_cell("  ").kind == "empty"
    assert classify_cell("N/A").kind == "placeholder"
    assert classify_cell("#DIV/0!").kind == "error"
    assert classify_cell("Oui").kind == "boolword"
    assert classify_cell(True).kind == "bool"
    assert classify_cell(3).kind == "number"
    assert classify_cell("Alger").kind == "text"
