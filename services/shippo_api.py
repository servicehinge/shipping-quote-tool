import requests
import config

# Cache carrier account info (fetched once per session)
_carrier_account_cache: dict | None = None


def _fetch_carrier_accounts(api_token: str | None = None) -> dict:
    """
    Fetch all carrier accounts from Shippo.
    Returns { object_id: { "name": str, "active": bool } }
    """
    global _carrier_account_cache
    if _carrier_account_cache is not None:
        return _carrier_account_cache

    token = api_token or config.SHIPPO_API_TOKEN
    if not token:
        return {}

    url = "https://api.goshippo.com/carrier_accounts/"
    headers = {
        "Authorization": f"ShippoToken {token}",
        "Content-Type": "application/json",
    }

    accounts = {}
    try:
        while url:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            for acct in data.get("results", []):
                obj_id = acct.get("object_id", "")
                carrier = acct.get("carrier", "").upper()
                acct_id = acct.get("account_id", "")
                active = acct.get("active", True)
                name = f"{carrier} ({acct_id})" if acct_id else carrier
                accounts[obj_id] = {"name": name, "active": active}
            url = data.get("next")
    except Exception:
        pass

    _carrier_account_cache = accounts
    return accounts


def get_carrier_account_names(api_token: str | None = None) -> dict[str, str]:
    """Return mapping of object_id -> display name (active accounts only)."""
    accounts = _fetch_carrier_accounts(api_token)
    return {k: v["name"] for k, v in accounts.items() if v["active"]}


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
            "account_name": str,    carrier account label
        }
        Sorted by price ascending.
    """
    rates_raw = response_json.get("rates", [])
    accounts = _fetch_carrier_accounts()
    acct_names = get_carrier_account_names()
    results = []

    for rate in rates_raw:
        # Skip rates from inactive carrier accounts
        carrier_acct_id = rate.get("carrier_account", "")
        acct_info = accounts.get(carrier_acct_id)
        if acct_info and not acct_info["active"]:
            continue

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

        account_name = acct_names.get(carrier_acct_id, "")

        results.append({
            "provider": rate.get("provider", ""),
            "service_name": rate.get("servicelevel", {}).get("name", ""),
            "service_token": rate.get("servicelevel", {}).get("token", ""),
            "amount_usd": amount,
            "estimated_days": estimated_days,
            "account_name": account_name,
        })

    # Sort by price ascending
    results.sort(key=lambda r: r["amount_usd"])
    return results
