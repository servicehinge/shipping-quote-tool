"""
Headless render tests for the destination section.

Switching the country swaps the radio's option labels, which is exactly the kind
of change that makes Streamlit raise on a stale session_state value. These run
the real widget tree rather than just the helper functions.
"""
from streamlit.testing.v1 import AppTest


def _intl_section():
    """Entry point rendered by AppTest: the International tab's destination."""
    from views.quote import _render_destination_section

    zip_, state, city, street, country = _render_destination_section(
        None, "intl", allow_international=True
    )
    import streamlit as st
    st.text(f"country={country}|zip={zip_}|state={state}")


def _domestic_section():
    """Entry point rendered by AppTest: the Domestic tab's destination."""
    from views.quote import _render_destination_section

    zip_, state, city, street, country = _render_destination_section(None, "dom")
    import streamlit as st
    st.text(f"country={country}|zip={zip_}|state={state}")


def test_international_section_offers_united_states_and_canada_by_full_name():
    at = AppTest.from_function(_intl_section).run()
    assert not at.exception

    # AppTest reports the rendered labels, which is exactly what matters here:
    # the sales team must never see a bare "CA" -- it reads as California.
    assert at.selectbox[0].options == ["United States", "Canada"]
    assert at.selectbox[0].value == "US"


def test_domestic_section_has_no_country_selector():
    at = AppTest.from_function(_domestic_section).run()
    assert not at.exception
    assert len(at.selectbox) == 0
    assert at.text[0].value.startswith("country=US|")


def test_switching_to_canada_relabels_the_postal_field_without_error():
    at = AppTest.from_function(_intl_section).run()
    assert at.radio[0].options[0] == "ZIP Code"
    assert "ZIP Code" in at.text_input[0].label

    at.selectbox[0].set_value("CA").run()

    assert not at.exception
    assert at.radio[0].options[0] == "Postal Code"
    assert "Postal Code" in at.text_input[0].label
    assert at.text[0].value.startswith("country=CA|")


def test_canadian_postal_entry_normalizes_and_derives_the_province():
    at = AppTest.from_function(_intl_section).run()
    at.selectbox[0].set_value("CA").run()

    at.text_input[0].set_value("m5v3a8").run()

    assert not at.exception
    assert at.text[0].value == "country=CA|zip=M5V 3A8|state=ON"


def test_switching_country_clears_a_postal_code_left_over_from_the_other_country():
    at = AppTest.from_function(_intl_section).run()
    at.text_input[0].set_value("90001").run()
    assert at.text[0].value == "country=US|zip=90001|state="

    at.selectbox[0].set_value("CA").run()

    assert not at.exception
    assert at.text[0].value == "country=CA|zip=|state="


def test_quick_pick_buttons_only_show_for_the_matching_country():
    at = AppTest.from_function(_intl_section).run()
    us_picks = [b.label for b in at.button]
    assert any("Mayflowers" in label for label in us_picks)

    at.selectbox[0].set_value("CA").run()

    assert not at.exception
    # Every preset destination is currently a US one, so none apply to Canada.
    assert [b.label for b in at.button] == []
