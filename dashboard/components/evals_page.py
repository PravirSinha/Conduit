"""CONDUIT — Evals Dashboard (3-tab: Quality Gates / Agent Health / Cost & Latency)"""

import os, json, sys
import streamlit as st
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SNAPSHOT_PATHS = [
    os.path.join(ROOT, "docs",  "eval_results.json"),
    os.path.join(ROOT, "evals", "reports", "latest", "summary.json"),
]

DEMO_SUMMARY = {
    "_demo": True,
    "run_at": "2026-04-10T10:30:00Z",
    "all_passed": True,
    "passed": 10, "failed": 0, "total": 10,
    "total_elapsed": 245.0,
    "headline_metrics": [
        {"id": "system_pass_rate",               "value": 100},
        {"id": "intake_classification_accuracy", "value": 90.0},
        {"id": "rag_recall_at_5",                "value": 80.0},
    ],
    "eval_metrics": {
        "Fault Classification Accuracy":    {"eval": "Fault Classification Accuracy",    "pass_rate": 90.0,  "passed": 9,  "failed": 1, "total": 10},
        "Urgency Accuracy":                 {"eval": "Urgency Accuracy",                 "pass_rate": 100.0, "passed": 10, "failed": 0, "total": 10},
        "LLM Judge: Diagnosis Relevance":   {"eval": "LLM Judge: Diagnosis Relevance",   "pass_rate": 90.0,  "passed": 9,  "failed": 1, "total": 10},
        "LLM Judge: Hallucination Check":   {"eval": "LLM Judge: Hallucination Check",   "pass_rate": 100.0, "passed": 10, "failed": 0, "total": 10},
        "LLM Judge: Technician Clarity":    {"eval": "LLM Judge: Technician Clarity",    "pass_rate": 90.0,  "passed": 9,  "failed": 1, "total": 10},
        "RAG Precision@5":                  {"eval": "RAG Precision@5",                  "pass_rate": 100.0, "passed": 5,  "failed": 0, "total": 5},
        "RAG Recall@5":                     {"eval": "RAG Recall@5",                     "pass_rate": 80.0,  "passed": 4,  "failed": 1, "total": 5},
        "RAG Relevance Score":              {"eval": "RAG Relevance Score",              "pass_rate": 100.0, "passed": 5,  "failed": 0, "total": 5},
        "GST Calculation Accuracy":         {"eval": "GST Calculation Accuracy",         "pass_rate": 100.0, "passed": 5,  "failed": 0, "total": 5},
        "Parts Compatibility Accuracy":     {"eval": "Parts Compatibility Accuracy",     "pass_rate": 100.0, "passed": 5,  "failed": 0, "total": 5},
        "Quoting Dataset Accuracy":         {"eval": "Quoting Dataset Accuracy",         "pass_rate": 100.0, "passed": 4,  "failed": 0, "total": 4},
        "Reorder Quantity Accuracy":        {"eval": "Reorder Quantity Accuracy",        "pass_rate": 100.0, "passed": 4,  "failed": 0, "total": 4},
    },
    "modules": [
        {"label": "Intake Guardrails",              "passed": True,  "cost": "$0.00",  "elapsed_s": 38.2},
        {"label": "Quoting Guardrails",             "passed": True,  "cost": "$0.00",  "elapsed_s": 22.1},
        {"label": "Output Validators",              "passed": True,  "cost": "$0.00",  "elapsed_s": 19.6},
        {"label": "Inventory Agent",                "passed": True,  "cost": "$0.00",  "elapsed_s": 28.4},
        {"label": "Quoting Agent",                  "passed": True,  "cost": "$0.00",  "elapsed_s": 31.7},
        {"label": "Transaction Agent",              "passed": True,  "cost": "$0.00",  "elapsed_s": 44.8},
        {"label": "Replenishment Agent",            "passed": True,  "cost": "$0.00",  "elapsed_s": 33.6},
        {"label": "Intake Agent (LLM)",             "passed": True,  "cost": "~$0.20", "elapsed_s": 62.1},
        {"label": "RAG Retrieval (Pinecone)",       "passed": True,  "cost": "~$0.05", "elapsed_s": 18.4},
        {"label": "LLM-as-Judge (Diagnosis)",       "passed": True,  "cost": "~$0.05", "elapsed_s": 24.3},
    ],
}


def _load_snapshot():
    for path in SNAPSHOT_PATHS:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    d = json.load(f)
                    d["_source"] = "real"
                    return d
            except Exception:
                continue
    return DEMO_SUMMARY


def _fmt_date(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso


def _pct(v):
    if v is None: return "N/A"
    try:    return f"{float(v):.0f}%"
    except: return "N/A"


def _metric_card(label, value_str, sub=None, color="#1c1917"):
    st.markdown(f"""
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                padding:14px 18px;margin-bottom:8px;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.65rem;
                    letter-spacing:0.1em;text-transform:uppercase;color:#64748b;">
            {label}
        </div>
        <div style="font-family:'IBM Plex Mono',monospace;font-size:1.4rem;
                    font-weight:700;color:{color};margin-top:4px;">
            {value_str}
        </div>
        {f'<div style="font-size:0.72rem;color:#64748b;margin-top:2px;">{sub}</div>' if sub else ''}
    </div>
    """, unsafe_allow_html=True)


def _eval_row(label, pass_rate, passed, total, desc=""):
    color = "#15803d" if pass_rate >= 90 else "#ca8a04" if pass_rate >= 70 else "#dc2626"
    bar_w = int(pass_rate)
    st.markdown(f"""
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                padding:12px 18px;margin-bottom:8px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
                <div style="font-weight:600;font-size:0.88rem;color:#1c1917;">{label}</div>
                {f'<div style="font-size:0.72rem;color:#64748b;margin-top:2px;">{desc}</div>' if desc else ''}
                <div style="font-size:0.72rem;color:#64748b;margin-top:2px;">{passed}/{total} cases passing</div>
            </div>
            <div style="font-family:'IBM Plex Mono',monospace;font-size:1.15rem;
                        font-weight:700;color:{color};white-space:nowrap;margin-left:16px;">
                {pass_rate:.0f}%
            </div>
        </div>
        <div style="background:#e2e8f0;border-radius:4px;height:5px;width:100%;margin-top:8px;">
            <div style="background:{color};border-radius:4px;height:5px;width:{bar_w}%;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _get_agent_stats():
    try:
        sys.path.insert(0, ROOT)
        from database.connection import get_session
        from database.models import AgentAuditLog
        from sqlalchemy import func
        cutoff = datetime.utcnow() - timedelta(days=7)
        with get_session() as db:
            rows = (
                db.query(
                    AgentAuditLog.agent_name,
                    func.count(AgentAuditLog.log_id).label("runs"),
                    func.avg(AgentAuditLog.latency_ms).label("avg_ms"),
                    func.min(AgentAuditLog.latency_ms).label("min_ms"),
                    func.max(AgentAuditLog.latency_ms).label("max_ms"),
                )
                .filter(
                    AgentAuditLog.action == "agent_end",
                    AgentAuditLog.created_at >= cutoff,
                    AgentAuditLog.latency_ms.isnot(None),
                )
                .group_by(AgentAuditLog.agent_name)
                .order_by(func.avg(AgentAuditLog.latency_ms).desc())
                .all()
            )
        labels  = {"intake_agent": "Intake Agent", "quoting_agent": "Quoting Agent",
                   "inventory_agent": "Inventory Agent", "transaction_agent": "Transaction Agent",
                   "replenishment_agent": "Replenishment Agent"}
        llm_set = {"intake_agent"}
        return [{"key": r.agent_name, "label": labels.get(r.agent_name, r.agent_name),
                 "runs": r.runs, "avg_ms": round(r.avg_ms) if r.avg_ms else 0,
                 "min_ms": r.min_ms or 0, "max_ms": r.max_ms or 0,
                 "llm": r.agent_name in llm_set} for r in rows]
    except Exception:
        return []


def render_evals():

    st.markdown("""
    <div style="margin-bottom:2rem;">
        <div style="font-family:'IBM Plex Mono',monospace;font-size:0.7rem;
                    letter-spacing:0.15em;text-transform:uppercase;color:#64748b;">
            System Health
        </div>
        <h1 style="font-family:'IBM Plex Mono',monospace;font-size:2rem;
                   font-weight:600;color:#1c1917;margin:0.25rem 0;">
            Eval Results
        </h1>
    </div>
    """, unsafe_allow_html=True)

    summary     = _load_snapshot()
    is_demo     = summary.get("_demo", False)
    agent_stats = _get_agent_stats()
    run_at      = summary.get("run_at", "")

    if is_demo:
        st.info(
            "**Demo mode** — representative results. "
            "Run `python evals/run_evals.py --free` and commit `docs/eval_results.json` to show real numbers.",
            icon="🧪"
        )
    else:
        st.markdown(f"""
        <div style="display:inline-flex;align-items:center;gap:8px;background:#f0fdf4;
                    border:1px solid #bbf7d0;border-radius:20px;
                    padding:4px 14px;font-size:0.78rem;color:#15803d;margin-bottom:16px;">
            ✓ Live snapshot · {_fmt_date(run_at)} · $0.00 to view
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📊 Quality Gates", "🤖 Agent Health", "💰 Cost & Latency"])

    # ══════════════════════════════════════════════════
    # TAB 1 — QUALITY GATES
    # ══════════════════════════════════════════════════
    with tab1:
        passed     = summary.get("passed", 0)
        total      = summary.get("total", 0)
        all_passed = summary.get("all_passed", False)
        elapsed    = summary.get("total_elapsed", 0)
        modules    = summary.get("modules", [])
        em         = summary.get("eval_metrics") or {}
        mmap       = {m.get("id"): m for m in (summary.get("headline_metrics") or []) if isinstance(m, dict)}

        def _val(mid, fb=None):
            return (mmap.get(mid) or {}).get("value", fb)

        # Status banner
        if all_passed:
            st.markdown(f"""
            <div style="background:#f0fdf4;border:1.5px solid #16a34a;border-radius:10px;
                        padding:16px 24px;margin-bottom:20px;display:flex;align-items:center;gap:14px;">
                <span style="font-size:1.5rem;">✅</span>
                <div>
                    <div style="font-size:1rem;font-weight:600;color:#15803d;">
                        {passed}/{total} eval modules passing — system is production ready
                    </div>
                    <div style="font-size:0.76rem;color:#166534;margin-top:2px;">
                        Last run: {_fmt_date(run_at)} · {elapsed:.0f}s total
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)
        else:
            bad = [m["label"] for m in modules if not m.get("passed")]
            st.error(f"**{summary.get('failed',0)} failing:** {', '.join(bad)}")

        # KPI row
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("System Pass Rate", _pct(_val("system_pass_rate", round(passed/total*100) if total else 0)))
        with c2: st.metric("LLM Accuracy", _pct(_val("intake_classification_accuracy")), help="GPT-4o fault classification vs 10 ground truth labels")
        with c3: st.metric("RAG Recall@5", _pct(_val("rag_recall_at_5")), help="Expected parts found in Pinecone top-5 results")
        with c4:
            ng = len([m for m in modules if any(x in m.get("label","") for x in {"Guardrail","Validator"})])
            st.metric("Active Guardrails", ng, help="Deterministic checks on every pipeline run")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── LAYER 1: GUARDRAILS
        st.markdown("#### 🛡️ Layer 1 — Rule-Based Guardrails")
        st.caption("Deterministic Python validation — $0.00, enforced on every live pipeline execution")

        with st.expander("View all 14 guardrail checks"):
            st.markdown("""
**Intake Agent (5 checks)**
- Required fields present: fault_classification, urgency, confidence, required_parts
- Enum validation: fault_classification ∈ 7 allowed values
- Enum validation: urgency ∈ {HIGH, MEDIUM, LOW, NEEDS_CLARIFICATION}
- Confidence bounds: 0.0 ≤ confidence ≤ 1.0
- **Safety override**: BRAKE_SYSTEM / EV_SYSTEM cannot have LOW urgency — auto-escalated

**Quoting Agent (5 checks)**
- Quote total must be positive
- Line items must be non-empty
- Arithmetic: subtotal + GST − discount = total (±₹1 tolerance)
- **Discount cap**: max 30% unless recall job
- **GST validation**: exactly 18% of post-discount subtotal

**Inventory / Transaction / Replenishment (4 checks)**
- Schema: required fields present, non-negative quantities
- quote_id must exist before transaction proceeds
- PO values must be positive
- Supplier scoring must produce ranked list before PO creation
            """)

        for m in [x for x in modules if any(g in x.get("label","") for g in {"Guardrail","Validator"})]:
            ok = m.get("passed", False)
            st.markdown(f"""
            <div style="background:{"#f0fdf4" if ok else "#fef2f2"};border:1px solid {"#16a34a" if ok else "#dc2626"};
                        border-radius:8px;padding:10px 18px;margin-bottom:6px;
                        display:flex;justify-content:space-between;align-items:center;">
                <div style="display:flex;align-items:center;gap:10px;">
                    <span>{"✅" if ok else "❌"}</span>
                    <div>
                        <div style="font-weight:600;font-size:0.88rem;">{m["label"]}</div>
                        <div style="font-size:0.72rem;color:#57534e;">Cost: {m.get("cost","$0.00")} · {m.get("elapsed_s",0):.1f}s</div>
                    </div>
                </div>
                <div style="font-weight:700;font-size:0.78rem;color:{"#15803d" if ok else "#991b1b"};">{"PASSED" if ok else "FAILED"}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── LAYER 2: LLM ACCURACY (ground truth)
        st.markdown("#### 🤖 Layer 2 — LLM Classification Accuracy")
        st.caption("Intake Agent (GPT-4o) evaluated against 10 labelled ground truth cases · ~$0.20/run")

        for key in ["Fault Classification Accuracy", "Urgency Accuracy"]:
            m = em.get(key)
            if m:
                _eval_row(key, m.get("pass_rate",0), m.get("passed",0), m.get("total",0),
                          "fault_classification enum match" if "Fault" in key else "urgency enum match")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── LAYER 3: LLM-AS-JUDGE
        st.markdown("#### 🧑‍⚖️ Layer 3 — LLM-as-Judge (Diagnosis Quality)")
        st.caption("GPT-4o evaluates the free-text fault_description and notes for relevance, hallucination, and clarity · ~$0.05/run")

        with st.expander("How LLM-as-judge works in Conduit"):
            st.markdown("""
The Intake Agent produces two free-text outputs alongside its structured classification:
- **fault_description** — one sentence describing the likely fault for the technician
- **notes** — additional context or instructions

These cannot be evaluated with exact match (unlike enum fields).
A second GPT-4o call acts as a **quality judge**, evaluating each output on:

1. **Diagnosis Relevance** — does fault_description directly address the complaint?
2. **Hallucination Check** — does it mention issues/parts NOT in the complaint or catalog?
3. **Technician Clarity** — would a technician clearly understand what to inspect/fix?

This costs ~$0.05 for 10 eval cases (short judge prompt, 200 max tokens each).
The judge uses temperature=0.0 for deterministic evaluation.
            """)

        for key in ["LLM Judge: Diagnosis Relevance", "LLM Judge: Hallucination Check", "LLM Judge: Technician Clarity"]:
            m = em.get(key)
            descs = {
                "LLM Judge: Diagnosis Relevance": "Is fault_description relevant to the original complaint?",
                "LLM Judge: Hallucination Check": "Does response avoid hallucinating parts/issues not in complaint or catalog?",
                "LLM Judge: Technician Clarity":  "Would a technician clearly understand what to inspect/repair?",
            }
            if m:
                _eval_row(key, m.get("pass_rate",0), m.get("passed",0), m.get("total",0), descs.get(key,""))
            else:
                st.markdown(f"""
                <div style="background:#fafafa;border:1px dashed #cbd5e1;border-radius:8px;
                            padding:10px 18px;margin-bottom:8px;">
                    <div style="font-weight:600;font-size:0.88rem;color:#64748b;">{key}</div>
                    <div style="font-size:0.72rem;color:#94a3b8;">{descs.get(key,"")} · Run evals/run_evals.py to populate</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── LAYER 4: RAG METRICS
        st.markdown("#### 🔍 Layer 4 — RAG Retrieval Quality (Pinecone)")
        st.caption("Measures whether the right parts are retrieved for a given complaint · ~$0.05/run (embeddings only)")

        rag_descs = {
            "RAG Precision@5":    "Of top-5 retrieved parts, what fraction are relevant to the complaint?",
            "RAG Recall@5":       "Of all expected part categories, what fraction appear in top-5 results?",
            "RAG Relevance Score":"Average cosine similarity score from Pinecone (target ≥ 0.70)",
        }
        has_rag = any(em.get(k) for k in rag_descs)
        if not has_rag:
            st.info("Run `python evals/run_evals.py --rag-only` (~$0.05) to populate RAG metrics.", icon="🔍")
        else:
            for key, desc in rag_descs.items():
                m = em.get(key)
                if m:
                    _eval_row(key, m.get("pass_rate",0), m.get("passed",0), m.get("total",0), desc)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── LAYER 5: COMPONENT ACCURACY
        st.markdown("#### ⚙️ Layer 5 — Component Logic Accuracy")
        st.caption("Agent business logic tested against synthetic datasets · $0.00/run")

        comp_keys = ["GST Calculation Accuracy","Parts Compatibility Accuracy",
                     "Quoting Dataset Accuracy","Reorder Quantity Accuracy"]
        for key in comp_keys:
            m = em.get(key)
            if m:
                _eval_row(key, m.get("pass_rate",0), m.get("passed",0), m.get("total",0))

        # Hallucination explainer
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🧠 Hallucination prevention architecture"):
            st.markdown("""
Conduit uses **structural prevention** (guards against hallucinations at the source)
combined with **LLM-as-judge** (detects any that slip through):

| Method | How | Where |
|---|---|---|
| RAG grounding | Parts must come from Pinecone — agent cannot invent part numbers | Intake Agent |
| Enum constraints | fault_classification / urgency validated against strict allowed-values list | Guardrail Layer |
| Deterministic financials | All quoting maths is pure Python — GPT-4o never touches numbers | Quoting Agent |
| Confidence threshold | Complaints < 70% confidence routed to human review (HITL) | Intake Agent |
| **LLM-as-judge** | GPT-4o evaluates free-text diagnosis for hallucinated content | Eval Layer 3 |
| LangSmith tracing | Every GPT-4o call logged — prompt/response auditable per RO | Observability |
            """)

    # ══════════════════════════════════════════════════
    # TAB 2 — AGENT HEALTH
    # ══════════════════════════════════════════════════
    with tab2:
        st.markdown("#### Per-Agent Latency — Last 7 Days")
        st.caption("Live data from `agent_audit_log` table · logged automatically on every pipeline run")

        if not agent_stats:
            st.info("No agent data yet. Run a pipeline from New Repair Order to populate this tab.")
        else:
            total_ms = sum(r["avg_ms"] for r in agent_stats)
            slowest  = max(agent_stats, key=lambda r: r["avg_ms"])
            llm_r    = next((r for r in agent_stats if r["llm"]), None)
            llm_pct  = round(llm_r["avg_ms"] / total_ms * 100) if llm_r and total_ms else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Pipeline Runs (7d)", agent_stats[0]["runs"])
            with c2: st.metric("Avg Pipeline Time", f"{total_ms/1000:.1f}s", help="Sum of avg latency across all agents")
            with c3: st.metric("Slowest Agent", slowest["label"].replace(" Agent",""), delta=f"{slowest['avg_ms']}ms avg", delta_color="off")
            with c4: st.metric("LLM % of Pipeline", f"{llm_pct}%", help="% of pipeline time on GPT-4o (Intake only)")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Latency by Agent**")

            max_ms = max(r["avg_ms"] for r in agent_stats) or 1
            for r in sorted(agent_stats, key=lambda x: x["avg_ms"], reverse=True):
                pct   = r["avg_ms"] / max_ms * 100
                color = "#f97316" if r["llm"] else "#3b82f6"
                tag   = "GPT-4o" if r["llm"] else "deterministic"
                st.markdown(f"""
                <div style="margin-bottom:10px;">
                    <div style="display:flex;justify-content:space-between;
                                font-family:'IBM Plex Mono',monospace;font-size:0.75rem;
                                color:#334155;margin-bottom:3px;">
                        <span>{r["label"]} <span style="color:#94a3b8;font-size:0.68rem;">· {tag}</span></span>
                        <span>{r["avg_ms"]}ms avg &nbsp;|&nbsp; {r["min_ms"]}–{r["max_ms"]}ms range</span>
                    </div>
                    <div style="background:#e2e8f0;border-radius:4px;height:7px;">
                        <div style="background:{color};border-radius:4px;height:7px;width:{pct:.0f}%;"></div>
                    </div>
                </div>""", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.caption("🟠 Orange = LLM (GPT-4o) · 🔵 Blue = deterministic Python")

            import pandas as pd
            df = pd.DataFrame([{
                "Agent": r["label"], "Avg (ms)": r["avg_ms"],
                "Min (ms)": r["min_ms"], "Max (ms)": r["max_ms"],
                "Runs (7d)": r["runs"], "Type": "LLM" if r["llm"] else "Deterministic",
            } for r in agent_stats])
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ══════════════════════════════════════════════════
    # TAB 3 — COST & LATENCY
    # ══════════════════════════════════════════════════
    with tab3:
        st.markdown("#### Cost per Pipeline Run")

        # GPT-4o pricing (gpt-4o as of 2024)
        INPUT_COST_PER_1K  = 0.005
        OUTPUT_COST_PER_1K = 0.015
        intake_input  = 800;  intake_output  = 400
        judge_input   = 300;  judge_output   = 80   # eval only, not per live run
        embed_tokens  = 200

        intake_cost   = intake_input/1000*INPUT_COST_PER_1K + intake_output/1000*OUTPUT_COST_PER_1K
        embed_cost    = embed_tokens/1000 * 0.0001
        total_run     = intake_cost + embed_cost

        runs_7d = agent_stats[0]["runs"] if agent_stats else 0
        spend_7d = total_run * runs_7d

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("Cost per Pipeline Run", f"~${total_run:.4f}", help="GPT-4o intake + Pinecone embedding")
        with c2: st.metric("GPT-4o per Run", f"~${intake_cost:.4f}", help=f"~{intake_input} input + ~{intake_output} output tokens")
        with c3: st.metric("Embedding per Run", f"~${embed_cost:.6f}", help="text-embedding-3-small, ~200 tokens")
        with c4: st.metric("Est. 7-Day Spend", f"~${spend_7d:.2f}", delta=f"{runs_7d} runs" if runs_7d else None, delta_color="off")

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("**Cost Breakdown — per live pipeline run**")
        import pandas as pd
        live_costs = pd.DataFrame([
            {"Component": "GPT-4o — Intake Classification",   "Tokens": f"~{intake_input+intake_output}",  "Est. Cost": f"${intake_cost:.4f}", "Notes": "Only LLM call in production pipeline"},
            {"Component": "Pinecone — Semantic Part Search",  "Tokens": f"~{embed_tokens}",                "Est. Cost": f"${embed_cost:.6f}",  "Notes": "text-embedding-3-small"},
            {"Component": "PostgreSQL — All 5 Agents",        "Tokens": "—",                               "Est. Cost": "$0.0000",             "Notes": "Cloud SQL, fixed monthly cost"},
            {"Component": "Cloud Run — Backend compute",      "Tokens": "—",                               "Est. Cost": "~$0.0001",            "Notes": "Per-request, negligible at this scale"},
            {"Component": "Total per repair order",           "Tokens": "—",                               "Est. Cost": f"~${total_run:.4f}",  "Notes": "4 of 5 agents are 100% deterministic"},
        ])
        st.dataframe(live_costs, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Cost Breakdown — eval suite (run before demo/deploy)**")
        judge_cost = judge_input/1000*INPUT_COST_PER_1K*10 + judge_output/1000*OUTPUT_COST_PER_1K*10
        eval_costs = pd.DataFrame([
            {"Eval Module": "Guardrails — 3 modules",        "Cost": "$0.00",          "When": "Every deploy (CI/CD)", "What": "Pure Python assertions"},
            {"Eval Module": "Component Evals — 5 agents",   "Cost": "$0.00",          "When": "Every deploy (CI/CD)", "What": "Logic accuracy vs synthetic datasets"},
            {"Eval Module": "Intake Agent LLM accuracy",     "Cost": "~$0.20",         "When": "Pre-deploy",           "What": "10 GPT-4o calls vs ground truth labels"},
            {"Eval Module": "LLM-as-Judge (diagnosis)",      "Cost": f"~${judge_cost:.2f}", "When": "Pre-deploy",      "What": "10 judge calls for free-text quality"},
            {"Eval Module": "RAG Retrieval (Pinecone)",      "Cost": "~$0.05",         "When": "Weekly or pre-deploy", "What": "Precision@5, Recall@5, cosine similarity"},
            {"Eval Module": "Full Pipeline — 5 end-to-end",  "Cost": "~$0.80",         "When": "Pre-release",          "What": "E2E success rate, latency, GST accuracy"},
            {"Eval Module": "Total — full suite",            "Cost": "~$1.10",         "When": "—",                    "What": "—"},
        ])
        st.dataframe(eval_costs, use_container_width=True, hide_index=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
**Why so cheap per run?**

Only **1 of 5 agents** calls an LLM. Inventory,
Quoting, Transaction, and Replenishment are 100%
deterministic Python — no API calls, no latency risk,
zero variable cost per run.
            """)
        with col2:
            st.markdown("""
**LangSmith observability**

Every GPT-4o call is automatically traced to LangSmith —
token counts, latency, prompt/response pairs are
auditable per repair order at `eu.api.smith.langchain.com`.
Zero extra instrumentation needed.
            """)

        with st.expander("🔄 How to refresh eval snapshot"):
            st.code("""
# Free evals — guardrails + component logic ($0.00)
python evals/run_evals.py --free

# With RAG + LLM-as-judge (~$0.10)
python evals/run_evals.py --no-pipeline

# Full suite including end-to-end pipeline (~$1.10)
python evals/run_evals.py

# Commit snapshot → dashboard auto-updates
git add docs/eval_results.json
git commit -m "docs: update eval snapshot"
git push
            """, language="bash")
