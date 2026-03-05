"""CONDUIT — Pending Approval Page (HITL)"""
import streamlit as st
from dashboard.api_client import get_pending_approval, approve_quote, reject_quote


def render_pending_approval():
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Human-in-the-Loop
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Pending Approvals
        </h1>
    </div>
    """, unsafe_allow_html=True)

    ros = get_pending_approval()

    if not ros:
        st.markdown("""
        <div class="alert alert-success">
            ✓ No pending approvals — all queues clear
        </div>""", unsafe_allow_html=True)
        return

    st.markdown(f"""
    <div class="alert alert-warning">
        ⚠ {len(ros)} repair order(s) awaiting approval
    </div>""", unsafe_allow_html=True)

    for ro in ros:
        ro_id   = ro.get("ro_id", "")
        vehicle = f"{ro.get('vehicle_year', '')} {ro.get('vehicle_make', '')} {ro.get('vehicle_model', '')}"
        fault   = ro.get("fault_classification", "—")
        total   = ro.get("final_total")
        status  = ro.get("status", "—")

        with st.expander(
            f"🔴  {ro_id}  |  {vehicle}  |  {fault}  |  {status}",
            expanded=True
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Vehicle", vehicle)
            with col2:
                st.metric("Fault", fault)
            with col3:
                st.metric("Quote Total",
                          f"₹{total:,.0f}" if total else "Pending")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Advisor Authentication</div>',
                        unsafe_allow_html=True)

            col_id, col_pin = st.columns(2)
            with col_id:
                advisor_id = st.text_input(
                    "Advisor ID",
                    key=f"advisor_{ro_id}",
                    placeholder="e.g. SA-001"
                )
            with col_pin:
                pin = st.text_input(
                    "Advisor PIN",
                    key=f"pin_{ro_id}",
                    type="password",
                    placeholder="Enter PIN"
                )

            notes = st.text_input(
                "Notes (optional)",
                key=f"notes_{ro_id}",
                placeholder="Any approval notes..."
            )

            col_approve, col_reject = st.columns(2)

            with col_approve:
                if st.button(f"✓  APPROVE", key=f"approve_{ro_id}",
                             use_container_width=True):
                    if not advisor_id or not pin:
                        st.error("Advisor ID and PIN required")
                    else:
                        with st.spinner("Processing approval..."):
                            result = approve_quote(
                                ro_id      = ro_id,
                                advisor_id = advisor_id,
                                pin        = pin,
                                notes      = notes or "",
                            )

                        if result and "Invalid PIN" not in str(result):
                            st.success(f"✓ RO {ro_id} approved — pipeline resumed")
                            st.rerun()
                        elif result and "Invalid PIN" in str(result):
                            st.error("Invalid PIN")
                        else:
                            st.error("Approval failed — check if pipeline is paused")

            with col_reject:
                reject_reason = st.text_input(
                    "Rejection reason",
                    key=f"reason_{ro_id}",
                    placeholder="Required for rejection"
                )

                if st.button(f"✗  REJECT", key=f"reject_{ro_id}",
                             use_container_width=True):
                    if not advisor_id or not pin:
                        st.error("Advisor ID and PIN required")
                    elif not reject_reason:
                        st.error("Rejection reason required")
                    else:
                        with st.spinner("Processing rejection..."):
                            result = reject_quote(
                                ro_id      = ro_id,
                                advisor_id = advisor_id,
                                pin        = pin,
                                reason     = reject_reason,
                            )

                        if result:
                            st.warning(f"RO {ro_id} rejected — reservations released")
                            st.rerun()
                        else:
                            st.error("Rejection failed")