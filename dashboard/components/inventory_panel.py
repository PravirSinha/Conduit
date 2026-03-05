"""CONDUIT — Inventory Panel"""
import streamlit as st
import pandas as pd
from dashboard.api_client import list_parts, get_stock_alerts


def render_inventory():
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Stock Management
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Inventory
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # Stock alerts
    alerts = get_stock_alerts()
    if alerts:
        col1, col2 = st.columns(2)
        with col1:
            if alerts.get("critical_count", 0) > 0:
                st.markdown(f"""
                <div class="alert alert-danger">
                    ✗ {alerts['critical_count']} part(s) at CRITICAL stock level
                </div>""", unsafe_allow_html=True)
        with col2:
            if alerts.get("low_count", 0) > 0:
                st.markdown(f"""
                <div class="alert alert-warning">
                    ⚠ {alerts['low_count']} part(s) at LOW stock level
                </div>""", unsafe_allow_html=True)

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            "Stock Status",
            ["All", "healthy", "low", "critical"],
        )
    with col2:
        category_filter = st.selectbox(
            "Category",
            ["All", "Brakes", "EV Components", "Electrical",
             "Filters", "Suspension", "Engine"],
        )

    status   = None if status_filter == "All" else status_filter
    category = None if category_filter == "All" else category_filter

    parts = list_parts(status=status, category=category)

    if not parts:
        st.info("No parts found")
        return

    df = pd.DataFrame([
        {
            "Part Number":  p.get("part_number"),
            "Description":  p.get("description", "")[:50],
            "Category":     p.get("category", "—"),
            "Brand":        p.get("brand", "—"),
            "On Hand":      p.get("qty_on_hand", 0),
            "Available":    p.get("qty_available", 0),
            "Status":       p.get("stock_status", "—").upper(),
            "Price (₹)":    f"₹{p.get('sell_price', 0):,.0f}" if p.get("sell_price") else "—",
            "Bin":          p.get("bin_location", "—"),
        }
        for p in parts
    ])

    st.markdown(f"""
    <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
                color: #64748b; margin-bottom: 1rem;">
        {len(df)} parts
    </div>""", unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True, hide_index=True)