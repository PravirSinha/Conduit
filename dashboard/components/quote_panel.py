"""CONDUIT — Quote Panel"""
import streamlit as st
from dashboard.api_client import get_quote


def render_quotes():
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.7rem;
                    letter-spacing: 0.15em; text-transform: uppercase; color: #64748b;">
            Pricing
        </div>
        <h1 style="font-family: 'IBM Plex Mono', monospace; font-size: 2rem;
                   font-weight: 600; color: #1c1917; margin: 0.25rem 0;">
            Quote Lookup
        </h1>
    </div>
    """, unsafe_allow_html=True)

    quote_id = st.text_input(
        "Quote ID",
        placeholder="e.g. QT-D30475A9",
    )

    if not quote_id:
        st.info("Enter a Quote ID to view details")
        return

    quote = get_quote(quote_id.strip().upper())

    if not quote:
        st.error(f"Quote {quote_id} not found")
        return

    # Quote header
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total (OEM)", f"₹{quote.get('total_amount', 0):,.0f}")
    with col2:
        st.metric("GST (18%)", f"₹{quote.get('gst_amount', 0):,.0f}")
    with col3:
        st.metric("Status", quote.get("status", "—"))

    st.markdown("<hr>", unsafe_allow_html=True)

    # Line items
    st.markdown('<div class="section-header">Line Items</div>',
                unsafe_allow_html=True)

    for item in quote.get("line_items", []):
        item_type = item.get("type", "")
        icon = "🔩" if item_type == "PART" else "🔧"
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between;
                    font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem;
                    padding: 8px 0; border-bottom: 1px solid #e2ded6; color: #1c1917;">
            <span>{icon} {item.get('description', '')[:55]}</span>
            <span style="color: #f97316;">₹{item.get('subtotal', 0):,.0f}</span>
        </div>""", unsafe_allow_html=True)

    # Totals
    st.markdown(f"""
    <div style="font-family: 'IBM Plex Mono', monospace; font-size: 0.8rem;
                padding: 1rem 0; color: #64748b;">
        Subtotal: ₹{quote.get('subtotal', 0):,.0f} &nbsp;|&nbsp;
        Discount: -₹{quote.get('discount_amount', 0):,.0f} &nbsp;|&nbsp;
        GST: ₹{quote.get('gst_amount', 0):,.0f}
    </div>
    <div style="font-family: 'IBM Plex Mono', monospace; font-size: 1.5rem;
                font-weight: 600; color: #f97316;">
        Total: ₹{quote.get('total_amount', 0):,.0f}
    </div>
    """, unsafe_allow_html=True)

    # Aftermarket option
    am = quote.get("aftermarket_quote")
    if am:
        st.markdown("<br>", unsafe_allow_html=True)
        saving = quote.get("total_amount", 0) - am.get("total_amount", 0)
        st.markdown(f"""
        <div class="alert alert-success">
            Aftermarket option available: ₹{am.get('total_amount', 0):,.0f}
            — customer saves ₹{saving:,.0f}
        </div>""", unsafe_allow_html=True)