"""CONDUIT — Overview Page"""
import streamlit as st
from dashboard.api_client import get_stats, list_ros


def render_overview():

    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Service Intelligence
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Operations Overview
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # ── FETCH STATS ───────────────────────────────────────────────────────
    stats = get_stats()

    if not stats:
        st.error("Cannot reach API — make sure uvicorn is running on port 8000")
        return

    # ── KPI ROW 1 — RO METRICS ────────────────────────────────────────────
    st.markdown('<div class="section-header">Repair Orders</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Total ROs", f"{stats['total_ros']:,}")
    with c2:
        st.metric("Open", stats['open_ros'],
                  delta=None)
    with c3:
        st.metric("Completed", stats['completed_ros'])
    with c4:
        st.metric("Pending Approval", stats['pending_approval'],
                  delta="Needs action" if stats['pending_approval'] > 0 else None,
                  delta_color="inverse")
    with c5:
        st.metric("EV Jobs", stats['ev_job_count'])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI ROW 2 — FINANCIAL ─────────────────────────────────────────────
    st.markdown('<div class="section-header">Financial</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric("Total Revenue",
                  f"₹{stats['total_revenue']:,.0f}")
    with c2:
        st.metric("Avg RO Value",
                  f"₹{stats['avg_ro_value']:,.0f}")
    with c3:
        st.metric("Pending POs",
                  stats['pending_pos'])
    with c4:
        st.metric("PO Value Outstanding",
                  f"₹{stats['total_po_value']:,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI ROW 3 — SYSTEM HEALTH ─────────────────────────────────────────
    st.markdown('<div class="section-header">System Health</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        confidence_pct = f"{stats['avg_confidence']*100:.0f}%" if stats['avg_confidence'] else "N/A"
        st.metric("Avg Agent Confidence", confidence_pct)
    with c2:
        color = "🔴" if stats['critical_parts'] > 0 else "🟢"
        st.metric(f"Critical Stock Parts", stats['critical_parts'])
    with c3:
        st.metric("Low Stock Parts", stats['low_parts'])

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── RECENT ROs TABLE ──────────────────────────────────────────────────
    st.markdown('<div class="section-header">Recent Repair Orders</div>',
                unsafe_allow_html=True)

    ros = list_ros(limit=10)

    if not ros:
        st.info("No repair orders found")
        return

    import pandas as pd

    df = pd.DataFrame([
        {
            "RO ID":       ro.get("ro_id"),
            "Vehicle":     f"{ro.get('vehicle_year', '')} {ro.get('vehicle_make', '')} {ro.get('vehicle_model', '')}",
            "Fault":       ro.get("fault_classification", "—"),
            "Urgency":     ro.get("urgency", "—"),
            "Status":      ro.get("status", "—"),
            "Total (₹)":   f"₹{ro.get('final_total', 0):,.0f}" if ro.get("final_total") else "—",
        }
        for ro in ros
    ])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )