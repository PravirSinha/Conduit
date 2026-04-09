<div align="center">

# CONDUIT
### Multi-Agent Automotive Service Intelligence Platform

*An end-to-end AI pipeline that transforms a customer complaint into a fully priced, approved repair order — autonomously.*

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B35?style=flat-square&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-000000?style=flat-square&logo=pinecone&logoColor=white)](https://pinecone.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-Containerised-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![LangSmith](https://img.shields.io/badge/LangSmith-Observability-1C3C3C?style=flat-square&logo=langchain&logoColor=white)](https://smith.langchain.com)
[![DeepEval](https://img.shields.io/badge/DeepEval-LLM_Evals-7C3AED?style=flat-square&logo=checkmarx&logoColor=white)](https://docs.confident-ai.com)
[![GCP](https://img.shields.io/badge/GCP-Cloud_Run_+_Cloud_SQL-4285F4?style=flat-square&logo=googlecloud&logoColor=white)](https://cloud.google.com)
[![Tests](https://img.shields.io/badge/Tests-159_passing-22C55E?style=flat-square&logo=pytest&logoColor=white)](./tests)
[![Evals](https://img.shields.io/badge/Evals-87_passing-22C55E?style=flat-square&logo=checkmarx&logoColor=white)](./evals)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white)](./github/workflows)

</div>

---

## What Is CONDUIT?

CONDUIT is a **production-grade multi-agent AI system** built for automotive service centres. A service advisor enters a customer complaint — *"grinding noise from front brakes, pedal feels soft"* — and five specialised AI agents work in sequence to classify the fault, check inventory, price the job, manage the transaction, and trigger parts replenishment if needed.

The entire pipeline runs in under 45 seconds with real-time visibility via Server-Sent Events streaming.

> **Why this matters:** Traditional automotive service workflows involve manual lookup across 3-4 systems, paper-based quoting, and no intelligent prioritisation. CONDUIT collapses that into a single, auditable AI pipeline with full observability.

---

## Live Demo

| Service | URL |
|---------|-----|
| **Streamlit Dashboard** | https://conduit-dashboard-577817366021.asia-south1.run.app |
| **FastAPI Backend** | https://conduit-577817366021.asia-south1.run.app |
| **API Docs** | https://conduit-577817366021.asia-south1.run.app/docs |
| **Health Check** | https://conduit-577817366021.asia-south1.run.app/health |

---

## Architecture Overview

```
Customer Complaint
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    CONDUIT PIPELINE                           │
│                                                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐       │
│  │   INTAKE    │───▶│  INVENTORY  │───▶│   QUOTING   │       │
│  │   AGENT     │    │   AGENT     │    │   AGENT     │       │
│  │             │    │             │    │             │       │
│  │ GPT-4o      │    │ Pinecone    │    │ GST + Disc. │       │
│  │ Classify    │    │ Semantic    │    │ OEM vs AM   │       │
│  │ fault type  │    │ parts search│    │ Loyalty     │       │
│  └─────────────┘    └─────────────┘    └─────────────┘       │
│         │                                      │             │
│         ▼                                      ▼             │
│  ┌─────────────┐                    ┌─────────────┐          │
│  │ REPLENISH.  │◀───────────────────│ TRANSACTION │          │
│  │   AGENT     │                    │   AGENT     │          │
│  │             │                    │             │          │
│  │ PO raising  │                    │ HITL logic  │          │
│  │ Reorder qty │                    │ Auto-approve│          │
│  └─────────────┘                    └─────────────┘          │
│                                                               │
│              LangGraph StateGraph + SSE Streaming             │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
   Completed Repair Order (DB) + Streamlit Dashboard
```

**Full architecture diagram:** see [`docs/architecture.md`](./docs/architecture.md)

---

## Key Features

### 5 Specialised LangGraph Agents

| Agent | Responsibility | Technology |
|-------|---------------|------------|
| **Intake** | Classifies fault type, urgency, required parts from natural language complaint | GPT-4o, Pinecone RAG |
| **Inventory** | Semantic search for compatible parts, reserves stock, checks compatibility | Pinecone vector DB |
| **Quoting** | Prices job with GST, loyalty discounts, OEM vs aftermarket options | Deterministic pricing engine |
| **Transaction** | Manages approval flow, HITL triggers for EV/high-value jobs | LangGraph interrupt |
| **Replenishment** | Raises purchase orders for depleted stock automatically | Forecast-driven reorder logic |

### Real-Time Pipeline Streaming
Every agent state transition is streamed to the dashboard via **Server-Sent Events (SSE)** — service advisors see the pipeline progress live, not just the final result.

### Human-in-the-Loop (HITL)
CONDUIT supports **two HITL gates** with independent toggles:

1) **Intake HITL (Supervisor review)** — pauses when the complaint is ambiguous and the system cannot confidently identify parts.
        - Triggers when: `intake_confidence < 0.70` OR `required_parts=[]` OR `fault_classification == "UNKNOWN"`
        - Supervisor can override with catalog parts, custom materials, and labor-only/inspection-only entries.

2) **Transaction HITL (Advisor approval)** — pauses before confirming inventory allocation and progressing the RO.
        - Triggers when: EV jobs, recall jobs, high-value quotes (above threshold), or low-confidence intake
        - Threshold is configurable via `AUTO_APPROVE_THRESHOLD` (default ₹50,000)

Feature flags:
- `INTAKE_HITL_ENABLED` (preferred)
- `TRANSACTION_HITL_ENABLED` (preferred)
- `HITL_ENABLED` (legacy alias; enables both when set)

### Financial Accuracy
- 18% GST calculated on post-discount amount (regulatory compliance)
- Loyalty tier discounts (Bronze 5% → Platinum 30%)
- OEM vs aftermarket pricing (aftermarket = 72% of OEM)
- Discount cap enforced at 30% regardless of loyalty tier
- Recall jobs: 100% manufacturer coverage

### Semantic Parts Search
Parts catalog embedded in Pinecone. When an intake agent identifies *"brake pads"*, it retrieves the top 5 compatible parts by semantic similarity — not keyword matching — filtered by vehicle make, model, year, and fuel type.

---

## Data Architecture

CONDUIT uses two data stores that serve fundamentally different purposes. Understanding why helps explain how the AI pipeline works.

### The Short Version

> **PostgreSQL** knows *who* the customer is, *what* vehicle they drive, and *what happened* in every past repair.  
> **Pinecone** knows *what parts exist* and can find the right ones from a plain-English description.  
> **GPT-4o** receives context from both and makes the decision.

---

### PostgreSQL — Operational Records

PostgreSQL is the system of record. Every transaction, every decision, every approval is written here permanently. It stores nine tables:

```
customers          Who the customer is, their loyalty tier, contact details
vehicles           VIN registry — make, model, year, fuel type, recall status
repair_orders      Every RO created — status, fault category, classification payload
quotes             Line-item pricing for every RO — parts, labour, GST breakdown
inventory          Current stock levels and reorder thresholds for every part
purchase_orders    Auto-raised POs when stock depletes — supplier, quantity, cost
parts              Master parts catalog with pricing, OEM codes, compatibility
suppliers          Supplier registry with lead times and reliability scores
recalls            Active manufacturer recalls keyed by make, model, year
```

**When a new repair order comes in**, the intake agent queries PostgreSQL for three things before GPT-4o sees a single word of the complaint:

- The vehicle record (make, model, year, fuel type, EV flag) — so the AI knows what it is working with
- The customer record (loyalty tier) — so discounts are applied correctly downstream
- Active recall flags for this vehicle — so safety-critical issues are never missed

This structured context goes into the GPT-4o prompt alongside the complaint. PostgreSQL is not doing any AI work — it is providing the factual ground truth that the AI reasons over.

---

### Pinecone — Parts Intelligence

Pinecone stores the parts catalog as vector embeddings — a mathematical representation of what each part is and what it is used for. This enables semantic search: finding the right part from a human description rather than an exact keyword or part number.

```
Customer says:   "grinding noise from front wheels when braking"
                              ↓
Pinecone finds:  BRK-PAD-HON-F-01  Honda Civic Front Brake Pad Set     (0.94 similarity)
                 BRK-ROT-HON-F-01  Honda Civic Front Brake Rotor        (0.91 similarity)
                 BRK-CAL-HON-F-01  Honda Civic Front Brake Caliper      (0.87 similarity)
                 BRK-FLD-UNI-001   Brake Fluid DOT4 Universal           (0.81 similarity)
                 BRK-HSE-HON-F-01  Honda Civic Brake Hose Front         (0.79 similarity)
```

The top 5 results are filtered by vehicle make and fuel type, then passed to GPT-4o as candidate parts. GPT-4o then confirms which parts are actually required based on the full complaint context. Pinecone narrows the search space; GPT-4o makes the final call.

---

### How Both Feed Into a Single Decision

```
Customer complaint: "grinding noise, brakes feel soft"
        │
        ├── PostgreSQL ──▶  Vehicle: 2022 Honda City, Petrol, not EV
        │                   Customer: Priya S., Gold loyalty tier
        │                   Recalls: No active recalls
        │
        ├── Pinecone ────▶  Top 5 parts by semantic similarity
        │                   (brake pads, rotors, caliper, fluid, hose)
        │
        └── GPT-4o ──────▶  Receives all of the above
                            Returns:
                            - Fault: BRAKE_SYSTEM
                            - Parts required: pads + rotors
                            - Urgency: HIGH (safety critical)
                            - Confidence: 0.92
                            - EV protocol: false
```

No single component makes the decision. PostgreSQL provides context, Pinecone provides candidate parts, and GPT-4o synthesises both into a structured classification that flows into the rest of the pipeline.

---

## Tech Stack

```
Layer               Technology
──────────────────────────────────────────────────────
AI Agents           LangGraph 0.2 + OpenAI GPT-4o
Vector Search       Pinecone (semantic parts catalog)
Orchestration       LangGraph StateGraph
API                 FastAPI + Uvicorn (SSE streaming)
Dashboard           Streamlit (7 pages, real-time)
Database            PostgreSQL 15 + SQLAlchemy + Alembic
Observability       LangSmith (traces) + DeepEval (evals)
Testing             pytest (159 tests) + custom evals (87 tests)
CI/CD               GitHub Actions
Infrastructure      GCP Cloud Run + GCP Cloud SQL + GCP Artifact Registry
Containerisation    Docker
```

---

## Observability & Evals

CONDUIT uses **two layers** that serve different purposes:

- **LangSmith (live production observability)**
        - Every pipeline run is traced with latency + cost.
        - Used for debugging, performance monitoring, and cost governance.

- **Evals (offline quality + guardrails)**
        - `python evals/run_evals.py` runs the eval suite and writes a **static snapshot** JSON.
        - The Streamlit **Evals tab reads** `docs/eval_results.json`.
        - Viewing the Evals tab is always **$0.00** (no LLM calls are triggered).

Refresh workflow for the deployed dashboard snapshot:

```bash
# $0.00 deterministic smoke suite
python evals/run_evals.py --free

# Commit the refreshed snapshot so the dashboard updates
git add docs/eval_results.json
git commit -m "docs: refresh eval snapshot"
git push origin main
```

---

## Demo Queries (HITL vs Non-HITL)

Use these as ready-made `complaint_text` examples for demos/interviews.

### Cases where HITL is typically NOT required (happy path)
- "Routine service: oil change and oil filter replacement. No warning lights."
- "Grinding noise from front brakes when braking. Please replace brake pads."
- "Battery is weak, car slow to crank in the morning. Replace 12V battery." (non-EV)
- "Front suspension clunk over speed bumps. Inspect and replace shock absorbers if needed."
- "Regular maintenance: replace air filter and cabin filter."

### Cases where HITL SHOULD be required

**Intake HITL (supervisor review)** — ambiguous / unknown / no parts:
- "Rear bumper dent and repaint required. Bodywork + paint."
- "Water leakage inside cabin during rain. Need diagnosis."
- "Rattle noise sometimes from dashboard area, intermittent. Not sure when it happens."

**Transaction HITL (advisor approval)** — EV / recall / high value:
- "EV battery warning light on, reduced power mode. Suspect high-voltage battery issue." (EV VIN)
- "Timing belt replacement + water pump replacement; full service." (often high value)
- "Customer came in for manufacturer recall repair. Perform recall service." (VIN with recall)

Tip for deterministic demos: set `AUTO_APPROVE_THRESHOLD` low (e.g., `10000`) to force advisor approval on most quotes.

---

## Project Structure

```
Conduit/
├── agents/                     # 5 LangGraph agents
│   ├── intake_agent.py         # Fault classification + RAG
│   ├── inventory_agent.py      # Parts search + reservation
│   ├── quoting_agent.py        # Pricing + GST + discounts
│   ├── transaction_agent.py    # HITL + approval flow
│   └── replenishment_agent.py  # PO generation + reorder
│
├── api/                        # FastAPI application
│   ├── main.py                 # App entry point + middleware
│   └── routes/                 # 7 route modules
│       ├── repair_orders.py    # RO CRUD + SSE streaming
│       ├── vehicles.py
│       ├── customers.py
│       ├── parts.py
│       ├── inventory.py
│       ├── suppliers.py
│       └── dashboard.py
│
├── dashboard/                  # Streamlit frontend
│   └── app.py                  # 7 pages: pipeline, ROs, inventory...
│
├── database/
│   ├── models.py               # 9 SQLAlchemy models
│   ├── connection.py           # Session management
│   └── migrations/             # Alembic migrations
│
├── tools/                      # Shared agent tools
│   ├── inventory_tools.py      # Pinecone search + compatibility
│   └── pricing_tools.py        # GST, discounts, line items
│
├── evals/                      # Evaluation framework
│   ├── guardrails/             # Deterministic validation ($0.00)
│   ├── component/              # Per-agent quality evals
│   ├── rag/                    # Pinecone retrieval quality
│   ├── pipeline/               # End-to-end evals
│   ├── datasets/               # Ground truth JSON cases
│   └── run_evals.py            # Master runner
│
├── tests/                      # pytest test suite
│   ├── unit/                   # 38 unit tests
│   ├── integration/            # 22 API integration tests
│   └── agents/                 # 99 agent tests
│
├── data/synthetic/             # Synthetic data generation
│   └── generate_all.py         # Seeds 500 vehicles, 28 parts
│
├── orchestrator.py             # LangGraph pipeline definition
├── config.py                   # Environment configuration
└── .github/workflows/
    ├── ci.yml                  # Lint + test on every push
    └── deploy.yml              # Build → Artifact Registry → Cloud Run on merge
```

---

## Evaluation Framework

CONDUIT has a two-layer evaluation strategy:

### Layer 1 — Guardrails ($0.00, runs on every CI push)
Deterministic validation of every agent's output schema. Zero tolerance.

```
✓ Intake Guardrails      18 tests   Safety overrides, field validation
✓ Quoting Guardrails     13 tests   GST accuracy, discount caps
✓ Output Validators      18 tests   All agent output schemas
```

### Layer 2 — Quality Evals (LLM-based, runs at deployment)
```
✓ Inventory Agent         6 tests   100% compatibility accuracy
✓ Quoting Agent           8 tests   100% GST accuracy across all amounts
✓ Transaction Agent      15 tests   HITL trigger logic, boundary cases
✓ Replenishment Agent     9 tests   Reorder quantity accuracy
~ Intake Agent (LLM)             ~$0.20   Classification + safety
~ RAG Retrieval                  ~$0.05   Pinecone precision/recall
~ Full Pipeline                  ~$0.80   End-to-end success rate
```

**Total: 87 tests passing, $0.00 for free tier**

---

## Observability

### LangSmith
Every pipeline run is traced in LangSmith:
- Per-agent latency breakdown
- Token cost per repair order
- Input/output for every LLM call
- Pipeline success/failure rates

Set `LANGCHAIN_TRACING_V2=true` in `.env` to enable.

### DeepEval
LLM-as-judge metrics for intake classification quality:
- Hallucination rate (did agent invent parts not in catalog?)
- Faithfulness (did agent use retrieved context?)
- Answer relevancy

---

## Getting Started

### Prerequisites
```
Python 3.11
PostgreSQL 15
OpenAI API key
Pinecone API key (free tier sufficient)
```

### Local Setup

```bash
# 1. Clone
git clone https://github.com/PravirSinha/Conduit.git
cd conduit

# 2. Virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Environment variables
cp .env.example .env
# Edit .env — add OPENAI_API_KEY, PINECONE_API_KEY, DATABASE_URL

# 5. Database setup
alembic upgrade head

# 6. Seed data
python data/synthetic/generate_all.py

# 7. Start API
uvicorn api.main:app --reload --port 8000

# 8. Start Dashboard (new terminal)
streamlit run dashboard/app.py --server.port 8501
```

**API:** http://localhost:8000  
**Dashboard:** http://localhost:8501  
**API Docs:** http://localhost:8000/docs

### Docker

```bash
docker-compose up --build
```

### Run Tests

```bash
# Full test suite
pytest tests/ -v

# Free evals only ($0.00)
python evals/run_evals.py --free

# Full eval suite (~$1.00)
python evals/run_evals.py
```

---

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=conduit-parts-catalog
DATABASE_URL=postgresql://user:pass@localhost:5432/conduit

# App Config
ENVIRONMENT=development
HITL_ENABLED=false          # true = pause for human approval
AUTO_APPROVE_THRESHOLD=50000  # ₹ above which HITL triggers
LOG_LEVEL=INFO

# Observability (optional)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=...
LANGSMITH_PROJECT=conduit-portfolio
```

---

## Deployment

CONDUIT is deployed on Google Cloud Platform with:
- **Cloud Run** — serverless container hosting for FastAPI backend and Streamlit dashboard (auto-scales, no server management)
- **Cloud SQL PostgreSQL 15** — managed database (private, accessed via Unix socket)
- **Artifact Registry** — Docker image registry
- **GitHub Actions** — CI/CD pipeline (ci.yml → deploy.yml)

Deployment is triggered automatically on push to `main` after all tests pass. HITL flags and all secrets are managed via GitHub Secrets — update a secret, re-run the deploy workflow, and Cloud Run picks up the new value automatically.

---

## Design Decisions

**Why LangGraph over a simple chain?**  
Each agent has independent validation mechanism, guardrails, and retry logic. LangGraph's StateGraph makes it easy to pause the pipeline (HITL), resume after human approval, and inspect state at any node — something a simple sequential chain cannot do cleanly.

**Why Pinecone for parts search?**  
Customers don't describe faults in part numbers. *"Grinding noise from front wheels"* needs to map to `BRK-PAD-HON-F-01`. Semantic search handles this naturally; keyword search would require extensive synonym mapping.

**Why SSE over WebSockets?**  
SSE is unidirectional (server → client) which is exactly what pipeline streaming needs. Simpler to implement, no connection management overhead, works through standard HTTP proxies.

**Why separate Quoting guardrails?**  
GST miscalculation is a regulatory violation, not just a bug. By running deterministic validation on every quote output before DB write, we ensure 100% financial accuracy regardless of LLM behaviour.

**Why Cloud Run over a VM?**  
Cloud Run eliminates server management entirely — no patching, no capacity planning, no SSH keys. For a portfolio project that needs to be reliably accessible to recruiters at any time, serverless auto-scaling is the right trade-off.

---

## Engineering Reflections

Building CONDUIT surfaced decisions that don't show up in tutorials — the kind that only emerge when a system has to actually work end-to-end.

**Multi-agent state is a first-class concern.**  
Chaining five agents is straightforward. Making them fail gracefully, resume after a human interrupt, and pass validated state between nodes required treating the StateGraph as a core architectural primitive — not plumbing. LangGraph's interrupt mechanism turned HITL from a feature into a natural pause in the graph rather than an external hack.

**Validation belongs at the boundary, not the end.**  
GST miscalculation is a regulatory issue, not just a bug. Running deterministic guardrails on every agent's output before any DB write meant the database never saw invalid data — regardless of what the LLM returned. This pattern is now a default for any agent output that touches money or compliance.

**Two data stores, one decision.**  
The intake agent queries PostgreSQL for vehicle and customer context, Pinecone for semantically similar parts, then passes both to GPT-4o in a single prompt. Neither store makes a decision — they provide the factual grounding that makes GPT-4o's classification accurate and auditable. Keeping operational records (PostgreSQL) separate from parts intelligence (Pinecone) also means each can be scaled, queried, and maintained independently.

**Streaming is a UX decision as much as a technical one.**  
A 45-second pipeline without feedback looks broken. SSE streaming of intermediate agent states — not just the final result — gave users visibility into what the system was doing and why. The choice of SSE over WebSockets simplified the server stack significantly since the communication is strictly unidirectional.

**Eval cost discipline compounds across projects.**  
Running the full LLM eval suite on every push would cost ~$30/month. Tiering evals — deterministic guardrails on every CI run at $0.00, LLM-judge quality evals manually before each deploy at ~$1.00 — keeps the total well under $10 for the entire project lifetime. This discipline matters more as you add more AI products sharing the same API budget.

---

## Future Enhancements

The current system handles the core repair order pipeline end-to-end. The next phase focuses on making the system smarter over time using its own history.

**Historical Case Retrieval — RAG over past repair orders**  
Today, Pinecone stores the parts catalog — structured data that enables semantic parts search. The planned enhancement is to also embed completed repair orders into a separate Pinecone namespace. When a new complaint comes in, the intake agent retrieves the top-k most similar past cases alongside the fault classification. This gives the agent context like: *"The last 3 Honda City brake complaints with this symptom pattern required caliper replacement, not just pad replacement"* — improving diagnosis accuracy and quoting precision for complex or recurring faults.

**PostgreSQL as the Formalised Historical Record Layer**  
PostgreSQL already stores every repair order, quote, and purchase order with full timestamps. The enhancement formalises this as a queryable case history — enabling the system to surface recurring faults by vehicle model, parts that consistently need co-replacement, seasonal fault patterns, and supplier reliability over time. This structured history feeds both the RAG layer above and reporting dashboards for service managers.

**Predictive Replenishment**  
Currently the replenishment agent raises POs reactively when stock falls below reorder point. With historical demand data in PostgreSQL, the next step is a simple forecast model — rolling average with seasonality — that anticipates demand before stockouts occur, particularly for high-velocity parts like filters and brake pads.

**Agent Memory Across Sessions**  
Returning customers with known fault history, vehicle quirks, or loyalty status currently require re-entering context. Persisting a lightweight customer and vehicle profile in PostgreSQL and injecting it into the intake agent's context window would make the system progressively more accurate for repeat customers.

**DeepEval Online Evaluation — Sampling Mode**  
Rather than running quality evals only at deploy time, a low-cost enhancement is to run DeepEval on a 5% random sample of production repair orders — catching regression in classification quality without the cost of evaluating every request.

---

## Author

Built by **Pravir Sinha**  

---

<div align="center">
<sub>Powered by GPT-4o, Pinecone, and an unreasonable number of guardrails</sub>
</div>