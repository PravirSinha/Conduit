"""CONDUIT — New Repair Order Page with Real SSE Streaming"""
import json
import time
import requests
import streamlit as st

API_BASE = "http://localhost:8000/api"

AGENT_META = {
    "intake_agent":        {"icon": "🧠", "label": "Intake Agent",       "desc": "Semantic search + GPT-4o fault classification"},
    "inventory_agent":     {"icon": "📦", "label": "Inventory Agent",     "desc": "Stock check + atomic parts reservation"},
    "quoting_agent":       {"icon": "🧾", "label": "Quoting Agent",       "desc": "OEM + aftermarket pricing + GST"},
    "transaction_agent":   {"icon": "✅", "label": "Transaction Agent",   "desc": "Approval + reservation confirmation"},
    "replenishment_agent": {"icon": "🚚", "label": "Replenishment Agent", "desc": "Supplier scoring + PO creation"},
}


def render_agent_step(container, agent_name, status, summary=None, elapsed=None):
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

    container.markdown(f"""
    <div style="background:{color};border:1px solid {border};border-left:3px solid {border};
                border-radius:3px;padding:10px 14px;margin-bottom:5px;
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


def render_new_ro():

    st.markdown("""
    <div style="margin-bottom:2rem;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;
                    letter-spacing:0.15em;text-transform:uppercase;color:#64748b;">
            Pipeline Entry
        </div>
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:2rem;
                   font-weight:600;color:#1c1917;margin:0.25rem 0;">
            New Repair Order
        </h1>
    </div>
    """, unsafe_allow_html=True)

    col_form, col_pipeline = st.columns([3, 2])

    with col_form:
        st.markdown('<div class="section-header">Vehicle & Complaint</div>',
                    unsafe_allow_html=True)

        vin = st.text_input("Vehicle VIN", placeholder="e.g. I0Y6DPBHSAHXTHV3A")

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

        # Render waiting state for all agents
        agent_placeholders = {}
        for agent_name in AGENT_META:
            agent_placeholders[agent_name] = st.empty()
            render_agent_step(agent_placeholders[agent_name], agent_name, "waiting")

        timing_ph = st.empty()

    # ── SSE STREAMING EXECUTION ───────────────────────────────────────────
    if not submit:
        return

    if not vin:
        st.error("VIN is required")
        return
    if not complaint:
        st.error("Complaint description is required")
        return

    st.markdown("<hr>", unsafe_allow_html=True)
    status_ph = st.empty()
    status_ph.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace;font-size:0.8rem;color:#f97316;">
        ⟳ Connecting to pipeline...
    </div>""", unsafe_allow_html=True)

    final_event = None
    ro_id       = None

    try:
        with requests.post(
            f"{API_BASE}/repair-orders/stream",
            json   = {
                "vin":            vin.upper().strip(),
                "complaint_text": complaint.strip(),
                "customer_id":    customer_id.strip() or None,
            },
            stream  = True,
            timeout = 120,
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

                elif etype == "hitl_required":
                    status_ph.markdown(f"""
                    <div class="alert alert-warning">
                        ⚠ {event.get('message')} — check Pending Approvals
                    </div>""", unsafe_allow_html=True)
                    return

                elif etype == "pipeline_complete":
                    final_event = event
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

    if not final_event:
        return

    status_ph.empty()

    if final_event.get("error"):
        st.markdown(f'<div class="alert alert-danger">✗ {final_event["error"]}</div>',
                    unsafe_allow_html=True)
        return

    # ── RESULTS ───────────────────────────────────────────────────────────
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

    # Footer reference
    if ro_id:
        st.markdown(f"""
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.72rem;
                    color:#334155;margin-top:1.5rem;padding-top:1rem;border-top:1px solid #1e1e2e;">
            RO: <span style="color:#f97316;">{ro_id}</span>
            &nbsp;·&nbsp; Quote: <span style="color:#f97316;">{final_event.get('quote_id', '—')}</span>
            &nbsp;·&nbsp; {final_event.get('total_elapsed', 0):.1f}s pipeline
        </div>""", unsafe_allow_html=True)