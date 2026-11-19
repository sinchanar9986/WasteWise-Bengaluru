# Waste Wise Bengaluru — MVP Implementation Plan

## Top-Level Overview

Build a single-page, end-to-end agentic AI waste allocation system for Bengaluru's municipal solid waste.
The system is a **Python Flask backend + single HTML/CSS/JS frontend** with a MySQL database.
IBM Granite LLM handles natural-language intake; all capacity arithmetic is deterministic Python.
The MVP must be demonstrable to judges in one browser tab with no login.

**Tech stack confirmed by problem statement:**
- Backend: Python (Flask), IBM Granite LLM (via IBM watsonx.ai REST API)
- Frontend: HTML5, CSS3, Vanilla JavaScript (single `index.html`)
- Database: MySQL
- Deployment target: local or IBM Cloud (localhost for MVP)

**Non-goals (explicitly excluded):** Auth, maps, user management, real BBMP data.

---

## Architecture

```
Browser (index.html)
  │  REST/JSON
  ▼
Flask App (app.py)
  ├── /api/allocate        → Load Intake Agent → Capacity Allocation Agent
  ├── /api/facilities      → current facility state
  ├── /api/close-facility  → facility closure trigger
  ├── /api/replan          → Scenario Analysis Agent (re-planning)
  ├── /api/compare         → baseline vs capacity-aware comparison
  └── /api/stats           → dashboard totals
  │
  ├── agents/
  │   ├── load_intake.py        (Granite LLM parse or regex fallback)
  │   ├── capacity_allocator.py (pure Python deterministic logic)
  │   └── scenario_analyst.py   (explanation + re-planning)
  │
  ├── db.py                (MySQL connection + queries)
  └── data/seed.sql        (simulated facility + request seed data)
```

---

## Sub-Tasks

---

### Sub-Task 1 — Database Schema & Seed Data

**Intent**
Define the MySQL schema and populate it with clearly labelled simulated data
(facilities, accepted materials, capacity, allocations).

**Expected Outcomes**
- `data/schema.sql` creates all tables
- `data/seed.sql` inserts ≥6 simulated Bengaluru facilities with varied materials, capacities, statuses
- Running both files produces a usable database with no errors

**Todo List**
1. Create `data/schema.sql`:
   - Table `facilities`: id, name, accepted_materials (comma-separated), total_capacity_tons, used_capacity_tons, remaining_capacity_tons (computed or stored), status (OPEN/CLOSED), zone, data_label (SIMULATED)
   - Table `allocations`: id, facility_id, waste_type, quantity_tons, origin, allocated_at, status (ALLOCATED/UNALLOCATED/REALLOCATED)
   - Table `waste_requests`: id, raw_input, waste_type, quantity_tons, origin, created_at
2. Create `data/seed.sql` with 6 facilities covering: Organic, Plastic, E-Waste, Construction, Wet Waste, Dry Waste — each with realistic but clearly simulated capacities.
3. Add a `NOTE` comment at the top of seed.sql: "SIMULATED DATA — not verified operational BBMP data."

**Relevant Context**
- Facility status drives closure scenario; `remaining_capacity_tons` must never go negative.
- `accepted_materials` stored as comma-separated string for simple MVP queries.

**Status:** [x] done

---

### Sub-Task 2 — Flask App Skeleton & DB Layer

**Intent**
Bootstrap the Flask application, database connection helper, and all API route stubs so
every subsequent sub-task can plug in without restructuring.

**Expected Outcomes**
- `app.py` starts with `flask run` and returns 200 on all stub endpoints
- `db.py` provides `get_db()` and helper query functions
- `requirements.txt` lists all dependencies

**Todo List**
1. Create `requirements.txt`: flask, mysql-connector-python, requests, python-dotenv
2. Create `.env.example` with: DB_HOST, DB_USER, DB_PASS, DB_NAME, WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_URL
3. Create `db.py` with:
   - `get_connection()` using mysql-connector-python
   - `get_all_facilities()` → list of dicts
   - `get_facility_by_id(id)`
   - `update_facility_capacity(id, delta_tons)` — safely subtracts, refuses negative
   - `insert_allocation(...)` → allocation record
   - `insert_waste_request(...)` → request record
   - `get_allocations_for_facility(facility_id)`
   - `get_dashboard_stats()` → totals dict
4. Create `app.py` with Flask app, CORS enabled, and stub routes:
   - POST `/api/allocate`
   - GET `/api/facilities`
   - POST `/api/close-facility`
   - POST `/api/replan`
   - POST `/api/compare`
   - GET `/api/stats`

**Relevant Context**
- All capacity arithmetic lives in Python agents, never in SQL triggers or LLM.
- `.env` file holds secrets; never commit real keys.

**Status:** [x] done

---

### Sub-Task 3 — Load Intake Agent

**Intent**
Parse a waste request (natural language or structured form) and return structured fields:
`waste_type`, `quantity_tons`, `origin`.

**Expected Outcomes**
- `agents/load_intake.py` exports `parse_waste_request(raw_input: str) -> dict`
- Correctly parses: `"Allocate 8 tons of organic waste from Yelahanka"` → `{waste_type: "organic", quantity_tons: 8.0, origin: "Yelahanka"}`
- Falls back to regex if Granite is unavailable
- Applies guardrails: quantity > 0, known waste type

**Todo List**
1. Create `agents/load_intake.py`
2. Implement `call_granite(prompt)` using IBM watsonx.ai REST API (`/ml/v1/text/generation`)
   - Model: `ibm/granite-13b-instruct-v2` or `ibm/granite-3-8b-instruct`
   - Prompt asks Granite to extract JSON `{waste_type, quantity_tons, origin}` from the input
   - Return parsed JSON; handle API errors gracefully
3. Implement regex fallback: extract number (quantity), known waste type keyword, origin as remaining text
4. Implement guardrails:
   - Reject quantity ≤ 0
   - Reject unknown waste type (not in allowed list)
   - Return `{error: "reason"}` for invalid inputs
5. Known waste types list: `["organic", "plastic", "e-waste", "construction", "wet", "dry", "mixed"]`

**Relevant Context**
- Granite is used for NL understanding; the returned dict feeds directly into the Capacity Allocation Agent.
- If Granite API is unavailable during the demo, the regex fallback must work reliably.

**Status:** [x] done

---

### Sub-Task 4 — Capacity Allocation Agent

**Intent**
Core deterministic allocation engine. Given structured waste request fields, select the best
facility and allocate waste without violating any constraint.

**Expected Outcomes**
- `agents/capacity_allocator.py` exports `allocate(waste_type, quantity_tons, origin) -> dict`
- Returns full allocation result including: facility chosen, allocated quantity, unallocated quantity, decision trace steps
- Never allocates to closed facilities, incompatible facilities, or beyond remaining capacity
- Implements both first-compatible and capacity-aware selection (returned separately for comparison)

**Todo List**
1. Create `agents/capacity_allocator.py`
2. Implement `get_compatible_facilities(waste_type)`:
   - Query DB for facilities where `accepted_materials` contains waste_type AND status = OPEN
3. Implement `first_compatible_select(facilities, quantity)`:
   - Return first facility with remaining_capacity ≥ quantity (or first with any capacity if none fits fully)
4. Implement `capacity_aware_select(facilities, quantity)`:
   - Score each facility: prefer highest remaining capacity AND lowest utilization ratio
   - Return best-scored facility
5. Implement `allocate(waste_type, quantity_tons, origin)`:
   - Run guardrails (no negatives, no unknowns)
   - Get compatible open facilities
   - If none → return unallocated with reason
   - Run capacity-aware selection
   - If chosen facility remaining < quantity → partial allocation (allocate what fits, return unallocated remainder)
   - Call `db.update_facility_capacity()` and `db.insert_allocation()`
   - Build and return decision_trace list
6. Implement `compare_approaches(waste_type, quantity_tons)`:
   - Run both selectors on a snapshot of current facilities (read-only, no DB write)
   - Return `{first_compatible: {...}, capacity_aware: {...}}` for display

**Relevant Context**
- Capacity arithmetic is entirely in Python — LLM never touches numbers.
- `decision_trace` is a list of `{step, status, detail}` objects rendered by the frontend.

**Status:** [x] done

---

### Sub-Task 5 — Scenario Analysis Agent

**Intent**
Explain allocation decisions in plain English using Granite, handle facility closure,
and produce a re-planning result.

**Expected Outcomes**
- `agents/scenario_analyst.py` exports `explain_allocation(allocation_result)` and `replan_after_closure(facility_id)`
- Explanation is a readable English paragraph (Granite-generated or template fallback)
- `replan_after_closure` returns: affected allocations, new allocations, unallocated quantities, explanation

**Todo List**
1. Create `agents/scenario_analyst.py`
2. Implement `explain_allocation(allocation_result: dict) -> str`:
   - Build a Granite prompt from the allocation result dict
   - Ask Granite to write a 2-3 sentence plain-English explanation of the decision
   - Fallback: template string using allocation_result fields
3. Implement `replan_after_closure(facility_id: int) -> dict`:
   a. Mark facility as CLOSED in DB
   b. Fetch all ALLOCATED allocations for that facility
   c. For each affected allocation:
      - Return waste back to unallocated pool
      - Revert capacity in DB (add quantity back to closed facility record for audit)
      - Run `allocate()` from capacity_allocator for the returned waste
   d. Collect new allocations and remaining unallocated quantities
   e. Call `explain_allocation` for the overall re-plan
   f. Return structured result with before/after states
4. Implement `explain_rejection(reason: str, waste_type: str, quantity: float) -> str`:
   - Template or Granite explanation for why a request was rejected

**Relevant Context**
- Facility closure is the critical demo scenario; the before/after display is judge-facing.
- Re-planning calls the existing `allocate()` function — no duplicate logic.

**Status:** [x] done

---

### Sub-Task 6 — Flask Route Implementation

**Intent**
Wire all agents into the Flask routes so every API endpoint returns real data.

**Expected Outcomes**
- POST `/api/allocate` accepts `{raw_input}` or `{waste_type, quantity_tons, origin}` and returns full allocation result + decision trace + explanation
- GET `/api/facilities` returns current facility list with capacity state
- POST `/api/close-facility` accepts `{facility_id}` and returns re-planning result
- POST `/api/replan` manually triggers re-planning for a facility
- POST `/api/compare` accepts `{waste_type, quantity_tons}` and returns both approach results
- GET `/api/stats` returns dashboard totals

**Todo List**
1. Fill in `/api/allocate`:
   - If body has `raw_input` → call `load_intake.parse_waste_request()`
   - Else use structured fields directly
   - Call `capacity_allocator.allocate()`
   - Call `scenario_analyst.explain_allocation()`
   - Return combined JSON
2. Fill in `/api/facilities` → `db.get_all_facilities()`
3. Fill in `/api/close-facility` → `scenario_analyst.replan_after_closure(facility_id)`
4. Fill in `/api/compare` → `capacity_allocator.compare_approaches()`
5. Fill in `/api/stats` → `db.get_dashboard_stats()`
6. Add consistent error response format: `{success: false, error: "message"}`

**Relevant Context**
- All routes return `application/json`.
- Frontend will call these endpoints directly via `fetch()`.

**Status:** [x] done

---

### Sub-Task 7 — Frontend Dashboard (index.html)

**Intent**
Single-file interactive dashboard. Judges see the full system in one browser tab.

**Expected Outcomes**
- `index.html` with embedded CSS and JS loads in browser
- Dashboard panels: Totals, Facility Table, Allocation History
- Waste Request Form (structured fields + natural language textarea)
- Decision Trace display panel
- Comparison Table (first-compatible vs capacity-aware)
- Facility Closure simulation button per facility row
- Re-planning result panel (Before → Closed → Re-planned → New Allocation)
- Excess-demand scenario is naturally demonstrated when quantity > total available capacity

**Todo List**
1. Create `index.html` with 3-column layout (CSS Grid):
   - Left: Stats cards (Total Waste, Allocated, Unallocated, Facilities)
   - Center: Waste Request Form + Decision Trace
   - Right: Facility Table
2. Add Waste Request Form:
   - Dropdown: Waste Type
   - Number input: Quantity (tons)
   - Text: Origin
   - Textarea: Natural Language Request (optional)
   - Submit button → POST `/api/allocate`
3. Display Decision Trace after submission:
   - Each step as a checklist row: ✓ / ✗ icon + step name + detail
   - Final allocation decision highlighted
4. Add Facility Table:
   - Columns: Name, Zone, Accepts, Total Cap, Used, Remaining, Status, Actions
   - "Close Facility" button per row → POST `/api/close-facility` → show re-planning result modal
5. Add Comparison Panel:
   - Triggered after each allocation
   - Side-by-side: First-Compatible vs Capacity-Aware
6. Add Re-planning Result Panel:
   - Shows: Facility Closed → Affected Allocations → New Allocations → Unallocated
7. Auto-refresh stats cards after each action via GET `/api/stats`
8. Add a clearly visible banner: "⚠ All facility data is SIMULATED — not verified BBMP operational data"

**Relevant Context**
- No JS framework — plain fetch + DOM manipulation.
- CSS: clean, readable, Bengaluru green/white color scheme to fit the domain.
- Must work offline from filesystem if Flask is running locally.

**Status:** [x] done

---

### Sub-Task 8 — Integration Test & Demo Script

**Intent**
Verify the full end-to-end flow works and prepare a repeatable demo sequence for judges.

**Expected Outcomes**
- All 6 API endpoints return correct data
- Three demo scenarios work without errors:
  1. Normal allocation (NL input)
  2. Excess-demand (request more than available capacity)
  3. Facility closure + re-planning
- `demo_script.md` documents exact steps and expected outputs for the demo

**Todo List**
1. Run `python app.py` and confirm Flask starts
2. Test POST `/api/allocate` with NL input: `"Allocate 8 tons of organic waste from Yelahanka"`
3. Test excess demand: request 500 tons of organic waste
4. Test POST `/api/close-facility` on the facility used in step 2 → verify re-planning fires
5. Test GET `/api/stats` reflects correct totals after steps 2–4
6. Open `index.html` in browser, run all three scenarios through the UI
7. Write `demo_script.md` with step-by-step judge demo walkthrough
8. Fix any integration bugs found

**Relevant Context**
- Granite API key must be in `.env` before testing NL input.
- If Granite is unavailable, regex fallback should handle standard inputs.

**Status:** [x] done

---

## File Map

```
hackathon live/
├── app.py                    Flask app + all routes
├── db.py                     MySQL helpers
├── requirements.txt
├── .env.example
├── agents/
│   ├── __init__.py
│   ├── load_intake.py        Load Intake Agent
│   ├── capacity_allocator.py Capacity Allocation Agent
│   └── scenario_analyst.py  Scenario Analysis Agent
├── data/
│   ├── schema.sql
│   └── seed.sql
├── index.html                Frontend dashboard
└── demo_script.md            Judge demo walkthrough
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM usage | Granite for NL parse + explanations only | Keeps numbers deterministic |
| DB writes | Only after successful allocation | Prevents partial state |
| Capacity update | Stored column, updated on allocation | Simple, no computed columns |
| Partial allocation | Allowed — allocate what fits, return remainder | Realistic waste management |
| Multi-facility split | Out of scope for MVP | Keeps allocation logic simple |
| Frontend framework | None (vanilla JS) | Zero build step, demo-safe |
| Facility data | Simulated, clearly labelled | Honest, judge-safe |
