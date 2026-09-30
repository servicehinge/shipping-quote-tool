"""
Destination postal-code and address parsing for the International tab.

These cover the bug that started this work: Canadian destinations were either
rejected outright or, worse, silently priced as US shipments because a 5-digit
house number was read as a ZIP code.
"""
import pytest

from views.quote import (
    _ca_province_from_postal,
    _format_dest_state,
    _is_valid_postal,
    _normalize_postal,
    _parse_address,
)


# ── Postal code validation ────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["90001", "11238", "92123", "90001-1234"])
def test_us_zip_accepts_five_digits_and_zip_plus_four(code):
    assert _is_valid_postal(code, "US")


@pytest.mark.parametrize("code", ["9001", "900011", "M5V 3A8", "", "abcde"])
def test_us_zip_rejects_anything_else(code):
    assert not _is_valid_postal(code, "US")


@pytest.mark.parametrize("code", ["M5V 3A8", "M5V3A8", "m5v 3a8", "V6B 1A1", "H3B 2Y5"])
def test_canadian_postal_accepts_with_without_space_and_lowercase(code):
    assert _is_valid_postal(code, "CA")


@pytest.mark.parametrize(
    "code",
    [
        "90001",        # a US ZIP is not a Canadian postal code
        "D5V 3A8",      # D never appears in a Canadian postal code
        "Z5V 3A8",      # Z never leads
        "M5V 3A",       # too short
        "M5V 3A8X",     # too long
        "",
    ],
)
def test_canadian_postal_rejects_malformed(code):
    assert not _is_valid_postal(code, "CA")


def test_canadian_postal_normalizes_to_single_space_uppercase():
    assert _normalize_postal("m5v3a8", "CA") == "M5V 3A8"
    assert _normalize_postal("  M5V  3A8 ", "CA") == "M5V 3A8"


def test_us_zip_is_left_as_typed_apart_from_trimming():
    assert _normalize_postal("  90001 ", "US") == "90001"


# ── Province derivation ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "postal,province",
    [
        ("M5V 3A8", "ON"),   # Toronto
        ("V6B 1A1", "BC"),   # Vancouver
        ("H3B 2Y5", "QC"),   # Montreal
        ("T2P 1J9", "AB"),   # Calgary
        ("B3H 1A1", "NS"),   # Halifax
    ],
)
def test_province_is_derived_from_postal_first_letter(postal, province):
    assert _ca_province_from_postal(postal) == province


def test_ambiguous_x_prefix_returns_blank_rather_than_guessing():
    # X covers both NT and NU, so no province is better than the wrong one.
    assert _ca_province_from_postal("X0A 1B0") == ""


# ── Address parsing ───────────────────────────────────────────────────────

def test_us_address_parses_zip_state_city():
    parsed = _parse_address("1234 Main St, Los Angeles, CA 90001", "US")
    assert parsed["zip"] == "90001"
    assert parsed["state"] == "CA"
    assert parsed["city"] == "Los Angeles"


def test_us_address_with_five_digit_house_number_takes_the_trailing_zip():
    # Regression: the leading 12345 used to win and the quote silently priced
    # a shipment to ZIP 12345 (Schenectady NY).
    parsed = _parse_address("12345 Wilshire Blvd, Los Angeles, CA 90025", "US")
    assert parsed["zip"] == "90025"


def test_canadian_address_parses_postal_and_province():
    parsed = _parse_address("100 Queen St W, Toronto, ON M5H 2N2", "CA")
    assert parsed["zip"] == "M5H 2N2"
    assert parsed["state"] == "ON"
    assert parsed["city"] == "Toronto"


def test_canadian_address_with_five_digit_house_number_is_not_read_as_a_zip():
    # The exact shape that produced a wrong-but-plausible US rate.
    parsed = _parse_address("12345 Yonge St, Richmond Hill, ON L4E 3S3", "CA")
    assert parsed["zip"] == "L4E 3S3"
    assert parsed["state"] == "ON"


def test_canadian_address_without_province_falls_back_to_postal_prefix():
    parsed = _parse_address("100 Queen St W, Toronto M5H 2N2", "CA")
    assert parsed["zip"] == "M5H 2N2"
    assert parsed["state"] == "ON"


def test_canadian_address_drops_the_trailing_country_name():
    parsed = _parse_address("100 Queen St W, Toronto, ON M5H 2N2, Canada", "CA")
    assert parsed["zip"] == "M5H 2N2"
    assert "Canada" not in parsed["city"]
    assert "Canada" not in parsed["street"]


# ── History label (no separate country column) ────────────────────────────

def test_us_history_label_is_unchanged():
    assert _format_dest_state("CA", "US") == "CA"
    assert _format_dest_state("", "US") == ""


def test_canadian_history_label_always_spells_out_the_country():
    # "ON (CA)" would reintroduce exactly the CA/California ambiguity.
    assert _format_dest_state("ON", "CA") == "ON (Canada)"
    assert _format_dest_state("", "CA") == "(Canada)"
