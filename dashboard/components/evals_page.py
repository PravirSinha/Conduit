"""CONDUIT — Evals Dashboard
Tab 1: Eval Quality  — all pass/fail metrics, guardrails, LLM accuracy, RAG, LLM-as-judge
Tab 2: Cost & Latency — live per-run tracking + short cost guide
"""

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
    "run_at": "2026-04-10T12:03:00Z",
    "all_passed": True,
    "passed": 10, "failed": 0, "total": 10,
    "total_elapsed": 498.0,
    "headline_metrics": [
        {"id": "system_pass_rate",               "value": 100},
        {"id": "intake_classification_accuracy", "value": 80.0},
        {"id": "rag_recall_at_5",                "value": 100.0},
    ],
    "eval_metrics": {
        "Fault Classification Accuracy":  {"eval": "Fault Classification Accuracy",  "pass_rate": 80.0,  "passed": 8,  "failed": 2,  "total": 10},
        "Urgency Accuracy":               {"eval": "Urgency Accuracy",               "pass_rate": 90.0,  "passed": 9,  "failed": 1,  "total": 10},
        "LLM Judge: Diagnosis Relevance": {"eval": "LLM Judge: Diagnosis Relevance", "pass_rate": 100.0, "passed": 10, "failed": 0,  "total": 10},
        "LLM Judge: Hallucination Check": {"eval": "LLM Judge: Hallucination Check", "pass_rate": 100.0, "passed": 10, "failed": 0,  "total": 10},
        "LLM Judge: Technician Clarity":  {"eval": "LLM Judge: Technician Clarity",  "pass_rate": 100.0, "passed": 10, "failed": 0,  "total": 10},
        "RAG Precision@5":                {"eval": "RAG Precision@5",                "pass_rate": 100.0, "passed": 5,  "failed": 0,  "total": 5},
        "RAG Recall@5":                   {"eval": "RAG Recall@5",                   "pass_rate": 100.0, "passed": 5,  "failed": 0,  "total": 5},
        "RAG Relevance Score":            {"eval": "RAG Relevance Score",            "pass_rate": 100.0, "passed": 5,  "failed": 0,  "total": 5},
        "GST Calculation Accuracy":       {"eval": "GST Calculation Accuracy",       "pass_rate": 100.0, "passed": 5,  "failed": 0,  "total": 5},
        "Parts Compatibility Accuracy":   {"eval": "Parts Compatibility Accuracy",   "pass_rate": 100.0, "passed": 5,  "failed": 0,  "total": 5},
        "Quoting Dataset Accuracy":       {"eval": "Quoting Dataset Accuracy",       "pass_rate": 100.0, "passed": 4,  "failed": 0,  "total": 4},
        "Reorder Quantity Accuracy":      {"eval": "Reorder Quantity Accuracy",      "pass_rate": 100.0, "passed": 4,  "failed": 0,  "total": 4},
    },
    "modules": [
        {"label": "Intake Guardrails",        "passed": True,  "cost": "$0.00",  "elapsed_s": 6.4},
        {"label": "Quoting Guardrails",       "passed": True,  "cost": "$0.00",  "elapsed_s": 7.2},
        {"label": "Output Validators",        "passed": True,  "cost": "$0.00",  "elapsed_s": 7.6},
        {"label": "Inventory Agent",          "passed": True,  "cost": "$0.00",  "elapsed_s": 6.2},
        {"label": "Quoting Agent",            "passed": True,  "cost": "$0.00",  "elapsed_s": 6.2},
        {"label": "Transaction Agent",        "passed": True,  "cost": "$0.00",  "elapsed_s": 8.2},
        {"label": "Replenishment Agent",      "passed": True,  "cost": "$0.00",  "elapsed_s": 6.3},
        {"label": "Intake Agent (LLM)",       "passed": True,  "cost": "~$0.20", "elapsed_s": 135.2},
        {"label": "RAG Retrieval (Pinecone)", "passed": True,  "cost": "~$0.05", "elapsed_s": 119.4},
        {"label": "LLM-as-Judge (Diagnosis)", "passed": True,  "cost": "~$0.05", "elapsed_s": 195.6},
    ],
}

GPT4O_INPUT_PER_1K  = 0.005
GPT4O_OUTPUT_PER_1K = 0.015
EMBED_PER_1K        = 0.0001
INTAKE_IN   = 800
INTAKE_OUT  = 400
EMBED_TOKS  = 200
COST_PER_RUN = INTAKE_IN/1000*GPT4O_INPUT_PER_1K + INTAKE_OUT/1000*GPT4O_OUTPUT_PER_1K + EMBED_TOKS/1000*EMBED_PER_1K


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


def _bar(label, pass_rate, passed, total, desc=""):
    """Renders a metric row with inline progress bar — pure st.markdown, no nested HTML issues."""
    color = "#15803d" if pass_rate >= 90 else "#ca8a04" if pass_rate >= 70 else "#dc2626"
    bar_w = min(int(pass_rate), 100)
    sub   = f'<div style="font-size:0.71rem;color:#64748b;margin-top:1px;">{desc}</div>' if desc else ""
    st.markdown(f"""
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;
                padding:11px 16px;margin-bottom:6px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-weight:600;font-size:0.86rem;color:#1c1917;">{label}</span>
          {sub}
          <div style="font-size:0.70rem;color:#94a3b8;margin-top:1px;">{passed}/{total} cases</div>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:1.05rem;
                     font-weight:700;color:{color};">{pass_rate:.0f}%</span>
      </div>
      <div style="background:#e2e8f0;border-radius:3px;height:4px;margin-top:7px;">
        <div style="background:{color};border-radius:3px;height:4px;width:{bar_w}%;"></div>
      </div>
    </div>""", unsafe_allow_html=True)


def _module_row(label, passed, cost, elapsed):
    ok     = passed
    bg     = "#f0fdf4" if ok else "#fef2f2"
    border = "#16a34a" if ok else "#dc2626"
    sc     = "#15803d" if ok else "#991b1b"
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:8px;
                padding:10px 16px;margin-bottom:5px;
                display:flex;align-items:center;justify-content:space-between;">
      <div style="display:flex;align-items:center;gap:10px;">
        <span>{"✅" if ok else "❌"}</span>
        <div>
          <div style="font-weight:600;font-size:0.86rem;color:#1c1917;">{label}</div>
          <div style="font-size:0.70rem;color:#64748b;">Cost: {cost} · {elapsed:.1f}s</div>
        </div>
      </div>
      <span style="font-weight:700;font-size:0.76rem;color:{sc};letter-spacing:0.04em;">
        {"PASSED" if ok else "FAILED"}
      </span>
    </div>""", unsafe_allow_html=True)


def _get_live_runs():
    """Return recent pipeline runs with per-agent latency from agent_audit_log."""
    try:
        sys.path.insert(0, ROOT)
        from database.connection import get_session
        from database.models import AgentAuditLog
        cutoff = datetime.utcnow() - timedelta(days=7)
        with get_session() as db:
            rows = (
                db.query(
                    AgentAuditLog.ro_id,
                    AgentAuditLog.agent_name,
                    AgentAuditLog.latency_ms,
                    AgentAuditLog.created_at,
                )
                .filter(
                    AgentAuditLog.action == "agent_end",
                    AgentAuditLog.created_at >= cutoff,
                    AgentAuditLog.latency_ms.isnot(None),
                )
                .order_by(AgentAuditLog.created_at.desc())
                .limit(250)
                .all()
            )

        from collections import defaultdict
        runs = defaultdict(lambda: {"agents": {}, "ts": None})
        for r in rows:
            runs[r.ro_id]["agents"][r.agent_name] = r.latency_ms
            if runs[r.ro_id]["ts"] is None:
                runs[r.ro_id]["ts"] = r.created_at

        AGENTS = ["intake_agent", "inventory_agent", "quoting_agent",
                  "transaction_agent", "replenishment_agent"]
        LABELS = {"intake_agent": "Intake", "inventory_agent": "Inventory",
                  "quoting_agent": "Quoting", "transaction_agent": "Transaction",
                  "replenishment_agent": "Replenish"}

        result = []
        for ro_id, data in list(runs.items())[:20]:
            agents = data["agents"]
            total_ms = sum(agents.values())
            intake_ms = agents.get("intake_agent", 0)
            cost = COST_PER_RUN
            row = {
                "ro_id":    ro_id,
                "ts":       data["ts"],
                "total_ms": total_ms,
                "total_s":  round(total_ms / 1000, 1),
                "cost":     cost,
                "intake_ms": intake_ms,
            }
            for a in AGENTS:
                row[LABELS[a]] = agents.get(a, 0)
            result.append(row)

        return result, LABELS
    except Exception as e:
        return [], {}


def render_evals():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
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

    summary = _load_snapshot()
    is_demo = summary.get("_demo", False)
    run_at  = summary.get("run_at", "")

    if is_demo:
        st.info("**Demo mode** — representative results shown. "
                "Run `python evals/run_evals.py --no-pipeline` and commit `docs/eval_results.json` for live numbers.",
                icon="🧪")
    else:
        st.markdown(f"""
        <div style="display:inline-flex;align-items:center;gap:8px;background:#f0fdf4;
                    border:1px solid #bbf7d0;border-radius:20px;
                    padding:4px 14px;font-size:0.78rem;color:#15803d;margin-bottom:14px;">
            ✓ Live snapshot · {_fmt_date(run_at)} · $0.00 to view
        </div>""", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🤖 Agent Health", "💰 Cost & Latency"])

    # ═══════════════════════════════════════════════════════════
    # TAB 1 — EVAL QUALITY
    # ═══════════════════════════════════════════════════════════
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

        # ── Status banner ─────────────────────────────────────
        if all_passed:
            st.markdown(f"""
            <div style="background:#f0fdf4;border:1.5px solid #16a34a;border-radius:10px;
                        padding:14px 20px;margin-bottom:18px;display:flex;align-items:center;gap:12px;">
              <span style="font-size:1.4rem;">✅</span>
              <div>
                <div style="font-size:0.95rem;font-weight:600;color:#15803d;">
                  {passed}/{total} eval modules passing — system is production ready
                </div>
                <div style="font-size:0.74rem;color:#166534;margin-top:2px;">
                  Last run: {_fmt_date(run_at)} · {elapsed:.0f}s total
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
        else:
            bad = [m["label"] for m in modules if not m.get("passed")]
            st.error(f"**{summary.get('failed',0)} module(s) failing:** {', '.join(bad)}")

        # ── KPI row ────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("System Pass Rate", _pct(_val("system_pass_rate", round(passed/total*100) if total else 0)))
        with c2: st.metric("LLM Accuracy", _pct(_val("intake_classification_accuracy")),
                           help="GPT-4o fault classification vs 10 labelled ground truth cases")
        with c3: st.metric("RAG Recall@5", _pct(_val("rag_recall_at_5")),
                           help="Expected parts found in Pinecone top-5 results")
        with c4:
            ng = len([m for m in modules if any(x in m.get("label","") for x in {"Guardrail","Validator"})])
            st.metric("Active Guardrails", ng, help="Deterministic checks enforced on every live pipeline run")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SECTION 1: Guardrails ──────────────────────────────
        st.markdown("**🛡️ Rule-Based Guardrails — $0.00, run on every live pipeline execution**")
        with st.expander("View all 14 guardrail checks"):
            st.markdown("""
**Intake (5):** required fields · fault_classification enum (7 values) · urgency enum · confidence ∈ [0,1] · safety override — BRAKE/EV cannot be LOW urgency

**Quoting (5):** positive total · non-empty line items · arithmetic check (subtotal + GST − discount = total ±₹1) · discount cap 30% · GST exactly 18% of post-discount amount

**Inventory / Transaction / Replenishment (4):** schema validation · non-negative quantities · quote_id required before transaction · PO values positive
            """)
        for m in [x for x in modules if any(g in x.get("label","") for g in {"Guardrail","Validator"})]:
            _module_row(m["label"], m.get("passed", False), m.get("cost","$0.00"), m.get("elapsed_s",0))

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SECTION 2: LLM Classification Accuracy ─────────────
        st.markdown("**🤖 LLM Classification Accuracy — GPT-4o vs ground truth labels (~$0.20/run)**")
        for key in ["Fault Classification Accuracy", "Urgency Accuracy"]:
            m = em.get(key)
            if m:
                _bar(key, m["pass_rate"], m["passed"], m["total"],
                     "Exact match against 10 labelled ground truth cases")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SECTION 3: LLM-as-Judge ────────────────────────────
        st.markdown("**🧑‍⚖️ LLM-as-Judge — free-text diagnosis quality (~$0.05/run)**")
        st.caption("A second GPT-4o call evaluates fault_description and technician notes for relevance, hallucination, and clarity.")
        for key in ["LLM Judge: Diagnosis Relevance", "LLM Judge: Hallucination Check", "LLM Judge: Technician Clarity"]:
            m = em.get(key)
            descs = {
                "LLM Judge: Diagnosis Relevance": "Is fault_description relevant to the complaint?",
                "LLM Judge: Hallucination Check": "Does response avoid hallucinating parts/issues not in catalog?",
                "LLM Judge: Technician Clarity":  "Would a technician clearly understand what to inspect/repair?",
            }
            if m:
                _bar(key, m["pass_rate"], m["passed"], m["total"], descs.get(key,""))
            else:
                st.caption(f"_{key} — run `python evals/run_evals.py --no-pipeline` to populate_")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SECTION 4: RAG Metrics ─────────────────────────────
        st.markdown("**🔍 RAG Retrieval Quality — Pinecone semantic search (~$0.05/run)**")
        rag_descs = {
            "RAG Precision@5":    "Of top-5 retrieved parts, what fraction are relevant?",
            "RAG Recall@5":       "Of all expected part categories, what fraction appear in top-5?",
            "RAG Relevance Score":"Average cosine similarity score (threshold ≥ 0.35 for text-embedding-3-small)",
        }
        has_rag = any(em.get(k) for k in rag_descs)
        if not has_rag:
            st.caption("_RAG metrics not in snapshot — run `python evals/run_evals.py --rag-only` (~$0.05) to populate_")
        else:
            for key, desc in rag_descs.items():
                m = em.get(key)
                if m:
                    _bar(key, m["pass_rate"], m["passed"], m["total"], desc)

        st.markdown("<br>", unsafe_allow_html=True)

        # ── SECTION 5: Component logic ─────────────────────────
        st.markdown("**⚙️ Component Logic Accuracy — agent business rules ($0.00/run)**")
        for key in ["GST Calculation Accuracy","Parts Compatibility Accuracy",
                    "Quoting Dataset Accuracy","Reorder Quantity Accuracy"]:
            m = em.get(key)
            if m:
                _bar(key, m["pass_rate"], m["passed"], m["total"])

        # ── Hallucination note ─────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🧠 How hallucinations are prevented"):
            st.markdown("""
| Method | Mechanism | Layer |
|---|---|---|
| RAG grounding | Parts must come from Pinecone — agent cannot invent part numbers | Intake Agent |
| Enum constraints | fault_classification / urgency validated against allowed-values list | Guardrail |
| Deterministic financials | All quoting maths is pure Python — GPT-4o never touches numbers | Quoting Agent |
| Confidence threshold | < 70% confidence → routed to human HITL review, not auto-quoted | Intake Agent |
| LLM-as-judge | Second GPT-4o call checks free-text diagnosis for hallucinated content | Eval Layer |
| LangSmith tracing | Every GPT-4o prompt/response pair is logged and auditable per RO | Observability |
            """)

    # ═══════════════════════════════════════════════════════════
    # TAB 2 — COST & LATENCY
    # ═══════════════════════════════════════════════════════════
    with tab2:
        live_runs, agent_labels = _get_live_runs()

        # ── Live run tracking ──────────────────────────────────
        st.markdown("#### Pipeline Runs — Last 7 Days")

        if not live_runs:
            st.info("No pipeline data yet. Run a repair order from New Repair Order to populate live tracking.")
        else:
            # Summary KPIs
            avg_total_s = sum(r["total_s"] for r in live_runs) / len(live_runs)
            avg_cost    = sum(r["cost"] for r in live_runs) / len(live_runs)
            avg_intake  = sum(r["intake_ms"] for r in live_runs) / len(live_runs)
            llm_pct     = round(avg_intake / (avg_total_s * 10)) if avg_total_s > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Runs (7d)", len(live_runs))
            with c2: st.metric("Avg Pipeline Time", f"{avg_total_s:.1f}s")
            with c3: st.metric("Avg Cost per Run",  f"~${avg_cost:.4f}")
            with c4: st.metric("LLM % of Time",     f"{llm_pct}%",
                               help="% of pipeline time on GPT-4o (Intake Agent only)")

            st.markdown("<br>", unsafe_allow_html=True)

            # Per-run table
            import pandas as pd
            AGENT_COLS = list(agent_labels.values())
            rows = []
            for r in live_runs:
                row = {
                    "RO":            r["ro_id"],
                    "Time":          r["ts"].strftime("%d %b %H:%M") if r["ts"] else "—",
                    "Total (s)":     r["total_s"],
                    "Est. Cost ($)": f"~${r['cost']:.4f}",
                }
                for col in AGENT_COLS:
                    row[f"{col} (ms)"] = r.get(col, "—")
                rows.append(row)

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Per-agent latency bars
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("**Avg Latency by Agent (last 7 days)**")
            agent_avgs = {}
            for r in live_runs:
                for col in AGENT_COLS:
                    ms = r.get(col)
                    if ms and isinstance(ms, (int, float)) and ms > 0:
                        agent_avgs.setdefault(col, []).append(ms)
            agent_means = {k: sum(v)/len(v) for k, v in agent_avgs.items()}
            max_ms = max(agent_means.values()) if agent_means else 1
            llm_agents = {"Intake"}
            for agent, avg_ms in sorted(agent_means.items(), key=lambda x: -x[1]):
                pct   = avg_ms / max_ms * 100
                color = "#f97316" if agent in llm_agents else "#3b82f6"
                tag   = "GPT-4o" if agent in llm_agents else "deterministic"
                st.markdown(f"""
                <div style="margin-bottom:9px;">
                  <div style="display:flex;justify-content:space-between;
                              font-family:'IBM Plex Mono',monospace;font-size:0.74rem;
                              color:#334155;margin-bottom:3px;">
                    <span>{agent} <span style="color:#94a3b8;font-size:0.67rem;">· {tag}</span></span>
                    <span>{avg_ms:.0f}ms avg</span>
                  </div>
                  <div style="background:#e2e8f0;border-radius:3px;height:6px;">
                    <div style="background:{color};border-radius:3px;height:6px;width:{pct:.0f}%;"></div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("---")

        # ── Cost guide (collapsible) ───────────────────────────
        st.markdown("**Reference Guide**")

        with st.expander("💡 Why does each run cost ~$0.01?"):
            st.markdown(f"""
Only **1 of 5 agents** calls an LLM. Inventory, Quoting, Transaction, and Replenishment are 100% deterministic Python — no API calls, no variable cost.

| Component | Tokens | Est. Cost | Notes |
|---|---|---|---|
| GPT-4o — Intake classification | ~{INTAKE_IN+INTAKE_OUT} | ${INTAKE_IN/1000*GPT4O_INPUT_PER_1K + INTAKE_OUT/1000*GPT4O_OUTPUT_PER_1K:.4f} | Only LLM call in production |
| Pinecone — Semantic search | ~{EMBED_TOKS} | ${EMBED_TOKS/1000*EMBED_PER_1K:.6f} | text-embedding-3-small |
| PostgreSQL — All agents | — | $0.00 | Cloud SQL, fixed monthly |
| **Total per repair order** | — | **~${COST_PER_RUN:.4f}** | 4/5 agents deterministic |
            """)

        with st.expander("📋 Eval suite cost (run before demo/deploy)"):
            import pandas as pd
            judge_cost = 300/1000*GPT4O_INPUT_PER_1K*10 + 80/1000*GPT4O_OUTPUT_PER_1K*10
            st.dataframe(pd.DataFrame([
                {"Module": "Guardrails — 3 modules",       "Cost": "$0.00",          "When": "Every CI deploy",  "What": "87 deterministic assertions"},
                {"Module": "Component evals — 5 agents",   "Cost": "$0.00",          "When": "Every CI deploy",  "What": "Logic accuracy vs synthetic datasets"},
                {"Module": "Intake LLM accuracy",          "Cost": "~$0.20",         "When": "Pre-deploy",       "What": "10 GPT-4o calls vs ground truth"},
                {"Module": "LLM-as-judge (diagnosis)",     "Cost": f"~${judge_cost:.2f}", "When": "Pre-deploy",  "What": "10 judge calls for free-text quality"},
                {"Module": "RAG retrieval — Pinecone",     "Cost": "~$0.05",         "When": "Weekly",           "What": "Precision@5, Recall@5, cosine similarity"},
                {"Module": "Full pipeline — 5 E2E runs",   "Cost": "~$0.80",         "When": "Pre-release",      "What": "E2E success rate, latency, GST accuracy"},
                {"Module": "Total — full suite",           "Cost": "~$1.10",         "When": "—",                "What": "—"},
            ]), use_container_width=True, hide_index=True)

        with st.expander("🔍 LangSmith observability"):
            st.markdown("""
Every GPT-4o call is automatically traced to LangSmith — token counts, latency,
and prompt/response pairs are auditable per repair order.

View traces at `eu.api.smith.langchain.com` — zero extra instrumentation needed.
The `langsmith.wrappers.wrap_openai` client wrapper handles this transparently.
            """)

        with st.expander("🔄 How to refresh eval snapshot"):
            st.code("""
# Recommended before demo (~$0.30, includes LLM + RAG + LLM-as-judge)
python evals/run_evals.py --no-pipeline

# Commit to update dashboard
git add docs/eval_results.json
git commit -m "docs: update eval snapshot"
git push
            """, language="bash")
