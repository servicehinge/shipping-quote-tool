import requests
from datetime import date, datetime, timedelta
import config


# Token cache
_token_cache = {"token": None, "expires_at": None}


def get_oauth_token(account_number=None, force_refresh=False) -> str:
    """
    取得 FedEx OAuth access token（自動快取 55 分鐘）
    帶上 account_number 以取得帳號綁定的 token
    """
    now = datetime.now()
    if (
        not force_refresh
        and _token_cache["token"]
        and _token_cache["expires_at"]
        and now < _token_cache["expires_at"]
    ):
        return _token_cache["token"]

    url = f"{config.FEDEX_BASE_URL}/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": config.FEDEX_API_KEY,
        "client_secret": config.FEDEX_SECRET_KEY,
    }
    if account_number:
        payload["account_number"] = account_number
    elif config.FEDEX_ACCOUNT_NUMBER:
        payload["account_number"] = config.FEDEX_ACCOUNT_NUMBER

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(url, data=payload, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + timedelta(seconds=data.get("expires_in", 3600) - 300)

    return _token_cache["token"]


def get_rate_quote(
    account_number: str,
    total_weight_kg: float,
    num_packages: int,
    destination: dict,
) -> dict:
    """
    查詢 FedEx 國際運費

    Args:
        account_number: FedEx 9位數帳號
        total_weight_kg: 總重量(kg)
        num_packages: 總箱數
        destination: {
            "postal_code": "90001",
            "state_code": "CA",      # 選填
            "city": "Los Angeles",   # 選填
            "street": ""             # 選填
        }

    Returns:
        FedEx API raw response dict
    """
    token = get_oauth_token(account_number=account_number)
    url = f"{config.FEDEX_BASE_URL}/rate/v1/rates/quotes"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-locale": "en_US",
    }

    # Build recipient address — always include all fields for FedEx
    recipient_address = {
        "countryCode": "US",
        "residential": False,
        "postalCode": destination.get("postal_code") or "",
        "stateOrProvinceCode": destination.get("state_code") or "",
        "city": destination.get("city") or "",
    }
    street = destination.get("street") or ""
    recipient_address["streetLines"] = [street] if street else [""]

    # Weight per package
    weight_per_pkg = round(total_weight_kg / num_packages, 2)

    # Build package line items
    package_line_items = []
    for _ in range(num_packages):
        package_line_items.append(
            {
                "subPackagingType": "BOX",
                "groupPackageCount": 1,
                "weight": {"units": "KG", "value": weight_per_pkg},
            }
        )

    payload = {
        "accountNumber": {"value": account_number},
        "rateRequestControlParameters": {
            "returnTransitTimes": True,
            "rateSortOrder": "COMMITASCENDING",
        },
        "requestedShipment": {
            "shipper": {"address": config.SENDER_ADDRESS},
            "recipient": {"address": recipient_address},
            "pickupType": "DROPOFF_AT_FEDEX_LOCATION",
            "rateRequestType": ["LIST"],
            "requestedPackageLineItems": package_line_items,
            "packagingType": "YOUR_PACKAGING",
            "totalPackageCount": num_packages,
            "shipDateStamp": date.today().isoformat(),
            "customsClearanceDetail": {
                "commodities": [
                    {
                        "description": "Door Hardware",
                        "countryOfManufacture": "TW",
                        "quantity": 1,
                        "quantityUnits": "PCS",
                        "weight": {
                            "units": "KG",
                            "value": total_weight_kg,
                        },
                        "customsValue": {
                            "amount": 100.00,
                            "currency": "USD",
                        },
                    }
                ],
            },
        },
    }

    response = requests.post(url, json=payload, headers=headers, timeout=60)

    # If 401, retry with fresh token
    if response.status_code == 401:
        token = get_oauth_token(account_number=account_number, force_refresh=True)
        headers["Authorization"] = f"Bearer {token}"
        response = requests.post(url, json=payload, headers=headers, timeout=60)

    response.raise_for_status()
    return response.json()


def parse_rate_response(response_json: dict) -> list[dict]:
    """
    解析 FedEx 運費回傳結果，同服務取最便宜的方案

    Returns:
        list of {
            "service_type": str,
            "service_name": str,
            "total_charge": float (TWD),
            "currency": str,
            "transit_days": str,
            "delivery_date": str,
        }
    """
    from datetime import datetime as dt

    raw_results = []
    rate_details = response_json.get("output", {}).get("rateReplyDetails", [])

    for detail in rate_details:
        service_type = detail.get("serviceType", "")

        # Get the best rate (ACCOUNT rate preferred over LIST)
        rated_details = detail.get("ratedShipmentDetails", [])
        best_rate = None
        for rd in rated_details:
            if rd.get("rateType") == "ACCOUNT":
                best_rate = rd
                break
        if best_rate is None and rated_details:
            best_rate = rated_details[0]
        if best_rate is None:
            continue

        total_charge = float(best_rate.get("totalNetCharge", 0))
        currency = best_rate.get("currency", "TWD")

        # Transit time from commit.dateDetail
        commit = detail.get("commit", {})
        date_detail = commit.get("dateDetail", {})
        delivery_date_str = date_detail.get("dayFormat", "")

        # Calculate transit days from delivery date
        transit_days = "N/A"
        if delivery_date_str:
            try:
                delivery_dt = dt.fromisoformat(delivery_date_str)
                days = (delivery_dt.date() - date.today()).days
                transit_days = str(days) if days > 0 else "1"
                delivery_date_str = delivery_dt.strftime("%m/%d (%a)")
            except (ValueError, TypeError):
                pass

        raw_results.append(
            {
                "service_type": service_type,
                "service_name": detail.get("serviceName", service_type),
                "total_charge": total_charge,
                "currency": currency,
                "transit_days": transit_days,
                "delivery_date": delivery_date_str,
            }
        )

    # Deduplicate: keep cheapest per service_type
    best_by_type = {}
    for r in raw_results:
        key = r["service_type"]
        if key not in best_by_type or r["total_charge"] < best_by_type[key]["total_charge"]:
            best_by_type[key] = r

    # Sort by price ascending
    return sorted(best_by_type.values(), key=lambda x: x["total_charge"])
