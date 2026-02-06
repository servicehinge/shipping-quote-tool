import streamlit as st
import pandas as pd
from services.history import load_history, export_history_excel, COLUMN_LABELS


def render_history_page():
    st.header("歷史報價紀錄")
    st.caption("自動保留 3 個月內的紀錄")

    df = load_history()

    if df.empty:
        st.info("尚無歷史紀錄")
        return

    # ── Filters ──
    col1, col2 = st.columns(2)
    with col1:
        model_options = sorted(df["product_model"].dropna().unique().tolist())
        model_filter = st.multiselect("篩選產品型號", model_options)
    with col2:
        state_options = sorted(df["destination_state"].dropna().unique().tolist())
        state_filter = st.multiselect("篩選州別", state_options)

    # Apply filters
    filtered = df.copy()
    if model_filter:
        filtered = filtered[filtered["product_model"].isin(model_filter)]
    if state_filter:
        filtered = filtered[filtered["destination_state"].isin(state_filter)]

    # ── Display ──
    if filtered.empty:
        st.info("篩選條件下無紀錄")
        return

    # Rename columns for display
    display_df = filtered.rename(columns=COLUMN_LABELS)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Summary ──
    st.subheader("統計摘要")
    col1, col2, col3 = st.columns(3)
    col1.metric("紀錄筆數", len(filtered))
    if "cost_per_kg_ntd" in filtered.columns:
        avg_cost = filtered["cost_per_kg_ntd"].astype(float).mean()
        col2.metric("平均每KG成本", f"NT$ {avg_cost:,.2f}")
    if "quoted_price_usd" in filtered.columns:
        avg_quote = filtered["quoted_price_usd"].astype(float).mean()
        col3.metric("平均報價金額", f"US$ {avg_quote:,.2f}")

    # ── Download ──
    st.divider()
    excel_bytes = export_history_excel(filtered)
    st.download_button(
        "下載 Excel",
        data=excel_bytes,
        file_name="shipping_quotes_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
