import streamlit as st
import pandas as pd
from services.history import load_history, export_history_excel, COLUMN_LABELS


def render_history_page():
    st.header("歷史報價紀錄 Quote History")
    st.caption("自動保留 3 個月內的紀錄 Auto-retains records from the last 3 months")

    df = load_history()

    if df.empty:
        st.info("尚無歷史紀錄 No history records yet")
        return

    # ── Filters ──
    col1, col2 = st.columns(2)
    with col1:
        model_options = sorted(df["product_model"].dropna().unique().tolist())
        model_filter = st.multiselect("篩選產品型號 Filter by Model", model_options)
    with col2:
        state_options = sorted(df["destination_state"].dropna().unique().tolist())
        state_filter = st.multiselect("篩選州別 Filter by State", state_options)

    # Apply filters
    filtered = df.copy()
    if model_filter:
        filtered = filtered[filtered["product_model"].isin(model_filter)]
    if state_filter:
        filtered = filtered[filtered["destination_state"].isin(state_filter)]

    # ── Display ──
    if filtered.empty:
        st.info("篩選條件下無紀錄 No records match the filter")
        return

    # 顯示每筆紀錄，附帶「編輯」按鈕
    st.subheader(f"共 {len(filtered)} 筆紀錄 {len(filtered)} Record(s)")

    for idx, row in filtered.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.markdown(f"**{row['product_model']}** — {row.get('packing_config', '')}")
            c2.markdown(f"{row.get('quantity_sets', '')} sets → {row.get('destination_state', '')} {row.get('destination_zip', '')}")
            c3.markdown(f"**US$ {row.get('quoted_price_usd', 0):,.2f}** ({row.get('service_name', '')})")

            with c4:
                if st.button("編輯 Edit", key=f"edit_{idx}"):
                    st.session_state["prefill"] = {
                        "model": str(row.get("product_model", "")),
                        "packing_config": str(row.get("packing_config", "")),
                        "quantity_sets": str(row.get("quantity_sets", "1")),
                        "dest_zip": str(row.get("destination_zip", "")),
                        "dest_state": str(row.get("destination_state", "")),
                        "exchange_rate": float(row.get("exchange_rate", 30)) if pd.notna(row.get("exchange_rate")) else 30.0,
                        "markup_percent": float(row.get("markup_percent", 15)) if pd.notna(row.get("markup_percent")) else 15.0,
                    }
                    st.session_state["nav_page"] = "運費報價 Quote"
                    st.rerun()

            st.caption(f"{row.get('timestamp', '')} | {row.get('service_type', '')} | NT$ {row.get('shipping_cost_ntd', 0):,.0f} | 匯率 Rate {row.get('exchange_rate', '')} | 加成 Markup {row.get('markup_percent', '')}%")

    # ── Summary 統計摘要 ──
    st.divider()
    st.subheader("統計摘要 Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("紀錄筆數 Records", len(filtered))
    if "cost_per_kg_ntd" in filtered.columns:
        avg_cost = filtered["cost_per_kg_ntd"].astype(float).mean()
        col2.metric("平均每KG成本 Avg Cost/KG", f"NT$ {avg_cost:,.2f}")
    if "quoted_price_usd" in filtered.columns:
        avg_quote = filtered["quoted_price_usd"].astype(float).mean()
        col3.metric("平均報價金額 Avg Quote", f"US$ {avg_quote:,.2f}")

    # ── Download 下載 ──
    st.divider()
    excel_bytes = export_history_excel(filtered)
    st.download_button(
        "下載 Excel Download Excel",
        data=excel_bytes,
        file_name="shipping_quotes_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
