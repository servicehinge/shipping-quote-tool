import re
import streamlit as st
from services.product_data import (
    get_product_models,
    get_packing_options,
    calculate_shipment,
)
from services.fedex_api import get_rate_quote, parse_rate_response
from services.shippo_api import get_domestic_rates, parse_shippo_rates
from services.history import save_quote
import config

PRODUCT_DATA_URL = "https://docs.google.com/spreadsheets/d/1Bkbj1Iyi-CsSRCEABGlRmxJuvANmQuh41_4uVnHHoo0/edit?gid=214800878#gid=214800878"
WEIGHT_DATA_URL = "https://docs.google.com/spreadsheets/d/1Bkbj1Iyi-CsSRCEABGlRmxJuvANmQuh41_4uVnHHoo0/edit?gid=510415783#gid=510415783"


US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}

MAX_PRODUCTS = 5

QUICK_MODELS = [
    "K51M-400-X3", "K51M-450-X3", "K51M-450-X2",
    "K51P-500-X2", "K51M-500D-X3", "K51MP-450-X2", "K51MP-450-X3",
]


def _parse_us_address(text: str) -> dict:
    """Parse a US address, return {zip, state, city, street}"""
    result = {"zip": "", "state": "", "city": "", "street": ""}
    text = text.strip()
    if not text:
        return result

    text = re.sub(r"\b(United\s+States|USA|U\.S\.A\.?|US)\b", "", text, flags=re.IGNORECASE)

    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
    if zip_match:
        result["zip"] = zip_match.group(1)
        text = text[:zip_match.start()] + text[zip_match.end():]

    for token in re.findall(r"\b([A-Za-z]{2})\b", text):
        if token.upper() in US_STATES:
            result["state"] = token.upper()
            text = re.sub(r"\b" + re.escape(token) + r"\b", "", text, count=1)
            break

    text = re.sub(r"[,.\n]+", ",", text)
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 2:
        result["city"] = parts[-1]
        result["street"] = ", ".join(parts[:-1])
    elif len(parts) == 1:
        result["city"] = parts[0]

    return result


def _parse_prefill_products(prefill: dict) -> list:
    """Parse semicolon-separated multi-product prefill data, return [(model, qty), ...]"""
    models = [m.strip() for m in str(prefill.get("model", "")).split(";") if m.strip()]
    quantities_raw = str(prefill.get("quantity_sets", "1")).split(";")
    quantities = []
    for q in quantities_raw:
        try:
            quantities.append(int(float(q.strip())))
        except ValueError:
            quantities.append(1)
    while len(quantities) < len(models):
        quantities.append(1)
    return list(zip(models, quantities))


def _clear_old_results_if_changed(product_entries, dest_zip, dest_state, state_key):
    """Clear old results when input conditions change"""
    if state_key not in st.session_state:
        return
    q = st.session_state[state_key]
    current_key = [(e["model"], e["quantity_sets"]) for e in product_entries]
    saved_key = q.get("products_key", [])
    rates_key = state_key.replace("last_query", "last_rates")
    if (
        current_key != saved_key
        or q["dest_zip"] != dest_zip
        or q["dest_state"] != dest_state
    ):
        st.session_state.pop(rates_key, None)
        st.session_state.pop(state_key, None)


def _get_fixed_basic_cost(total_sets: int) -> tuple[float | None, bool]:
    """
    Return (fixed_cost, needs_manual_input) based on total sets.
    If total_sets > 25, returns (None, True).
    """
    for max_sets, cost in config.DOMESTIC_FIXED_COSTS:
        if total_sets <= max_sets:
            return cost, False
    return None, True


def _build_shippo_parcels(total_cartons: int, total_weight_kg: float) -> list[dict]:
    """Build Shippo parcel list from carton count and total weight."""
    weight_per_parcel = round(total_weight_kg / total_cartons, 2) if total_cartons > 0 else 0
    parcels = []
    for _ in range(total_cartons):
        parcels.append({
            "length": str(config.DEFAULT_CARTON_LENGTH_CM),
            "width": str(config.DEFAULT_CARTON_WIDTH_CM),
            "height": str(config.DEFAULT_CARTON_HEIGHT_CM),
            "distance_unit": "cm",
            "weight": str(weight_per_parcel),
            "mass_unit": "kg",
        })
    return parcels


def _render_product_section(products, prefill, prefill_products, pfx):
    """Render the shared product & quantity section.
    pfx: key prefix for unique widget keys ('intl' or 'dom').
    Returns (product_entries, total_cartons, total_weight_kg, total_sets) or None.
    """
    col_header, col_link1, col_link2 = st.columns([3, 1, 1])
    with col_header:
        st.subheader("1. 產品 & 數量 Product & Quantity")
    with col_link1:
        st.markdown(
            f'<a href="{PRODUCT_DATA_URL}" target="_blank">'
            f'<button style="margin-top:18px;padding:4px 12px;border:1px solid #ccc;border-radius:4px;background:#f0f2f6;cursor:pointer;">'
            f'重量明細編輯 Edit Weight Data</button></a>',
            unsafe_allow_html=True,
        )
    with col_link2:
        st.markdown(
            f'<a href="{WEIGHT_DATA_URL}" target="_blank">'
            f'<button style="margin-top:18px;padding:4px 12px;border:1px solid #ccc;border-radius:4px;background:#f0f2f6;cursor:pointer;">'
            f'報價紀錄 Quote Log</button></a>',
            unsafe_allow_html=True,
        )

    all_models = get_product_models(products)
    other_models = [m for m in all_models if m not in QUICK_MODELS]
    models = QUICK_MODELS + other_models

    rows_key = f"{pfx}_num_product_rows"
    if prefill_products:
        st.session_state[rows_key] = len(prefill_products)
    elif rows_key not in st.session_state:
        st.session_state[rows_key] = 1

    num_rows = st.session_state[rows_key]

    btn_col1, btn_col2, _ = st.columns([1, 1, 3])
    with btn_col1:
        if num_rows < MAX_PRODUCTS:
            if st.button("+ 新增產品 Add Product", key=f"{pfx}_add_product"):
                st.session_state[rows_key] = num_rows + 1
                st.rerun()
    with btn_col2:
        if num_rows > 1:
            if st.button("- 移除最後一項 Remove Last", key=f"{pfx}_remove_product"):
                last = num_rows - 1
                st.session_state.pop(f"{pfx}_product_{last}_model", None)
                st.session_state.pop(f"{pfx}_product_{last}_qty", None)
                st.session_state[rows_key] = num_rows - 1
                st.rerun()

    product_entries = []
    has_missing_data = False

    for i in range(num_rows):
        prefill_model_idx = None
        prefill_qty = 1
        if i < len(prefill_products):
            pf_model, pf_qty = prefill_products[i]
            if pf_model in models:
                prefill_model_idx = models.index(pf_model)
            prefill_qty = pf_qty

        col_model, col_qty = st.columns([3, 1])
        with col_model:
            model_i = st.selectbox(
                f"產品 {i+1} Product {i+1}",
                models,
                index=prefill_model_idx,
                placeholder="請選擇 Select",
                key=f"{pfx}_product_{i}_model",
            )
        with col_qty:
            qty_i = st.number_input(
                f"數量 Qty {i+1} (sets)",
                min_value=1,
                value=prefill_qty,
                step=1,
                key=f"{pfx}_product_{i}_qty",
            )

        if model_i is None:
            has_missing_data = True
            continue

        options_i = get_packing_options(products, model_i)
        if not options_i:
            st.warning(f"產品 {i+1} ({model_i}) 無包裝資料 No packing data")
            has_missing_data = True
            continue

        shipment_i = calculate_shipment(options_i, qty_i)
        product_entries.append({
            "model": model_i,
            "quantity_sets": qty_i,
            "shipment": shipment_i,
        })

        breakdown_parts = []
        for b in shipment_i["breakdown"]:
            breakdown_parts.append(
                f"{b['count']} 箱 x {b['sets_per_carton']}sets ({b['weight_kg']}kg)"
            )
        st.caption(f"　{model_i}: " + " + ".join(breakdown_parts))

    if not product_entries:
        st.info("請選擇至少一個產品型號 Please select at least one product model")
        return None

    if has_missing_data:
        return None

    total_cartons = sum(e["shipment"]["num_cartons"] for e in product_entries)
    total_weight_kg = round(sum(e["shipment"]["total_weight_kg"] for e in product_entries), 2)
    total_sets = sum(e["quantity_sets"] for e in product_entries)

    col_a, col_b = st.columns(2)
    col_a.metric("總箱數 Total Cartons", f"{total_cartons} 箱 ctns")
    col_b.metric("產品重量 Product Weight", f"{total_weight_kg} kg")

    return product_entries, total_cartons, total_weight_kg, total_sets


def _render_destination_section(prefill, pfx):
    """Render the US destination section. Returns (dest_zip, dest_state, dest_city, dest_street)."""
    addr_mode = st.radio(
        "輸入方式 Input Method",
        ["ZIP Code", "貼上完整地址 Paste Full Address"],
        horizontal=True,
        key=f"{pfx}_addr_mode",
    )

    dest_zip = ""
    dest_state = ""
    dest_city = ""
    dest_street = ""

    if addr_mode == "ZIP Code":
        dest_zip = st.text_input(
            "郵遞區號 ZIP Code",
            value=prefill["dest_zip"] if prefill else "",
            placeholder="90001",
            key=f"{pfx}_dest_zip",
        )
    else:
        full_addr = st.text_area(
            "貼上地址 Paste Address",
            height=80,
            placeholder="例 Example: 1234 Main St, Los Angeles, CA 90001",
            key=f"{pfx}_full_addr",
        )
        if full_addr.strip():
            parsed = _parse_us_address(full_addr)
            dest_zip = parsed["zip"]
            dest_state = parsed["state"]
            dest_city = parsed["city"]
            dest_street = parsed["street"]
            parts = []
            if dest_street:
                parts.append(f"Street: {dest_street}")
            if dest_city:
                parts.append(f"City: {dest_city}")
            if dest_state:
                parts.append(f"State: {dest_state}")
            if dest_zip:
                parts.append(f"ZIP: {dest_zip}")
            if parts:
                st.caption("解析結果 Parsed: " + " / ".join(parts))
            else:
                st.caption("無法解析地址 Could not parse address")

    return dest_zip, dest_state, dest_city, dest_street


def _save_quote_common(query, rate_data, shipping_type):
    """Build and save a quote record for both international and domestic."""
    entries = query["product_entries"]
    product_model_str = "; ".join(e["model"] for e in entries)
    quantity_sets_str = "; ".join(str(e["quantity_sets"]) for e in entries)
    packing_parts = []
    for e in entries:
        per_product = " + ".join(
            f"{b['count']}x{b['sets_per_carton']}sets"
            for b in e["shipment"]["breakdown"]
        )
        packing_parts.append(f"{e['model']}: {per_product}")
    packing_desc = "; ".join(packing_parts)

    record = {
        "shipping_type": shipping_type,
        "product_model": product_model_str,
        "packing_config": packing_desc,
        "quantity_sets": quantity_sets_str,
        "num_cartons": query["combined_shipment"]["num_cartons"],
        "total_weight_kg": query["combined_shipment"]["total_weight_kg"],
        "destination_state": query["dest_state"],
        "destination_zip": query["dest_zip"],
    }
    record.update(rate_data)
    save_quote(record)


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def render_quote_page(products: dict):
    tab_intl, tab_dom, tab_ocean = st.tabs([
        "\u2708\uFE0F  International  國際運費",
        "\U0001F69A  Domestic  美國國內",
        "\U0001F6A2  Projects  海運專案",
    ])

    with tab_intl:
        _render_international_flow(products)
    with tab_dom:
        _render_domestic_flow(products)
    with tab_ocean:
        _render_ocean_flow(products)


# ---------------------------------------------------------------------------
# International flow
# ---------------------------------------------------------------------------

def _render_international_flow(products: dict):
    pfx = "intl"

    prefill = st.session_state.pop("prefill", None)
    prefill_products = []
    if prefill:
        st.info("已從歷史紀錄帶入資料，請修改後重新查詢。\nData loaded from history. Please modify and re-query.")
        prefill_products = _parse_prefill_products(prefill)

    # ── 1. Product & Quantity ──
    product_result = _render_product_section(products, prefill, prefill_products, pfx)
    if product_result is None:
        return
    product_entries, total_cartons, total_weight_kg, total_sets = product_result

    extra_weight = st.number_input(
        "額外重量 Extra Weight (kg)",
        min_value=0.0,
        value=0.5,
        step=0.1,
        format="%.1f",
        key=f"{pfx}_extra_weight",
    )

    combined_weight = total_weight_kg + extra_weight
    st.metric("合計重量 Combined Weight", f"{combined_weight:.1f} kg")

    st.divider()

    # ── 2. Destination ──
    st.subheader("2. 美國目的地 US Destination")
    dest_zip, dest_state, dest_city, dest_street = _render_destination_section(prefill, pfx)

    st.divider()

    # ── 3. Quote Settings ──
    st.subheader("3. 報價設定 Quote Settings")
    col1, col2 = st.columns(2)
    with col1:
        exchange_rate = st.number_input(
            "匯率 Exchange Rate (NTD/USD)",
            value=prefill["exchange_rate"] if prefill else float(config.DEFAULT_EXCHANGE_RATE),
            min_value=1.0,
            step=0.5,
            format="%.1f",
            key=f"{pfx}_exchange_rate",
        )
    with col2:
        markup_percent = st.number_input(
            "加成 Markup (%)",
            value=prefill["markup_percent"] if prefill else float(config.DEFAULT_MARKUP_PERCENT),
            min_value=0.0,
            step=1.0,
            format="%.1f",
            key=f"{pfx}_markup_percent",
        )

    st.divider()

    # ── Clear stale results ──
    _clear_old_results_if_changed(product_entries, dest_zip, dest_state, f"{pfx}_last_query")

    # ── Query Button ──
    account_number = st.session_state.get("fedex_account", "")

    if st.button("查詢 FedEx 運費 Get FedEx Rates", type="primary", use_container_width=True, key=f"{pfx}_query_btn"):
        if not account_number:
            st.error("請在左側欄輸入 FedEx 帳號號碼（9位數）\nPlease enter FedEx Account No. (9 digits) in the sidebar")
            return
        if not dest_zip and not (dest_city and dest_state):
            st.error("請輸入 ZIP Code 或完整地址\nPlease enter a ZIP Code or full address")
            return

        destination = {
            "postal_code": dest_zip,
            "state_code": dest_state.upper() if dest_state else "",
            "city": dest_city,
            "street": dest_street,
        }

        combined_shipment = {
            "num_cartons": total_cartons,
            "total_weight_kg": combined_weight,
        }

        with st.spinner("正在查詢 FedEx 運費 Fetching FedEx rates..."):
            try:
                response = get_rate_quote(
                    account_number=account_number,
                    total_weight_kg=combined_weight,
                    num_packages=total_cartons,
                    destination=destination,
                )
                rates = parse_rate_response(response)

                if not rates:
                    st.warning("FedEx 未回傳任何運費方案，請確認地址是否正確。\nNo rates returned. Please verify the address.")
                    return

                st.session_state[f"{pfx}_last_rates"] = rates
                st.session_state[f"{pfx}_last_query"] = {
                    "shipping_type": "international",
                    "product_entries": product_entries,
                    "products_key": [(e["model"], e["quantity_sets"]) for e in product_entries],
                    "combined_shipment": combined_shipment,
                    "dest_state": dest_state,
                    "dest_zip": dest_zip,
                    "exchange_rate": exchange_rate,
                    "markup_percent": markup_percent,
                }

            except Exception as e:
                error_msg = str(e)
                st.error(f"查詢失敗 Query failed: {error_msg}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        detail = e.response.json()
                        st.json(detail)
                    except Exception:
                        st.code(e.response.text[:1000])
                return

    # ── 4. Results ──
    if f"{pfx}_last_rates" in st.session_state and f"{pfx}_last_query" in st.session_state:
        st.subheader("4. 運費結果 Rate Results")

        query = st.session_state[f"{pfx}_last_query"]
        rates = st.session_state[f"{pfx}_last_rates"]
        current_exchange = exchange_rate
        current_markup = markup_percent

        SERVICE_ORDER = {
            "FEDEX_INTERNATIONAL_PRIORITY_EXPRESS": 0,
            "INTERNATIONAL_PRIORITY": 1,
            "FEDEX_INTERNATIONAL_PRIORITY": 1,
            "INTERNATIONAL_ECONOMY": 2,
            "FEDEX_INTERNATIONAL_ECONOMY": 2,
        }
        sorted_rates = sorted(
            rates,
            key=lambda r: SERVICE_ORDER.get(r["service_type"], 99),
        )

        cost_by_type = {}
        for rate in sorted_rates:
            cost_by_type[rate["service_type"]] = rate["total_charge"]

        priority_cost = cost_by_type.get(
            "FEDEX_INTERNATIONAL_PRIORITY",
            cost_by_type.get("INTERNATIONAL_PRIORITY"),
        )
        economy_cost = cost_by_type.get(
            "FEDEX_INTERNATIONAL_ECONOMY",
            cost_by_type.get("INTERNATIONAL_ECONOMY"),
        )

        combined_weight = query["combined_shipment"]["total_weight_kg"]

        for i, rate in enumerate(sorted_rates):
            cost_ntd = rate["total_charge"]
            usd_cost = cost_ntd / current_exchange if current_exchange > 0 else 0
            quoted_usd = usd_cost * (1 + current_markup / 100)
            cost_per_kg = (
                cost_ntd / combined_weight
                if combined_weight > 0
                else 0
            )

            stype = rate["service_type"]
            is_priority_express = stype == "FEDEX_INTERNATIONAL_PRIORITY_EXPRESS"
            is_priority = stype in ("INTERNATIONAL_PRIORITY", "FEDEX_INTERNATIONAL_PRIORITY")
            is_economy = stype in ("INTERNATIONAL_ECONOMY", "FEDEX_INTERNATIONAL_ECONOMY")

            with st.container(border=True):
                if is_priority_express:
                    st.markdown(
                        f"**{rate['service_name']}**　"
                        f'<span style="background:#FF6B35;color:white;padding:2px 8px;border-radius:4px;font-size:0.85em;">'
                        f'業務報價專用</span>',
                        unsafe_allow_html=True,
                    )
                elif is_priority:
                    st.markdown(
                        f"**{rate['service_name']}**　"
                        f'<span style="background:#2196F3;color:white;padding:2px 8px;border-radius:4px;font-size:0.85em;">'
                        f'一般正式出貨使用</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f"**{rate['service_name']}**")

                if is_economy and priority_cost is not None and economy_cost is not None:
                    diff = priority_cost - economy_cost
                    if 0 < diff <= 150:
                        st.info(
                            f"與 International Priority 僅差 NT$ {diff:,.0f}，"
                            f"建議選 Priority 出貨（速度更快）"
                        )

                c1, c2, c3 = st.columns(3)
                c1.metric("運費成本 Shipping Cost", f"NT$ {cost_ntd:,.0f}")
                c2.metric("美金成本 USD Cost", f"US$ {usd_cost:,.2f}")
                c3.metric(
                    f"報價金額 Quote (+{current_markup:.0f}%)",
                    f"US$ {quoted_usd:,.2f}",
                )

                c4, c5 = st.columns(2)
                c4.metric("每KG成本 Cost/KG", f"NT$ {cost_per_kg:,.2f}")
                c5.metric("預計天數 Transit Days", rate["transit_days"])

                if st.button(
                    "儲存此報價 Save Quote",
                    key=f"save_intl_{i}_{rate['service_type']}",
                ):
                    _save_quote_common(query, {
                        "service_type": rate["service_type"],
                        "service_name": rate["service_name"],
                        "shipping_cost_ntd": cost_ntd,
                        "exchange_rate": current_exchange,
                        "usd_cost": round(usd_cost, 2),
                        "markup_percent": current_markup,
                        "quoted_price_usd": round(quoted_usd, 2),
                        "cost_per_kg_ntd": round(cost_per_kg, 2),
                    }, "international")
                    st.success("報價已儲存! Quote saved!")


# ---------------------------------------------------------------------------
# Domestic flow
# ---------------------------------------------------------------------------

def _render_domestic_flow(products: dict):
    pfx = "dom"

    prefill = st.session_state.pop("prefill_dom", None)
    prefill_products = []
    if prefill:
        st.info("已從歷史紀錄帶入資料，請修改後重新查詢。\nData loaded from history. Please modify and re-query.")
        prefill_products = _parse_prefill_products(prefill)

    # ── 1. Product & Quantity ──
    product_result = _render_product_section(products, prefill, prefill_products, pfx)
    if product_result is None:
        return
    product_entries, total_cartons, total_weight_kg, total_sets = product_result

    extra_weight = st.number_input(
        "額外重量 Extra Weight (kg)",
        min_value=0.0,
        value=0.5,
        step=0.1,
        format="%.1f",
        key=f"{pfx}_extra_weight",
    )

    combined_weight = total_weight_kg + extra_weight
    st.metric("合計重量 Combined Weight", f"{combined_weight:.1f} kg")

    st.divider()

    # ── 2. Sender ──
    st.subheader("2. 寄件地 Sender")
    sender_labels = [
        f"{name} ({info['zip']})"
        for name, info in config.DOMESTIC_SENDERS.items()
    ] + ["Custom ZIP 自訂"]

    sender_choice = st.radio(
        "寄件倉庫 Sender Warehouse",
        sender_labels,
        horizontal=True,
        key=f"{pfx}_sender_choice",
    )

    sender_address = None
    if sender_choice == "Custom ZIP 自訂":
        custom_zip = st.text_input(
            "自訂寄件 ZIP Custom Sender ZIP",
            placeholder="10001",
            key=f"{pfx}_custom_sender_zip",
        )
        sender_address = {
            "street1": "",
            "city": "",
            "state": "",
            "zip": custom_zip,
            "country": "US",
        }
    else:
        for name, info in config.DOMESTIC_SENDERS.items():
            if sender_choice.startswith(name):
                sender_address = info
                break

    st.divider()

    # ── 3. Destination ──
    st.subheader("3. 收件地 US Destination")
    dest_zip, dest_state, dest_city, dest_street = _render_destination_section(prefill, pfx)

    st.divider()

    # ── Fixed basic cost (calculated, shown inline before query) ──
    auto_fixed, needs_manual = _get_fixed_basic_cost(total_sets)
    fixed_basic_cost = 0.0

    if needs_manual:
        st.warning(
            f"總組數 {total_sets} sets 超過 25，請手動輸入固定基本費用。\n"
            f"Total sets exceed 25. Please enter the fixed basic cost manually."
        )
        fixed_basic_cost = st.number_input(
            "固定基本費用 Fixed Basic Cost (USD)",
            min_value=0.0,
            value=30.0,
            step=5.0,
            format="%.0f",
            key=f"{pfx}_manual_fixed_cost",
        )
    else:
        fixed_basic_cost = auto_fixed

    # ── Clear stale results ──
    _clear_old_results_if_changed(product_entries, dest_zip, dest_state, f"{pfx}_last_query")

    # ── Query Button ──
    if st.button("查詢 Shippo 運費 Get Domestic Rates", type="primary", use_container_width=True, key=f"{pfx}_query_btn"):
        if not sender_address or not sender_address.get("zip"):
            st.error("請選擇寄件倉庫或輸入自訂 ZIP\nPlease select a sender warehouse or enter a custom ZIP")
            return
        if not dest_zip:
            st.error("請輸入目的地 ZIP Code\nPlease enter a destination ZIP Code")
            return

        parcels = _build_shippo_parcels(total_cartons, combined_weight)

        combined_shipment = {
            "num_cartons": total_cartons,
            "total_weight_kg": combined_weight,
        }

        with st.spinner("正在查詢 Shippo 運費 Fetching domestic rates..."):
            try:
                response = get_domestic_rates(
                    sender=sender_address,
                    recipient_zip=dest_zip,
                    parcels=parcels,
                )
                rates = parse_shippo_rates(response)

                if not rates:
                    st.warning("Shippo 未回傳任何運費方案，請確認地址是否正確。\nNo rates returned. Please verify the address.")
                    return

                st.session_state[f"{pfx}_last_rates"] = rates
                st.session_state[f"{pfx}_last_query"] = {
                    "shipping_type": "domestic",
                    "product_entries": product_entries,
                    "products_key": [(e["model"], e["quantity_sets"]) for e in product_entries],
                    "combined_shipment": combined_shipment,
                    "dest_state": dest_state,
                    "dest_zip": dest_zip,
                    "total_sets": total_sets,
                    "fixed_basic_cost": fixed_basic_cost,
                    "sender_zip": sender_address.get("zip", ""),
                }

            except Exception as e:
                error_msg = str(e)
                st.error(f"查詢失敗 Query failed: {error_msg}")
                if hasattr(e, "response") and e.response is not None:
                    try:
                        detail = e.response.json()
                        st.json(detail)
                    except Exception:
                        st.code(e.response.text[:1000])
                return

    # ── 4. 運費報價 Rate Results ──
    if f"{pfx}_last_rates" in st.session_state and f"{pfx}_last_query" in st.session_state:
        st.subheader("4. 運費報價 Shipping Rates")

        query = st.session_state[f"{pfx}_last_query"]
        rates = st.session_state[f"{pfx}_last_rates"]
        effective_fixed = fixed_basic_cost

        st.caption(
            f"定價公式 Pricing: Shippo Cost × {config.DOMESTIC_MARKUP} + "
            f"${effective_fixed:.0f} (fixed, {total_sets} sets)"
        )

        for i, rate in enumerate(rates):
            shippo_cost = rate["amount_usd"]
            quoted_usd = round(shippo_cost * config.DOMESTIC_MARKUP + effective_fixed, 2)

            with st.container(border=True):
                st.markdown(f"**{rate['provider']} — {rate['service_name']}**")

                c1, c2, c3 = st.columns(3)
                c1.metric("Shippo 成本 Cost", f"US$ {shippo_cost:,.2f}")
                c2.metric("報價金額 Quoted Price", f"US$ {quoted_usd:,.2f}")
                c3.metric("預計天數 Transit Days", rate["estimated_days"])

                st.caption(
                    f"${shippo_cost:,.2f} × {config.DOMESTIC_MARKUP} + ${effective_fixed:.0f} = ${quoted_usd:,.2f}"
                )

                if st.button(
                    "儲存此報價 Save Quote",
                    key=f"save_dom_{i}_{rate['service_token']}",
                ):
                    _save_quote_common(query, {
                        "service_type": rate["service_token"],
                        "service_name": f"{rate['provider']} {rate['service_name']}",
                        "shipping_cost_ntd": 0,
                        "exchange_rate": 0,
                        "usd_cost": round(shippo_cost, 2),
                        "markup_percent": 0,
                        "quoted_price_usd": quoted_usd,
                        "cost_per_kg_ntd": 0,
                    }, "domestic")
                    st.success("報價已儲存! Quote saved!")


# ---------------------------------------------------------------------------
# Ocean (Projects) flow
# ---------------------------------------------------------------------------

def _render_ocean_flow(products: dict):
    pfx = "ocean"

    prefill = st.session_state.pop("prefill_ocean", None)
    prefill_products = []
    if prefill:
        st.info("已從歷史紀錄帶入資料，請修改後重新查詢。\nData loaded from history. Please modify and re-query.")
        prefill_products = _parse_prefill_products(prefill)

    # ── 1. Product & Quantity ──
    product_result = _render_product_section(products, prefill, prefill_products, pfx)
    if product_result is None:
        return
    product_entries, total_cartons, total_weight_kg, total_sets = product_result

    extra_weight = st.number_input(
        "額外重量 Extra Weight (kg)",
        min_value=0.0,
        value=0.5,
        step=0.1,
        format="%.1f",
        key=f"{pfx}_extra_weight",
    )

    combined_weight = total_weight_kg + extra_weight
    st.metric("合計重量 Combined Weight", f"{combined_weight:.1f} kg")

    st.divider()

    # ── 2. Destination (for record keeping) ──
    st.subheader("2. 美國目的地 US Destination")
    dest_zip, dest_state, dest_city, dest_street = _render_destination_section(prefill, pfx)

    st.divider()

    # ── 3. Cost Inputs ──
    st.subheader("3. 費用設定 Cost Inputs")

    col1, col2, col3 = st.columns(3)
    with col1:
        ocean_per_kg = st.number_input(
            "海運 Ocean ($/kg)",
            min_value=0.0,
            value=config.OCEAN_COST_PER_KG,
            step=0.05,
            format="%.2f",
            key=f"{pfx}_ocean_per_kg",
        )
    with col2:
        inland_per_kg = st.number_input(
            "內陸 Inland X ($/kg)",
            min_value=0.0,
            value=1.20,
            step=0.05,
            format="%.2f",
            key=f"{pfx}_inland_per_kg",
        )
    with col3:
        insurance = st.number_input(
            "訂單處理費 Handling Fee ($)",
            min_value=0.0,
            value=config.OCEAN_INSURANCE,
            step=10.0,
            format="%.0f",
            key=f"{pfx}_insurance",
        )

    st.divider()

    # ── 4. Instant Calculation ──
    st.subheader("4. 報價結果 Quote Result")

    combined_per_kg = ocean_per_kg + inland_per_kg
    total_shipping = combined_per_kg * combined_weight
    grand_total = total_shipping + insurance

    st.caption(
        f"公式 Formula: ({ocean_per_kg:.2f} + {inland_per_kg:.2f}) × {combined_weight:.1f} kg + 處理費 ${insurance:.0f} = **${grand_total:,.2f}**"
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("海運 Ocean $/kg", f"$ {ocean_per_kg:.2f}")
        c2.metric("內陸 Inland $/kg", f"$ {inland_per_kg:.2f}")
        c3.metric("合計 Combined $/kg", f"$ {combined_per_kg:.2f}")

        c4, c5, c6 = st.columns(3)
        c4.metric("產品重量 Product Weight", f"{total_weight_kg} kg")
        c5.metric("額外重量 Extra Weight", f"{extra_weight:.1f} kg")
        c6.metric("合計重量 Combined Weight", f"{combined_weight:.1f} kg")

        c7, c8 = st.columns(2)
        c7.metric("訂單處理費 Handling Fee", f"$ {insurance:,.0f}")
        c8.metric("總報價 Grand Total", f"US$ {grand_total:,.2f}")

    # ── Save ──
    if st.button("儲存此報價 Save Quote", type="primary", use_container_width=True, key=f"{pfx}_save_btn"):
        query = {
            "shipping_type": "ocean",
            "product_entries": product_entries,
            "combined_shipment": {
                "num_cartons": total_cartons,
                "total_weight_kg": combined_weight,
            },
            "dest_state": dest_state,
            "dest_zip": dest_zip,
        }
        _save_quote_common(query, {
            "service_type": "OCEAN_PROJECT",
            "service_name": "Ocean Shipping (Projects)",
            "shipping_cost_ntd": 0,
            "exchange_rate": 0,
            "usd_cost": round(total_shipping, 2),
            "markup_percent": 0,
            "quoted_price_usd": round(grand_total, 2),
            "cost_per_kg_ntd": 0,
            "ocean_per_kg": ocean_per_kg,
            "inland_per_kg": inland_per_kg,
            "insurance": insurance,
            "extra_weight_kg": extra_weight,
        }, "ocean")
        st.success("報價已儲存! Quote saved!")
