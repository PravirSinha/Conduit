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

    stats = get_stats()

    if not stats:
        st.error("Cannot reach API — make sure backend is running")
        return

    # ── KPI ROW 1 — RO PIPELINE STATUS ───────────────────────────────────
    st.markdown('<div class="section-header">Repair Orders</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric("Total ROs", f"{stats['total_ros']:,}")
    with c2:
        st.metric("Open", stats["open_ros"],
                  help="Created, awaiting pipeline run")
    with c3:
        st.metric("In Progress", stats.get("in_progress_ros", 0),
                  help="Pipeline running or paused for HITL review")
    with c4:
        st.metric("Complete", stats["completed_ros"],
                  help="Pipeline finished, quote approved")
    with c5:
        st.metric("EV Jobs", stats["ev_job_count"])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI ROW 2 — FINANCIAL ─────────────────────────────────────────────
    st.markdown('<div class="section-header">Financial</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        rev7 = stats.get("revenue_7d", 0) or 0
        q7   = stats.get("quotes_7d", 0) or 0
        st.metric("Revenue (Last 7 Days)",
                  f"\u20b9{rev7:,.0f}",
                  delta=f"{q7} quote(s) generated")
    with c2:
        avg_val = stats.get("avg_ro_value") or 0
        st.metric("Avg RO Value",
                  f"\u20b9{avg_val:,.0f}" if avg_val else "\u2014")
    with c3:
        st.metric("Pending POs", stats["pending_pos"])
    with c4:
        st.metric("PO Value Outstanding",
                  f"\u20b9{stats['total_po_value']:,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI ROW 3 — SYSTEM HEALTH ─────────────────────────────────────────
    st.markdown('<div class="section-header">System Health</div>',
                unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        confidence_pct = f"{stats['avg_confidence']*100:.0f}%" if stats.get("avg_confidence") else "N/A"
        st.metric("Avg Agent Confidence", confidence_pct)
    with c2:
        st.metric("Critical Stock Parts", stats["critical_parts"])
    with c3:
        st.metric("Low Stock Parts", stats["low_parts"])

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
            "Vehicle":     f"{ro.get('vehicle_year', '')} {ro.get('vehicle_make', '')} {ro.get('vehicle_model', '')}".strip(),
            "Fault":       ro.get("fault_classification", "\u2014"),
            "Urgency":     ro.get("urgency", "\u2014"),
            "Status":      ro.get("status", "\u2014"),
            "Total (\u20b9)": f"\u20b9{ro.get('final_total', 0):,.0f}" if ro.get("final_total") else "\u2014",
            "Date":        ro.get("opened_at", "")[:10] if ro.get("opened_at") else "\u2014",
        }
        for ro in ros
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)
