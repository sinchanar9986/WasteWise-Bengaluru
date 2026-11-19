# 🌿 Waste Wise Bengaluru
### AI-Powered Capacity-Constrained Waste Processing Allocator
**IBM Bob Hackathon — Problem Statement 16**

> ⚠️ **All facility data is SIMULATED** — not verified operational BBMP data. For demonstration purposes only.

---

## Overview

An end-to-end agentic AI system that allocates Bengaluru's segregated municipal solid waste to suitable processing facilities. The system validates material compatibility, tracks facility capacity, explains every allocation decision, and re-plans automatically when a facility becomes unavailable.

### Three AI Agents

| Agent | File | Responsibility |
|---|---|---|
| **Load Intake Agent** | `agents/load_intake.py` | Parses natural-language and structured waste requests using IBM Granite LLM (regex fallback) |
| **Capacity Allocation Agent** | `agents/capacity_allocator.py` | Deterministic Python allocation engine — compatibility check, capacity-aware selection, decision trace |
| **Scenario Analysis Agent** | `agents/scenario_analyst.py` | Plain-English explanations via Granite, facility closure detection, re-planning |

---

## Tech Stack

- **IBM Granite LLM** via watsonx.ai REST API — NL parsing and explanation generation
- **Python 3.11 + Flask** — backend API
- **SQLite** — zero-install database (MySQL-ready schema in `data/schema.sql`)
- **HTML5 + CSS3 + Vanilla JS** — single-file dashboard (`index.html`)

---

## Quick Start

### 1. Clone and install
```bash
git clone <repo-url>
cd waste-wise-bengaluru
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — add your IBM watsonx.ai credentials
```

`.env` variables:
```
DB_PATH=wastewise.db
WATSONX_API_KEY=your_ibm_watsonx_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

> The app works without a Granite key — it falls back to regex parsing and template explanations automatically.

### 3. Run
```bash
python app.py
```

### 4. Open browser
Navigate to **http://localhost:5000**

The SQLite database is created and seeded automatically on first run — no SQL commands needed.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/allocate` | Allocate waste — accepts `raw_input` (NL) or structured `{waste_type, quantity_tons, origin}` |
| `GET` | `/api/facilities` | Current facility state with capacity |
| `POST` | `/api/close-facility` | Close a facility and trigger re-planning |
| `POST` | `/api/compare` | Compare first-compatible vs capacity-aware strategies (read-only) |
| `GET` | `/api/stats` | Dashboard totals |

---

## Demo Scenarios

### 1. Normal NL Allocation
Type in the natural language box: `Allocate 8 tons of organic waste from Yelahanka`
→ See the 7-step Decision Trace and Granite-generated explanation.

### 2. Excess Demand
Set Waste Type: `organic`, Quantity: `500` tons
→ See partial allocation with ⚠ unallocated quantity warning.

### 3. Facility Closure + Re-planning
Click **🚫 Close** on any facility row
→ See the 4-stage re-planning panel: `Facility Closed → Affected Identified → Re-planning → New Allocation`

---

## Project Structure

```
waste-wise-bengaluru/
├── app.py                    # Flask API — 6 endpoints
├── db.py                     # SQLite helpers (auto-creates DB on import)
├── requirements.txt
├── .env.example              # Environment variable template
├── agents/
│   ├── load_intake.py        # Load Intake Agent (Granite + regex fallback)
│   ├── capacity_allocator.py # Capacity Allocation Agent (pure Python)
│   └── scenario_analyst.py  # Scenario Analysis Agent (explanations + re-planning)
├── data/
│   ├── schema.sql            # MySQL-compatible schema (reference)
│   └── seed.sql              # Simulated facility data (reference)
├── index.html                # Single-file frontend dashboard
├── demo_script.md            # Judge demo walkthrough
└── setup.md                  # Setup instructions
```

---

## Guardrails

The system enforces these constraints at all times:
- No negative or zero quantities
- No unknown waste types
- No allocation to closed facilities
- No incompatible material allocation
- No capacity overflow (never exceeds `remaining_capacity_tons`)
- Clearly distinguishes simulated data from verified operational data

---

## Hackathon

**Problem Statement 16** — Waste Wise Bengaluru: Capacity-Constrained Waste Processing Allocator  
Domain: Circular Economy, Solid Waste Management & Resource Allocation  
Built with **IBM Bob** · **IBM Granite LLM** · **IBM watsonx.ai**
