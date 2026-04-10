"""CONDUIT — New Repair Order Page with Real SSE Streaming"""
import html as _html
import json
import os
import time
import requests
import streamlit as st

from config import INTAKE_HITL_ENABLED, TRANSACTION_HITL_ENABLED
from dashboard.api_client import submit_intake_review

API_BASE = os.environ.get("API_URL", "http://localhost:8000") + "/api"

AGENT_META = {
    "intake_agent":        {"icon": "🧠", "label": "Intake Agent",       "desc": "Semantic search + GPT-4o fault classification"},
    "inventory_agent":     {"icon": "📦", "label": "Inventory Agent",     "desc": "Stock check + atomic parts reservation"},
    "quoting_agent":       {"icon": "🧾", "label": "Quoting Agent",       "desc": "OEM + aftermarket pricing + GST"},
    "transaction_agent":   {"icon": "✅", "label": "Transaction Agent",   "desc": "Approval + reservation confirmation"},
    "replenishment_agent": {"icon": "🚚", "label": "Replenishment Agent", "desc": "Supplier scoring + PO creation"},
}


@st.cache_data(ttl=300)
def _load_demo_vins(limit: int = 3) -> list[str]:
    """Returns a small set of VINs for demo dropdown.

    Tries to read from the local DB; falls back to a few known demo VINs.
    """
    fallback = [
        "I0Y6DPBHSAHXTHV3A",
        "JH4TB2H26CC000000",
        "1HGCM82633A000000",
    ]

    try:
        from database.connection import get_session
        from database.models import Vehicle

        with get_session() as db:
            vehicles = db.query(Vehicle).limit(limit).all()

        vins = [v.vin for v in vehicles if getattr(v, "vin", None)]
        return vins or fallback
    except Exception:
        return fallback


def render_agent_step(container, agent_name, status, summary=None, elapsed=None, error_msg=None):
    meta   = AGENT_META.get(agent_name, {})
    icon   = meta.get("icon", "⚙")
    label  = meta.get("label", agent_name)
    desc   = meta.get("desc", "")

    if status == "waiting":
        color, text_color, border = "#0d0d14", "#2d3748", "#1e1e2e"
        status_html = '<span style="color:#2d3748;">○ Waiting</span>'

    elif status == "running":
        color, text_color, border = "#1a1207", "#f97316", "#f97316"
        status_html = '<span style="color:#f97316;">⟳ Running...</span>'

    elif status == "complete":
        color, text_color, border = "#0a1a0a", "#22c55e", "#22c55e"
        elapsed_str = f"{elapsed:.1f}s" if elapsed else ""
        status_html = f'<span style="color:#22c55e;">✓ {elapsed_str}</span>'

    else:  # error
        color, text_color, border = "#1a0a0a", "#ef4444", "#ef4444"
        status_html = '<span style="color:#ef4444;">✗ Error</span>'

    # Per-agent summary line
    summary_html = ""
    if summary and status == "complete":
        if agent_name == "intake_agent":
            fault = summary.get("fault", "—")
            conf  = (summary.get("confidence") or 0) * 100
            parts = len(summary.get("parts", []))
            ev    = " · EV" if summary.get("is_ev") else ""
            recall = " · RECALL" if summary.get("recall") else ""
            summary_html = f'<div style="color:#64748b;font-size:0.7rem;margin-top:3px;"><b style="color:#f97316">{fault}</b> · {conf:.0f}% confidence · {parts} parts{ev}{recall}</div>'

        elif agent_name == "inventory_agent":
            reserved = summary.get("reserved", 0)
            unavail  = len(summary.get("unavailable", []))
            reorder  = len(summary.get("reorder", []))
            summary_html = f'<div style="color:#64748b;font-size:0.7rem;margin-top:3px;">{reserved} reserved · {unavail} unavailable · {reorder} flagged for reorder</div>'

        elif agent_name == "quoting_agent":
            total  = summary.get("total") or 0
            has_am = summary.get("has_am", False)
            am_str = " · Aftermarket available" if has_am else ""
            summary_html = f'<div style="color:#64748b;font-size:0.7rem;margin-top:3px;">OEM ₹{total:,.0f}{am_str}</div>'

        elif agent_name == "transaction_agent":
            tx_status   = summary.get("status", "—")
            approved_by = summary.get("approved_by", "")
            hitl        = " · HITL used" if summary.get("hitl") else ""
            summary_html = f'<div style="color:#64748b;font-size:0.7rem;margin-top:3px;">{tx_status} by {approved_by}{hitl}</div>'

        elif agent_name == "replenishment_agent":
            pos = summary.get("pos_raised", 0)
            val = summary.get("total_po_value", 0)
            po_str = f"{pos} PO(s) raised · ₹{val:,.0f}" if pos else "No reorder needed"
            summary_html = f'<div style="color:#64748b;font-size:0.7rem;margin-top:3px;">{po_str}</div>'

    error_html = ""
    if error_msg and status == "error":
        pass

    container.markdown(f"""
    <div style="background:{color};border:1px solid {border};border-left:3px solid {border};
                border-radius:3px;padding:10px 14px;margin-bottom:0px;
                font-family:'IBM Plex Mono',monospace;transition:all 0.2s;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:{text_color};font-size:0.82rem;font-weight:500;">
                {icon} &nbsp;{label}
            </span>
            <span style="font-size:0.72rem;">{status_html}</span>
        </div>
        <div style="color:#334155;font-size:0.68rem;margin-top:2px;">{desc}</div>
        {summary_html}
    </div>
    """, unsafe_allow_html=True)

    if error_msg and status == "error":
        short = error_msg[:200] + ("..." if len(error_msg) > 200 else "")
        container.error(short, icon="🚫")


def _init_session_state():
    """Initialise all HITL-related session state keys if not already set."""
    defaults = {
        "hitl_ro_id":     None,
        "hitl_event":     None,
        "hitl_pending":   False,
        "final_event":    None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _clear_hitl_state():
    """Reset HITL session state — call on fresh pipeline run."""
    st.session_state["hitl_ro_id"]   = None
    st.session_state["hitl_event"]   = None
    st.session_state["hitl_pending"] = False
    st.session_state["final_event"]  = None


def _render_results(final_event, ro_id=None):
    """Renders pipeline results — shared by normal completion and HITL resume."""
    if final_event.get("error"):
        st.markdown(f'<div class="alert alert-danger">✗ {final_event["error"]}</div>',
                    unsafe_allow_html=True)
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Fault",      final_event.get("fault", "—"))
    with c2: st.metric("Urgency",    final_event.get("urgency", "—"))
    with c3:
        conf = (final_event.get("confidence") or 0) * 100
        st.metric("Confidence", f"{conf:.0f}%")
    with c4: st.metric("Status",     final_event.get("transaction_status", "—"))

    st.markdown("<br>", unsafe_allow_html=True)

    quote = final_event.get("quote")
    if quote:
        st.markdown('<div class="section-header">Quote Summary</div>', unsafe_allow_html=True)
        col_oem, col_am = st.columns(2)
        with col_oem:
            st.markdown(f"""
            <div class="quote-card">
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                            letter-spacing:0.1em;text-transform:uppercase;color:#64748b;margin-bottom:0.5rem;">
                    OEM Quote
                </div>
                <div class="quote-total">₹{quote.get('total_amount', 0):,.0f}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                            color:#64748b;margin-top:0.5rem;line-height:1.8;">
                    Subtotal &nbsp;₹{quote.get('subtotal', 0):,.0f}<br>
                    Discount -₹{quote.get('discount_amount', 0):,.0f}<br>
                    GST 18% &nbsp;₹{quote.get('gst_amount', 0):,.0f}
                </div>
            </div>""", unsafe_allow_html=True)

        am = final_event.get("aftermarket_quote")
        with col_am:
            if am:
                saving = quote.get("total_amount", 0) - am.get("total_amount", 0)
                st.markdown(f"""
                <div class="quote-card" style="border-color:#1e3a5f;">
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                                letter-spacing:0.1em;text-transform:uppercase;color:#64748b;margin-bottom:0.5rem;">
                        Aftermarket Option
                    </div>
                    <div class="quote-total" style="color:#3b82f6;">₹{am.get('total_amount', 0):,.0f}</div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                                color:#22c55e;margin-top:0.5rem;">
                        Customer saves ₹{saving:,.0f}
                    </div>
                </div>""", unsafe_allow_html=True)

    parts = final_event.get("required_parts", [])
    if parts:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">Parts Identified</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(parts), 3))
        for i, p in enumerate(parts):
            with cols[i % 3]:
                st.markdown(f"""
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;
                            color:#1c1917;padding:6px 10px;background:#ffffff;
                            border:1px solid #e2ded6;border-radius:4px;margin-bottom:4px;">
                    ✓ {p}
                </div>""", unsafe_allow_html=True)

    ro_display = ro_id or final_event.get("ro_id")
    if ro_display:
        st.markdown(f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                    color:#334155;margin-top:1.5rem;padding-top:1rem;border-top:1px solid #1e1e2e;">
            RO: <span style="color:#f97316;">{ro_display}</span>
            &nbsp;·&nbsp; Quote: <span style="color:#f97316;">{final_event.get('quote_id', '—')}</span>
        </div>""", unsafe_allow_html=True)


def _render_hitl_supervisor_form():
    """Renders the supervisor review form as a full standalone page."""
    ro_id = st.session_state.get("hitl_ro_id")

    st.markdown("""
    <div style="margin-bottom:2rem;">
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:2rem;
                   font-weight:600;color:#1c1917;margin:0.25rem 0;">
            Supervisor Review
        </h1>
    </div>
    """, unsafe_allow_html=True)

    st.warning(
        f"Pipeline paused for RO **{ro_id}** — complaint is ambiguous. "
        "Please provide a short diagnosis to resume.",
        icon="🛑",
    )

    st.markdown("<br>", unsafe_allow_html=True)

    supervisor_id = st.text_input("Supervisor ID", value="SUP-001", key="hitl_supervisor_id")
    pin           = st.text_input("Supervisor PIN", type="password", key="hitl_pin")
    refined       = st.text_area(
        "Supervisor finding / diagnosis",
        placeholder="e.g. battery not working; car not getting started",
        height=120,
        key="hitl_refined",
    )
    estimated_cost = st.number_input(
        "Estimated job cost (₹) — required for bodywork / custom jobs",
        min_value=0,
        value=0,
        step=500,
        key="hitl_estimated_cost",
        help="Enter the estimated cost if no parts are in the catalog (e.g. bodywork, painting, diagnostics)",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        submit_review = st.button("▶  Resume Pipeline", key="hitl_submit", use_container_width=True)
    with col2:
        cancel = st.button("✕  Cancel", key="hitl_cancel", use_container_width=True)

    if cancel:
        _clear_hitl_state()
        st.rerun()
        return

    if not submit_review:
        return

    pin_val     = st.session_state.get("hitl_pin", "")
    refined_val = st.session_state.get("hitl_refined", "")
    sup_id      = st.session_state.get("hitl_supervisor_id", "SUP-001")

    if not pin_val:
        st.error("Supervisor PIN is required")
        return
    if not refined_val.strip():
        st.error("Please enter a short diagnosis to proceed")
        return
    if not ro_id:
        st.error("RO ID missing — cannot submit review")
        return
    estimated_cost_val = st.session_state.get("hitl_estimated_cost", 0)
    if estimated_cost_val == 0:
        st.warning(
            "Estimated cost is ₹0. If this is a bodywork or custom job with no catalog parts, "
            "please enter an estimated cost above to generate a quote.",
            icon="⚠️"
        )
        return

    estimated_cost_val = st.session_state.get("hitl_estimated_cost", 0)
    custom_materials = []
    if estimated_cost_val and estimated_cost_val > 0:
        custom_materials = [{
            "description": refined_val.strip(),
            "cost": float(estimated_cost_val)
        }]

    with st.spinner("Resuming pipeline with supervisor input..."):
        resp = submit_intake_review(ro_id, {
            "supervisor_id":                 sup_id.strip() or "SUP-001",
            "pin":                           pin_val,
            "supervisor_complaint_override":  refined_val.strip(),
            "supervisor_notes":              refined_val.strip(),
            "supervisor_custom_materials":   custom_materials,
        })

    if not resp:
        st.error("Failed to submit intake review — please check your PIN and try again")
        return

    resumed_state = resp.get("state") or {}
    if resumed_state.get("error"):
        st.error(f"Pipeline error after resume: {resumed_state['error']}")
        return

    final_event = {
        "ro_id":                  ro_id,
        "fault":                  resumed_state.get("fault_classification"),
        "urgency":                resumed_state.get("urgency"),
        "confidence":             resumed_state.get("intake_confidence"),
        "required_parts":         resumed_state.get("required_parts", []),
        "parts_available":        resumed_state.get("parts_available"),
        "quote_id":               resumed_state.get("quote_id"),
        "transaction_status":     resumed_state.get("transaction_status"),
        "approved_by":            resumed_state.get("approved_by"),
        "reorder_summary":        resumed_state.get("reorder_summary"),
        "pos_raised":             resumed_state.get("pos_raised", []),
        "quote":                  resumed_state.get("quote"),
        "oem_quote":              resumed_state.get("oem_quote"),
        "aftermarket_quote":      resumed_state.get("aftermarket_quote"),
        "is_ev_job":              resumed_state.get("is_ev_job"),
        "recall_action_required": resumed_state.get("recall_action_required"),
        "error":                  resumed_state.get("error"),
        "total_elapsed":          0,
    }

    st.session_state["hitl_pending"] = False
    st.session_state["hitl_event"]   = None
    st.session_state["final_event"]  = final_event
    st.rerun()


def render_new_ro():

    _init_session_state()

    # ── EARLY HITL CHECK — show supervisor form immediately if pipeline is paused ──
    if st.session_state.get("hitl_pending") and st.session_state.get("hitl_event"):
        _render_hitl_supervisor_form()
        return

    # ── SHOW RESULTS if pipeline just completed after HITL resume ──
    if st.session_state.get("final_event") and not st.session_state.get("hitl_pending"):
        _render_results(st.session_state["final_event"], st.session_state.get("hitl_ro_id"))
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶  New Repair Order", key="new_ro_after_hitl"):
            _clear_hitl_state()
            st.rerun()
        return

    intake_hitl_label = "ON" if INTAKE_HITL_ENABLED else "OFF"
    intake_hitl_color = "#22c55e" if INTAKE_HITL_ENABLED else "#64748b"
    approval_hitl_label = "ON" if TRANSACTION_HITL_ENABLED else "OFF"
    approval_hitl_color = "#22c55e" if TRANSACTION_HITL_ENABLED else "#64748b"

    st.markdown(f"""
    <div style="margin-bottom:2rem;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;
                    letter-spacing:0.15em;text-transform:uppercase;color:#64748b;">
            Pipeline Entry
        </div>
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:2rem;
                   font-weight:600;color:#1c1917;margin:0.25rem 0;">
            New Repair Order
        </h1>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;color:#64748b;margin-top:0.25rem;">
            HITL: Intake <span style="color:{intake_hitl_color};font-weight:600;">{intake_hitl_label}</span>
            &nbsp;|&nbsp; Approval <span style="color:{approval_hitl_color};font-weight:600;">{approval_hitl_label}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_pipeline = st.columns([3, 2])

    with col_form:
        st.markdown('<div class="section-header">Vehicle & Complaint</div>',
                    unsafe_allow_html=True)

        demo_vins = _load_demo_vins(limit=3)

        if "vin_input" not in st.session_state:
            st.session_state["vin_input"] = ""

        vin_preset = st.selectbox(
            "Preset VIN (optional)",
            options=["Custom"] + demo_vins,
            index=0,
        )

        if vin_preset != "Custom":
            st.session_state["vin_input"] = vin_preset

        vin = st.text_input(
            "Vehicle VIN",
            key="vin_input",
            placeholder="e.g. I0Y6DPBHSAHXTHV3A",
        )

        complaint = st.text_area(
            "Customer Complaint",
            placeholder="Describe the issue in natural language...\ne.g. grinding noise from front wheels when braking, car pulls left",
            height=120,
        )

        customer_id = st.text_input("Customer ID (optional)", placeholder="e.g. CUST-001")

        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.button("▶  RUN PIPELINE", use_container_width=True)

    with col_pipeline:
        st.markdown('<div class="section-header">Live Pipeline</div>',
                    unsafe_allow_html=True)

        agent_placeholders = {}
        for agent_name in AGENT_META:
            agent_placeholders[agent_name] = st.empty()
            render_agent_step(agent_placeholders[agent_name], agent_name, "waiting")

        timing_ph = st.empty()

    # ── HANDLE FRESH PIPELINE RUN ─────────────────────────────────────────
    if submit:
        if not vin:
            st.error("VIN is required")
            return
        if not complaint:
            st.error("Complaint description is required")
            return

        # Clear any previous HITL state when starting a new run
        _clear_hitl_state()

        st.markdown("<hr>", unsafe_allow_html=True)
        status_ph = st.empty()
        status_ph.markdown("""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;color:#f97316;">
            ⟳ Connecting to pipeline...
        </div>""", unsafe_allow_html=True)

        final_event = None
        ro_id       = None
        hitl_event  = None

        try:
            with requests.post(
                f"{API_BASE}/repair-orders/stream",
                json   = {
                    "vin":            vin.upper().strip(),
                    "complaint_text": complaint.strip(),
                    "customer_id":    customer_id.strip() or None,
                },
                stream  = True,
                timeout = 300,
            ) as resp:

                resp.raise_for_status()

                for raw_line in resp.iter_lines():
                    if not raw_line:
                        continue

                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    if not line.startswith("data: "):
                        continue

                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("event")
                    agent = event.get("agent")

                    if etype == "ro_created":
                        ro_id = event.get("ro_id")
                        st.session_state["hitl_ro_id"] = ro_id
                        status_ph.markdown(f"""
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#64748b;">
                            RO: <span style="color:#f97316;">{ro_id}</span> · Pipeline running...
                        </div>""", unsafe_allow_html=True)

                    elif etype == "agent_running" and agent in agent_placeholders:
                        render_agent_step(agent_placeholders[agent], agent, "running")

                    elif etype == "agent_complete" and agent in agent_placeholders:
                        st_status = "error" if event.get("error") else "complete"
                        render_agent_step(
                            agent_placeholders[agent], agent, st_status,
                            summary = event.get("summary", {}),
                            elapsed = event.get("elapsed_agent", 0),
                        )

                    elif etype == "agent_error" and agent in agent_placeholders:
                        err = event.get("error", "Unknown error")
                        render_agent_step(agent_placeholders[agent], agent, "error", error_msg=err)
                        status_ph.error(f"✗ {err}")
                        return

                    elif etype == "hitl_required":
                        hitl_event = event
                        st.session_state["hitl_event"]   = event
                        st.session_state["hitl_pending"] = True
                        st.rerun()

                    elif etype == "pipeline_complete":
                        final_event = event
                        st.session_state["final_event"] = event
                        timing_ph.markdown(f"""
                        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                                    color:#22c55e;text-align:right;margin-top:4px;">
                            ✓ Complete · {event.get('total_elapsed', 0):.1f}s total
                        </div>""", unsafe_allow_html=True)

                    elif etype == "error":
                        status_ph.error(event.get("message", "Pipeline error"))
                        return

        except requests.exceptions.Timeout:
            status_ph.error("Timeout — agents may still be running in background")
            return
        except Exception as e:
            status_ph.error(f"Connection error: {e}")
            return

    if not st.session_state.get("final_event"):
        return

    # ── RESULTS (normal pipeline completion, no HITL) ─────────────────────
    final_event = st.session_state.get("final_event")
    if not final_event:
        return

    if final_event.get("error"):
        st.markdown(f'<div class="alert alert-danger">✗ {final_event["error"]}</div>',
                    unsafe_allow_html=True)
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Fault",      final_event.get("fault", "—"))
    with c2: st.metric("Urgency",    final_event.get("urgency", "—"))
    with c3:
        conf = (final_event.get("confidence") or 0) * 100
        st.metric("Confidence", f"{conf:.0f}%")
    with c4: st.metric("Status",     final_event.get("transaction_status", "—"))

    st.markdown("<br>", unsafe_allow_html=True)

    # Quote cards
    quote = final_event.get("quote")
    if quote:
        st.markdown('<div class="section-header">Quote Summary</div>', unsafe_allow_html=True)
        col_oem, col_am = st.columns(2)

        with col_oem:
            st.markdown(f"""
            <div class="quote-card">
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                            letter-spacing:0.1em;text-transform:uppercase;color:#64748b;margin-bottom:0.5rem;">
                    OEM Quote
                </div>
                <div class="quote-total">₹{quote.get('total_amount', 0):,.0f}</div>
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                            color:#64748b;margin-top:0.5rem;line-height:1.8;">
                    Subtotal &nbsp;₹{quote.get('subtotal', 0):,.0f}<br>
                    Discount -₹{quote.get('discount_amount', 0):,.0f}<br>
                    GST 18% &nbsp;₹{quote.get('gst_amount', 0):,.0f}
                </div>
            </div>""", unsafe_allow_html=True)

        am = final_event.get("aftermarket_quote")
        with col_am:
            if am:
                saving = quote.get("total_amount", 0) - am.get("total_amount", 0)
                st.markdown(f"""
                <div class="quote-card" style="border-color:#1e3a5f;">
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                                letter-spacing:0.1em;text-transform:uppercase;color:#64748b;margin-bottom:0.5rem;">
                        Aftermarket Option
                    </div>
                    <div class="quote-total" style="color:#3b82f6;">₹{am.get('total_amount', 0):,.0f}</div>
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                                color:#22c55e;margin-top:0.5rem;">
                        Customer saves ₹{saving:,.0f}
                    </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="quote-card" style="opacity:0.4;">
                    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.75rem;color:#64748b;">
                        OEM only (EV or recall job)
                    </div>
                </div>""", unsafe_allow_html=True)

    # Parts identified
    parts = final_event.get("required_parts", [])
    if parts:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-header">Parts Identified</div>', unsafe_allow_html=True)
        cols = st.columns(min(len(parts), 3))
        for i, p in enumerate(parts):
            with cols[i % 3]:
                st.markdown(f"""
                <div style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;
                            color:#1c1917;padding:6px 10px;background:#ffffff;
                            border:1px solid #e2ded6;border-radius:4px;margin-bottom:4px;
                            box-shadow:0 1px 2px rgba(0,0,0,0.04);">
                    ✓ {p}
                </div>""", unsafe_allow_html=True)

    # Reorder alert
    if final_event.get("reorder_summary"):
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(f'<div class="alert alert-warning">🚚 {final_event["reorder_summary"]}</div>',
                    unsafe_allow_html=True)

    # PO breakdown
    pos_raised = final_event.get("pos_raised") or []
    if pos_raised:
        rows = []
        for po in pos_raised:
            for part in (po.get("parts") or []):
                rows.append({
                    "PO":         po.get("po_id"),
                    "Supplier":   po.get("supplier_name") or po.get("supplier_id"),
                    "Part":       part.get("part_number"),
                    "Qty":        part.get("order_quantity"),
                    "Unit Cost":  part.get("unit_cost"),
                    "Line Value": part.get("order_value"),
                })

        if rows:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Purchase Order Breakdown</div>', unsafe_allow_html=True)
            st.caption("PO totals reflect proactive inventory replenishment (wholesale unit cost × bulk order quantity), not the customer quote.")
            st.dataframe(rows, use_container_width=True, hide_index=True)

    # Footer reference
    ro_id = final_event.get("ro_id") or st.session_state.get("hitl_ro_id")
    if ro_id:
        st.markdown(f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                    color:#334155;margin-top:1.5rem;padding-top:1rem;border-top:1px solid #1e1e2e;">
            RO: <span style="color:#f97316;">{ro_id}</span>
            &nbsp;·&nbsp; Quote: <span style="color:#f97316;">{final_event.get('quote_id', '—')}</span>
            &nbsp;·&nbsp; {final_event.get('total_elapsed', 0):.1f}s pipeline
        </div>""", unsafe_allow_html=True)
