"""CONDUIT — Purchase Order Tracker"""
import streamlit as st
import pandas as pd
from dashboard.api_client import list_pos, get_po_summary, update_po_status


def render_po_tracker():
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Procurement
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Purchase Orders
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # Summary
    summary = get_po_summary()
    if summary:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total POs", summary.get("total_pos", 0))
        with c2:
            st.metric("Pending", summary.get("pending_pos", 0))
        with c3:
            st.metric("Outstanding Value",
                      f"₹{summary.get('total_po_value', 0):,.0f}")

    st.markdown("<hr>", unsafe_allow_html=True)

    # Filter
    status_filter = st.selectbox(
        "Filter",
        ["All", "RAISED", "CONFIRMED", "DELIVERED", "CANCELLED"],
    )

    status = None if status_filter == "All" else status_filter
    pos    = list_pos(status=status)

    if not pos:
        st.info("No purchase orders found")
        return

    df = pd.DataFrame([
        {
            "PO ID":       po.get("po_id"),
            "Supplier":    po.get("supplier_id"),
            "Value (₹)":   f"₹{po.get('total_value', 0):,.0f}" if po.get("total_value") else "—",
            "Status":      po.get("status", "—"),
            "Raised By":   po.get("raised_by", "—"),
            "Created":     po.get("created_at", "")[:10] if po.get("created_at") else "—",
        }
        for po in pos
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Status update
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-header">Update PO Status</div>',
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        update_po_id = st.text_input("PO ID", placeholder="PO-20260228-XXXXXX")
    with col2:
        new_status = st.selectbox(
            "New Status",
            ["CONFIRMED", "DELIVERED", "CANCELLED"],
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("UPDATE"):
            if update_po_id:
                result = update_po_status(update_po_id.strip(), new_status)
                if result:
                    st.success(f"PO updated to {new_status}")
                else:
                    st.error("Update failed")