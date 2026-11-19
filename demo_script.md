# Waste Wise Bengaluru — Demo Script

> **Audience:** Hackathon judges  
> **Duration:** ~8 minutes  
> **Prerequisite:** Flask is running (`python app.py`) and the browser is open at **http://localhost:5000**

---

## Project File Structure

```
hackathon live/
├── app.py
├── db.py
├── requirements.txt
├── .env.example
├── agents/
│   ├── __init__.py
│   ├── load_intake.py
│   ├── capacity_allocator.py
│   └── scenario_analyst.py
├── data/
│   ├── schema.sql
│   └── seed.sql
├── index.html
├── setup.md
├── demo_script.md
└── waste-wise-plan.md
```

---

## Scenario 1 — Normal Allocation (Natural Language Input)

### Steps

1. **Open** http://localhost:5000 in the browser.

2. **Point out the SIMULATED DATA banner** at the top of the page:
   > _"All facility data is SIMULATED — not verified BBMP operational data."_  
   This is an important transparency signal — the system is honest about its data.

3. **Point out the Stats Cards** (pre-seeded history already visible):
   - Total Requests: **3**
   - Total Allocated (tons): reflects the 3 seeded allocations
   - Open / Closed Facilities: **6 / 0**

4. **Leave the structured form fields as-is.** In the **Natural Language Request** textarea, type:
   ```
   Allocate 8 tons of organic waste from Yelahanka
   ```

5. Click **🚀 Allocate Waste**.

6. **Point out the Decision Trace panel** that appears below the form:
   - ✅ Waste Type Identification — `Identified waste type: organic`
   - ✅ Quantity Validation — `Quantity: 8.0 tons`
   - ✅ Origin Recorded — `Origin: Yelahanka`
   - ✅ Compatible Facilities Search — `Found N compatible open facilities`
   - ✅ Facility Selection — `Selected: Yelahanka Organic Processing Centre (240.0t remaining)`
   - ✅ Capacity Check — `Requested 8.0t ≤ 240.0t available`
   - ✅ Allocation — `Allocated 8.0t to Yelahanka Organic Processing Centre`

7. **Point out the Explanation text** (Granite-generated or template fallback):
   > _"8.0 tons of organic waste from Yelahanka has been successfully allocated to Yelahanka Organic Processing Centre…"_

8. **Point out the Approach Comparison panel** (⚖):
   - **First Compatible** — first facility in the list with any space
   - **Capacity Aware** — highest remaining capacity, lowest utilisation pressure
   - If both selected the same facility: _"✓ Both approaches selected the same facility"_

9. **Stats cards update** — Total Requests and Total Allocated tons increment.

**Expected result:** Full allocation, 0 tons unallocated, Decision Trace shows all ✅.

---

## Scenario 2 — Excess Demand

### Steps

1. **Clear the Natural Language textarea** (leave it empty so the structured form is used).

2. Set the form fields:
   - Waste Type: **organic**
   - Quantity (tons): **500**
   - Origin: **Jayanagar**

3. Click **🚀 Allocate Waste**.

4. **Point out the amber Excess Demand warning** that appears in the Decision Trace panel:
   > _"⚠ Excess Demand: X.XX tons could not be allocated — insufficient compatible capacity."_

5. **Show the result summary box**:
   - Allocated: the total remaining organic capacity across all compatible facilities
   - Unallocated: `500 - <allocated>` tons
   - Facility: the facility that absorbed the partial allocation

6. **Show the Decision Trace**:
   - ✅ Waste Type Identification
   - ✅ Quantity Validation
   - ✅ Compatible Facilities Search
   - ✅ Facility Selection
   - ❌ Capacity Check — `Only X.XXt available — partial allocation (…t allocated, …t unallocated)`
   - ✅ Allocation — partial amount recorded

**Expected result:** Partial allocation, unallocated remainder shown, amber warning visible.

---

## Scenario 3 — Facility Closure + Re-planning

### Steps

1. **In the Facility Table** (center column), locate **Yelahanka Organic Processing Centre** —
   the facility used in Scenario 1 (or any OPEN facility with existing allocations).

2. Click the **🚫 Close** button in that facility's row.

3. A browser confirmation dialog appears:
   > _"Close 'Yelahanka Organic Processing Centre'? This will trigger re-planning for all its allocations."_  
   Click **OK**.

4. **Point out the 4-stage Re-planning Panel** that slides into view on the right:
   - **Stage 1: Facility Closed** — `Facility 'Yelahanka Organic Processing Centre' has been marked CLOSED`
   - **Stage 2: Affected Allocations Identified** — `N allocation(s) (X.XX tons) affected`
   - **Stage 3: Re-planning** — `Attempting reallocation to compatible open facilities`
   - **Stage 4: New Allocations** — `X.XX tons reallocated, Y.YY tons unallocated`

5. **Show the Affected Allocations table** — lists every ALLOCATED record that was on the closed facility.

6. **Show the New Allocations table** — lists the re-allocation results for each affected batch.

7. **Show the Facility Table** — the closed facility now shows:  
   `CLOSED` badge (red), no Close button.

8. **Stats cards refresh** — Open facilities count decrements.

**Expected result:** Facility marked CLOSED, affected waste automatically re-planned to remaining open facilities (or shown as unallocated if no capacity exists elsewhere).

---

## Key Talking Points for Judges

| Point | Detail |
|---|---|
| **IBM Granite LLM** | Handles natural language understanding — parses `"Allocate 8 tons of organic waste from Yelahanka"` into `{waste_type, quantity_tons, origin}` |
| **Deterministic arithmetic** | All capacity checks and allocation decisions are pure Python — the LLM never touches numbers, eliminating hallucination risk |
| **Transparent decision trace** | Every allocation produces a step-by-step audit trail visible to the user |
| **Automatic re-planning** | Facility closure triggers immediate re-allocation of all affected waste — no manual intervention |
| **Partial allocation** | When demand exceeds capacity, the system allocates what it can and clearly reports the unallocated remainder |
| **Honest about data** | The SIMULATED DATA banner is prominently shown — judges see transparent, responsible AI design |
| **End-to-end agent pipeline** | Intake Agent → Capacity Allocation Agent → Scenario Analysis Agent → (Re-plan Agent) — each with a defined contract |
| **Regex fallback** | If Granite is unavailable during the demo, the regex parser handles standard inputs — zero single points of failure |
| **Single-file frontend** | No build step, no framework — `index.html` loads instantly from `http://localhost:5000` |

---

## Troubleshooting During Demo

| Symptom | Fix |
|---|---|
| "Could not load facilities — is Flask running?" | Run `python app.py` and reload the page |
| Allocation fails with DB error | Check `.env` credentials and confirm `mysql -u root -p wastewise` works |
| Granite API error (explanation missing) | Template fallback kicks in automatically — demo continues |
| "No open facilities accept '…' waste" | Seed data may be exhausted; re-run `mysql -u root -p wastewise < data/seed.sql` |
