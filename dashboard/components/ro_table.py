"""CONDUIT — Repair Orders Table Page"""
import streamlit as st
import pandas as pd
from dashboard.api_client import list_ros


def render_ro_table():
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Records
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Repair Orders
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # Filters
    col1, col2 = st.columns([2, 4])
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "OPEN", "IN_PROGRESS", "COMPLETE"],
            format_func=lambda x: {
                "All":         "All Orders",
                "OPEN":        "Open — Awaiting Pipeline",
                "IN_PROGRESS": "In Progress — Pipeline Running",
                "COMPLETE":    "Complete — Quote Approved",
            }.get(x, x)
        )

    status = None if status_filter == "All" else status_filter
    ros    = list_ros(status=status, limit=100)

    if not ros:
        st.info("No repair orders found")
        return

    urgency_display = {
        "HIGH":               "High",
        "MEDIUM":             "Medium",
        "LOW":                "Low",
        "NEEDS_CLARIFICATION": "Needs Review",
    }
    status_display = {
        "OPEN":        "Open",
        "IN_PROGRESS": "In Progress",
        "COMPLETE":    "Complete",
        "CLOSED":      "Closed",
        "QUOTED":      "In Progress",
    }
    fault_display = {
        "BRAKE_SYSTEM":      "Brake System",
        "ELECTRICAL_SYSTEM": "Electrical",
        "ENGINE":            "Engine",
        "SUSPENSION":        "Suspension",
        "ROUTINE_SERVICE":   "Routine Service",
        "EV_SYSTEM":         "EV System",
        "UNKNOWN":           "Under Review",
    }

    df = pd.DataFrame([
        {
            "RO ID":    ro.get("ro_id"),
            "Vehicle":  f"{ro.get('vehicle_year', '')} {ro.get('vehicle_make', '')} {ro.get('vehicle_model', '')}".strip(),
            "Customer": ro.get("customer_name", "Walk-in") or "Walk-in",
            "Fault":    fault_display.get(ro.get("fault_classification", ""), ro.get("fault_classification", "—")),
            "Urgency":  urgency_display.get(ro.get("urgency", ""), ro.get("urgency", "—")),
            "Status":   status_display.get(ro.get("status", ""), ro.get("status", "—")),
            "Total (₹)": f"₹{ro.get('final_total', 0):,.0f}" if ro.get("final_total") else "—",
            "Opened":   ro.get("opened_at", "")[:10] if ro.get("opened_at") else "—",
        }
        for ro in ros
    ])

    st.markdown(f"""
    <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.75rem;
                color: #64748b; margin-bottom: 1rem;">
        {len(df)} records
    </div>""", unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True, hide_index=True)