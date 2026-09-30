"""
The FedEx rate request must carry the destination country it was given.

The recipient country code used to be hard-coded to "US", so a Canadian postal
code was sent as if it were a US address.
"""
import pytest

from services import fedex_api


class _FakeResponse:
    status_code = 200

    def __init__(self):
        self.captured = None

    def json(self):
        return {"output": {"rateReplyDetails": []}}

    def raise_for_status(self):
        pass


@pytest.fixture
def captured_payload(monkeypatch):
    """Capture the payload get_rate_quote() would POST, without calling FedEx."""
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent["url"] = url
        sent["payload"] = json
        return _FakeResponse()

    monkeypatch.setattr(fedex_api, "get_oauth_token", lambda **kwargs: "fake-token")
    monkeypatch.setattr(fedex_api.SESSION, "post", fake_post)
    return sent


def _recipient(sent):
    return sent["payload"]["requestedShipment"]["recipient"]["address"]


def test_canadian_destination_is_sent_with_canadian_country_code(captured_payload):
    fedex_api.get_rate_quote(
        account_number="123456789",
        total_weight_kg=10.0,
        num_packages=1,
        destination={"postal_code": "M5V 3A8", "country_code": "CA", "state_code": "ON"},
    )
    address = _recipient(captured_payload)
    assert address["countryCode"] == "CA"
    assert address["postalCode"] == "M5V 3A8"
    assert address["stateOrProvinceCode"] == "ON"


def test_us_destination_still_defaults_to_us(captured_payload):
    fedex_api.get_rate_quote(
        account_number="123456789",
        total_weight_kg=10.0,
        num_packages=1,
        destination={"postal_code": "90001"},
    )
    assert _recipient(captured_payload)["countryCode"] == "US"


def test_zip_lookup_is_skipped_for_non_us_destinations(monkeypatch, captured_payload):
    """zippopotam's /us/ endpoint can't answer for Canada, so don't ask it."""
    called = []
    monkeypatch.setattr(
        fedex_api, "lookup_zip_code",
        lambda city, state: called.append((city, state)) or "99999",
    )

    fedex_api.get_rate_quote(
        account_number="123456789",
        total_weight_kg=10.0,
        num_packages=1,
        destination={"postal_code": "", "country_code": "CA", "city": "Toronto", "state_code": "ON"},
    )

    assert called == []
    assert _recipient(captured_payload)["postalCode"] == ""


def test_zip_lookup_still_runs_for_us_destinations(monkeypatch, captured_payload):
    monkeypatch.setattr(fedex_api, "lookup_zip_code", lambda city, state: "90001")

    fedex_api.get_rate_quote(
        account_number="123456789",
        total_weight_kg=10.0,
        num_packages=1,
        destination={"postal_code": "", "city": "Los Angeles", "state_code": "CA"},
    )

    assert _recipient(captured_payload)["postalCode"] == "90001"
