import requests
import config


def get_domestic_rates(
    sender: dict,
    recipient_zip: str,
    parcels: list[dict],
    api_token: str | None = None,
) -> dict:
    """
    Query Shippo for domestic US shipping rates.

    Args:
        sender: Full address dict from config.DOMESTIC_SENDERS or custom
                { street1, city, state, zip, country }
        recipient_zip: US destination ZIP code
        parcels: list of { length, width, height, distance_unit, weight, mass_unit }
        api_token: Shippo API token (defaults to config value)

    Returns:
        Shippo API raw response dict
    """
    token = api_token or config.SHIPPO_API_TOKEN
    if not token:
        raise ValueError("SHIPPO_API_TOKEN is not configured")

    url = "https://api.goshippo.com/shipments/"
    headers = {
        "Authorization": f"ShippoToken {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "address_from": {
            "street1": sender.get("street1", ""),
            "city": sender.get("city", ""),
            "state": sender.get("state", ""),
            "zip": sender.get("zip", ""),
            "country": "US",
        },
        "address_to": {
            "zip": recipient_zip,
            "country": "US",
        },
        "parcels": parcels,
        "async": False,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def parse_shippo_rates(response_json: dict) -> list[dict]:
    """
    Extract and sort rates from Shippo shipment response.

    Returns:
        list of {
            "provider": str,        e.g. "USPS", "FedEx"
            "service_name": str,    e.g. "Priority Mail"
            "service_token": str,   Shippo service token
            "amount_usd": float,    Shippo cost in USD
            "estimated_days": str,  e.g. "3" or "N/A"
        }
        Sorted by price ascending.
    """
    rates_raw = response_json.get("rates", [])
    results = []

    for rate in rates_raw:
        amount_str = rate.get("amount", "0")
        try:
            amount = float(amount_str)
        except (ValueError, TypeError):
            continue

        # Skip rates with zero or negative amount
        if amount <= 0:
            continue

        estimated_days = rate.get("estimated_days") or "N/A"
        if estimated_days != "N/A":
            estimated_days = str(estimated_days)

        results.append({
            "provider": rate.get("provider", ""),
            "service_name": rate.get("servicelevel", {}).get("name", ""),
            "service_token": rate.get("servicelevel", {}).get("token", ""),
            "amount_usd": amount,
            "estimated_days": estimated_days,
        })

    # Sort by price ascending
    results.sort(key=lambda r: r["amount_usd"])
    return results
