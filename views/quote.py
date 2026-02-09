import re
import streamlit as st
from services.product_data import (
    get_product_models,
    get_packing_options,
    calculate_shipment,
)
from services.fedex_api import get_rate_quote, parse_rate_response
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


def _parse_us_address(text: str) -> dict:
    """解析美國地址，回傳 {zip, state, city, street}"""
    result = {"zip": "", "state": "", "city": "", "street": ""}
    text = text.strip()
    if not text:
        return result

    # 1. Extract ZIP code (5 digits, optionally -4 digits)
    zip_match = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
    if zip_match:
        result["zip"] = zip_match.group(1)
        text = text[:zip_match.start()] + text[zip_match.end():]

    # 2. Extract state code (2-letter, case insensitive)
    for token in re.findall(r"\b([A-Za-z]{2})\b", text):
        if token.upper() in US_STATES:
            result["state"] = token.upper()
            text = re.sub(r"\b" + re.escape(token) + r"\b", "", text, count=1)
            break

    # 3. Clean up remaining text → split into street and city
    # Remove extra commas, spaces, dots
    text = re.sub(r"[,.\n]+", ",", text)
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 2:
        # Last non-empty part = city, rest = street
        result["city"] = parts[-1]
        result["street"] = ", ".join(parts[:-1])
    elif len(parts) == 1:
        result["city"] = parts[0]

    return result


def _clear_old_results_if_changed(model, quantity_sets, dest_zip, dest_state):
    """當輸入條件改變時，自動清除舊的報價結果"""
    if "last_query" not in st.session_state:
        return
    q = st.session_state["last_query"]
    if (
        q["model"] != model
        or q["quantity_sets"] != quantity_sets
        or q["dest_zip"] != dest_zip
        or q["dest_state"] != dest_state
    ):
        st.session_state.pop("last_rates", None)
        st.session_state.pop("last_query", None)


def render_quote_page(products: dict):
    st.header("國際運費報價 International Shipping Quote")

    # ── 檢查是否有預填資料（從歷史紀錄「編輯」按鈕帶入）──
    prefill = st.session_state.pop("prefill", None)
    if prefill:
        st.info("已從歷史紀錄帶入資料，請修改後重新查詢。\nData loaded from history. Please modify and re-query.")

    # ── 1. 產品 & 數量 Product & Quantity ──
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

    # 常用快選型號（排在下拉選單最前面）
    QUICK_MODELS = [
        "K51M-400-X3", "K51M-450-X3", "K51M-450-X2",
        "K51P-500-X2", "K51M-500D-X3", "K51MP-450-X2", "K51MP-450-X3",
    ]
    all_models = get_product_models(products)
    other_models = [m for m in all_models if m not in QUICK_MODELS]
    models = QUICK_MODELS + other_models

    # 預填產品型號
    model_default = None
    if prefill and prefill.get("model") in models:
        model_default = models.index(prefill["model"])

    col1, col2 = st.columns(2)
    with col1:
        model = st.selectbox(
            "產品型號 Product Model", models,
            index=model_default,
            placeholder="請選擇產品型號 Select a model",
            key="model_select",
        )
    with col2:
        quantity_sets = st.number_input(
            "數量 Quantity (sets)", min_value=1,
            value=prefill["quantity_sets"] if prefill else 1,
            step=1,
        )

    if model is None:
        st.info("請選擇產品型號 Please select a product model")
        return

    # Auto-calculate packing
    options = get_packing_options(products, model)
    if options:
        shipment = calculate_shipment(options, quantity_sets)

        col_a, col_b = st.columns(2)
        col_a.metric("箱數 Cartons", f"{shipment['num_cartons']} 箱 ctns")
        col_b.metric("總重量 Total Weight", f"{shipment['total_weight_kg']} kg")

        # 顯示裝箱明細
        breakdown_parts = []
        for b in shipment["breakdown"]:
            breakdown_parts.append(
                f"{b['count']} 箱 x {b['sets_per_carton']}sets ({b['weight_kg']}kg)"
            )
        st.caption("裝箱明細 Packing: " + " + ".join(breakdown_parts))
    else:
        st.warning("此型號無包裝資料 No packing data for this model")
        return

    st.divider()

    # ── 2. 美國目的地 US Destination ──
    st.subheader("2. 美國目的地 US Destination")

    addr_mode = st.radio(
        "輸入方式 Input Method",
        ["ZIP Code", "貼上完整地址 Paste Full Address"],
        horizontal=True,
        key="addr_mode",
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
        )
    else:
        full_addr = st.text_area(
            "貼上地址 Paste Address",
            height=80,
            placeholder="例 Example: 1234 Main St, Los Angeles, CA 90001",
        )
        if full_addr.strip():
            parsed = _parse_us_address(full_addr)
            dest_zip = parsed["zip"]
            dest_state = parsed["state"]
            dest_city = parsed["city"]
            dest_street = parsed["street"]
            # 顯示解析結果
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

    st.divider()

    # ── 3. 報價設定 Quote Settings ──
    st.subheader("3. 報價設定 Quote Settings")
    col1, col2 = st.columns(2)
    with col1:
        exchange_rate = st.number_input(
            "匯率 Exchange Rate (NTD/USD)",
            value=prefill["exchange_rate"] if prefill else float(config.DEFAULT_EXCHANGE_RATE),
            min_value=1.0,
            step=0.5,
            format="%.1f",
        )
    with col2:
        markup_percent = st.number_input(
            "加成 Markup (%)",
            value=prefill["markup_percent"] if prefill else float(config.DEFAULT_MARKUP_PERCENT),
            min_value=0.0,
            step=1.0,
            format="%.1f",
        )

    st.divider()

    # ── 當輸入改變時，自動清除舊報價結果 ──
    _clear_old_results_if_changed(model, quantity_sets, dest_zip, dest_state)

    # ── Query Button ──
    # Get account number from sidebar
    account_number = st.session_state.get("fedex_account", "")

    if st.button("查詢 FedEx 運費 Get FedEx Rates", type="primary", use_container_width=True):
        # Validation
        if not account_number:
            st.error("請在左側欄輸入 FedEx 帳號號碼（9位數）\nPlease enter FedEx Account No. (9 digits) in the sidebar")
            return
        if not dest_zip and not (dest_city and dest_state):
            if addr_mode == "ZIP Code":
                st.error("請輸入 ZIP Code\nPlease enter a ZIP Code")
            else:
                st.error("無法從地址解析出 ZIP 或 City + State，請檢查地址格式\nCould not parse ZIP or City + State from the address")
            return

        destination = {
            "postal_code": dest_zip,
            "state_code": dest_state.upper() if dest_state else "",
            "city": dest_city,
            "street": dest_street,
        }

        with st.spinner("正在查詢 FedEx 運費 Fetching FedEx rates..."):
            try:
                response = get_rate_quote(
                    account_number=account_number,
                    total_weight_kg=shipment["total_weight_kg"],
                    num_packages=shipment["num_cartons"],
                    destination=destination,
                )
                rates = parse_rate_response(response)

                if not rates:
                    st.warning("FedEx 未回傳任何運費方案，請確認地址是否正確。\nNo rates returned. Please verify the address.")
                    return

                st.session_state["last_rates"] = rates
                st.session_state["last_query"] = {
                    "model": model,
                    "quantity_sets": quantity_sets,
                    "shipment": shipment,
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

    # ── 4. 運費結果 Rate Results ──
    if "last_rates" in st.session_state and "last_query" in st.session_state:
        st.subheader("4. 運費結果 Rate Results")

        query = st.session_state["last_query"]
        rates = st.session_state["last_rates"]

        # Use current markup/exchange rate settings (allow live adjustment)
        current_exchange = exchange_rate
        current_markup = markup_percent

        for i, rate in enumerate(rates):
            cost_ntd = rate["total_charge"]
            usd_cost = cost_ntd / current_exchange if current_exchange > 0 else 0
            quoted_usd = usd_cost * (1 + current_markup / 100)
            cost_per_kg = (
                cost_ntd / query["shipment"]["total_weight_kg"]
                if query["shipment"]["total_weight_kg"] > 0
                else 0
            )

            with st.container(border=True):
                st.markdown(f"**{rate['service_name']}**")

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
                    f"儲存此報價 Save Quote",
                    key=f"save_{i}_{rate['service_type']}",
                ):
                    # 裝箱明細字串
                    packing_desc = " + ".join(
                        f"{b['count']}x{b['sets_per_carton']}sets"
                        for b in query["shipment"]["breakdown"]
                    )
                    save_quote(
                        {
                            "product_model": query["model"],
                            "packing_config": packing_desc,
                            "quantity_sets": query["quantity_sets"],
                            "num_cartons": query["shipment"]["num_cartons"],
                            "total_weight_kg": query["shipment"]["total_weight_kg"],
                            "destination_state": query["dest_state"],
                            "destination_zip": query["dest_zip"],
                            "service_type": rate["service_type"],
                            "service_name": rate["service_name"],
                            "shipping_cost_ntd": cost_ntd,
                            "exchange_rate": current_exchange,
                            "usd_cost": round(usd_cost, 2),
                            "markup_percent": current_markup,
                            "quoted_price_usd": round(quoted_usd, 2),
                            "cost_per_kg_ntd": round(cost_per_kg, 2),
                        }
                    )
                    st.success("報價已儲存! Quote saved!")
