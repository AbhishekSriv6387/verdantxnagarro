# Verdant — Pitch Deck

> **Prompt, Plan, Preserve: Hacking Sustainability with Agentic AI**
> Track: Forecasting, Scheduling & Dispatch

---

## Slide 1: The Problem

### Batch Jobs Run on Autopilot — at Carbon's Expense

Organizations run thousands of batch jobs daily: ETL pipelines, ML training, business reports, data compaction.
These jobs overwhelmingly start at **fixed, convenient times** — typically early morning or business-hours slots inherited from legacy schedules.

**The disconnect:**
- Grid carbon intensity varies **2–5× within a single day** depending on renewable generation, demand, and fuel mix.
- Most batch jobs have scheduling flexibility (hours of slack before their deadline) but **zero carbon visibility**.
- Platform teams lack tools to quantify the carbon cost of "run it at 2 PM because that's when it always runs."

**The human cost:**
- Manual rescheduling across 100+ jobs is error-prone and unsustainable.
- Critical jobs and dependency chains make blanket "shift to night" rules dangerous.
- Without measurable evidence, sustainability commitments remain aspirational.

**Impact:** The decisions that commit carbon emissions happen daily in scheduling tools. Delaying them until quarterly ESG reporting makes the analysis too late to act on.

---

## Slide 2: Our Solution — Verdant

### A Carbon-Aware Batch Scheduling Agent

Verdant is an **agentic AI system** that finds lower-carbon execution windows for enterprise batch jobs:
- **Automatically moves** safe, flexible, independent jobs to cleaner slots.
- **Proposes changes** for critical or dependency-linked jobs and waits for human approval.
- **Measures everything** using the Green Software Foundation's SCI specification.
- **Never misses a deadline** — every candidate respects the SLA, safety buffer, and dependency order.

**One-liner:** *A greener window. The same deadline.*

**Key differentiators:**
- 🔒 **Non-negotiable guardrails** — critical jobs, SLA deadlines, and dependency chains are protected by code, not policy documents.
- 📊 **Transparent evidence** — every decision comes with frozen intensity data, candidate comparisons, rule IDs, and provenance labels.
- 🔌 **Works offline** — fully functional with synthetic data; honestly labeled. No internet required for the core scheduling engine.
- 🤖 **LLM-optional** — the agent's decisions are deterministic; AI narration is optional prose that runs after commit and has no scheduling authority.

---

## Slide 3: How the Agent Works

### Observe → Decide → Act → Escalate

```
  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
  │  OBSERVE    │    │   DECIDE     │    │    ACT       │    │  ESCALATE    │
  │             │    │              │    │              │    │              │
  │ • Read job  │───►│ • Enumerate  │───►│ • Apply      │───►│ • Proposal   │
  │   queue     │    │   all 30-min │    │   schedule   │    │   to human   │
  │ • Fetch     │    │   candidate  │    │   change     │    │   reviewer   │
  │   carbon    │    │   slots      │    │ • Commit     │    │ • Mandatory  │
  │   intensity │    │ • Compute    │    │   frozen     │    │   comment    │
  │ • Check     │    │   SCI for    │    │   evidence   │    │ • Revalidate │
  │   clock &   │    │   each       │    │ • Credit     │    │   at approval│
  │   deps      │    │ • Check dual │    │   savings    │    │   time       │
  │             │    │   thresholds │    │              │    │              │
  └─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

**The agentic loop:**
1. **Observe** the queue, simulated clock, dependency state, and carbon intensity data.
2. **Decide** using deterministic exhaustive search — every feasible 30-minute start slot is evaluated.
3. **Act** within explicit authority — move flexible, independent jobs that pass both savings thresholds.
4. **Escalate** when authority is insufficient — critical, linked, or baseline-infeasible jobs require human review.

The browser watcher can repeat this cycle every 30 seconds. Decisions are idempotent — running it again produces zero duplicates.

---

## Slide 4: Methodology — The Carbon Math

### SCI: Software Carbon Intensity

Following the **Green Software Foundation SCI Specification (ISO/IEC 21031:2024)**:

```
SCI = (E × I + M) / R

Where:
  E = Energy (kWh) = Power (kW) × Duration (h) × PUE
  I = Carbon Intensity (g CO₂e/kWh) — time-weighted over the run
  M = Embodied emissions per run (configurable; default 0)
  R = 1 job run (functional unit)
```

**What makes it rigorous:**
- **Time-weighted integration:** A 90-minute job straddling two half-hour intervals gets proportional intensity from each.
- **Fixed counterfactual baseline:** Always 14:00 local time on the job's earliest-start date. Never moved to improve results.
- **Dual threshold:** Both ≥5% AND ≥5g absolute savings required. Either alone is insufficient.
- **Honest exclusions:** Pending, rejected, blocked, and infeasible jobs are never counted in savings totals.

**Boundary:** Job IT electricity + PUE overhead. Network, storage, idle fleet, and retries are outside scope. Runtime and power are identical before and after — only timing changes.

---

## Slide 5: Results — Measurable Impact

### Default Demo Scenario (25 Jobs)

| Metric | Value |
|---|---|
| **Jobs auto-scheduled** | 15 of 25 |
| **Proposals for human review** | 7 |
| **Blocked/infeasible** | 3 |
| **Modeled daily savings** | 21,014 g CO₂e (~21 kg) |
| **Reduction percentage** | 39.8% |
| **Projected weekly (×7)** | 147,095 g CO₂e (~147 kg) |

### 7-Day Replay (175 Seeded Jobs)

| Metric | Value |
|---|---|
| **Total jobs evaluated** | 175 |
| **Applied schedules** | 105 |
| **Total modeled savings** | 167,144 g CO₂e (~167 kg) |
| **Average reduction** | 40.7% |
| **Source** | SIMULATED (reproducible seed 42) |

### Scale Performance

| Metric | Value |
|---|---|
| **500-job cycle** | 2.215 seconds (offline) |
| **Regression limit** | < 5 seconds |
| **Duplicate cycle** | Zero new decisions (idempotent) |

> ⚠️ **Honest framing:** These are modeled SCI estimates using synthetic carbon data. They are not measured real-world emissions reductions. Production validation requires metered workload telemetry and post-execution intensity reconciliation.

---

## Slide 6: Impact & Value Proposition

### Why This Matters

**For enterprises:**
- Turn scheduling flexibility into measurable carbon savings without operational risk.
- Meet ESG reporting requirements with auditable, per-job SCI evidence.
- Protect critical operations with non-bypassable guardrails.

**For the planet:**
- Grid intensity varies significantly by hour and region. Shifting compute to cleaner windows reduces attributional emissions without reducing compute.
- The opportunity scales with fleet size: a 1,000-job enterprise running 40% flexible workloads could see significant weekly carbon reductions.

**For the hackathon evaluation:**

| Judging Criterion | Evidence in Verdant |
|---|---|
| **Sustainability Impact & Measurability** | Per-run SCI, aggregate savings, frozen evidence, exportable reports, reproducible replay |
| **Agentic Depth & Technical Implementation** | Observe-decide-act-escalate loop, deterministic rules, transactional state, 95 automated tests |
| **Sustainability of the Agent Itself** | Zero LLM tokens for decisions, 2.2s/500-job cycle, offline-first, minimal dependencies |
| **Demo & Communication** | Working dashboard, transparent evidence, honest provenance labels |
| **Innovation & Creativity** | Multi-provider carbon data with honest fallback, append-only audit, frozen evidence by content hash |

---

## Slide 7: Efficiency & Responsible AI

### The Agent Earns Its Keep

**Model selection:**
- Core scheduling is **100% deterministic Python** — zero LLM tokens, zero API calls for decisions.
- Optional OpenAI narration uses `gpt-4.1-mini` with `store=false`, sending only a detached summary (no names, owners, credentials).

**Token efficiency:**
- Total LLM tokens for scheduling: **0** (always).
- Optional narration: ~180 output tokens per decision, only when explicitly enabled.
- Narration failure: graceful fallback to deterministic explanation text.

**Tool-call discipline:**
- No iterative LLM "plan → tool → observe → replan" loops.
- Exhaustive search evaluates all candidates in one pass.
- Curve reuse within a cycle eliminates redundant provider calls.

**Carbon-aware design:**
- Agent schedules against the same grid data it evaluates — it practices what it preaches.
- Synthetic fallback eliminates unnecessary API calls when coverage is incomplete.

**Guardrails:**
- LLM output cannot modify criticality, slots, emissions, approval state, or scheduling rules.
- A dedicated test sends malicious LLM output and confirms protected jobs remain unmoved.
- Deterministic evidence commits atomically with the schedule change; LLM prose appends separately after.

**Privacy:**
- Job names/owners are never sent to the LLM.
- `store=false` prevents external retention.
- Platform disables LLM narration for all authenticated workspaces until scoped consent is implemented.

---

## Slide 8: Demo Walkthrough

### What You'll See in the Live Demo (3–5 minutes)

**0:00–0:30 — The Pain**
- Open the dashboard showing 25 batch jobs with fixed 14:00 baseline schedules.
- Point out the SIMULATED badge and explain the demo boundary.

**0:30–1:00 — Autonomous Action**
- Click **Run agent cycle**. 15 jobs automatically move to cleaner windows.
- Click again: zero duplicate decisions (idempotent).
- Show the ~21 kg daily savings on the carbon cards.

**1:00–1:30 — Transparent Evidence**
- Select **Warehouse refresh**. Show the SVG chart with baseline vs. chosen intensity curves.
- Expand the decision log: rule IDs, candidate starts, intensity intervals, SLA margin.

**1:30–2:00 — Human Control**
- Open the **Approval inbox**. Approve "Daily revenue report" with a comment.
- Show that only authenticated reviewers can approve, and approval rechecks feasibility.
- Reject another proposal to show zero savings credit.

**2:00–2:30 — Scale & Replay**
- Click **Replay 7 days**: 175 jobs, ~167 kg CO₂e modeled savings.
- Show the replay chart with per-day breakdown.

**2:30–3:00 — Governance & Export**
- Show the admin panel: client/project/environment isolation, role-based access.
- Export a CSV or JSON report with per-job SCI, provenance, and inclusion flags.

**3:00–3:30 — Honest Pilot Ask**
- "These are modeled results. We need one platform team and one real queue for a 90-day pilot."

---

## Slide 9: Roadmap — 90-Day Production Pilot

| Phase | Period | Deliverable |
|---|---|---|
| **1. Discovery** | Days 1–15 | Interview workload owners; inventory one queue's dependencies, calendars, and data-freshness constraints |
| **2. Shadow Mode** | Days 16–30 | Read-only Airflow/Kubernetes adapter; real carbon entitlement; shadow recommendations vs. actual runs |
| **3. Hardening** | Days 31–45 | Enterprise SSO/MFA integration; secrets management; retention policies; security review |
| **4. Constraints** | Days 46–60 | Capacity constraints; duration/forecast uncertainty margins; stress tests |
| **5. Controlled Launch** | Days 61–75 | Small allowlisted flexible queue with kill switch; daily measured outcomes |
| **6. Validation** | Days 76–90 | Expand if results justify; reconcile actual carbon; pilot decision memo |

**What's needed from a pilot partner:**
- One data platform team willing to share one queue's scheduling metadata.
- Runtime, power/energy, baseline start, and completion data for shadow comparison.
- A 15-minute weekly review of recommendations and outcomes.

**What we deliver:**
- Zero unauthorized critical-job movements.
- Zero scheduler-induced SLA misses.
- 100% source/evidence completeness.
- Measured net carbon delta after accounting for retries and displaced work.

---

## Slide 10: Team & Technology Summary

### What We Built

| Dimension | Detail |
|---|---|
| **Lines of Python** | ~1,200 (backend) |
| **Lines of JS/HTML/CSS** | ~1,600 (dashboard) |
| **Automated tests** | 95 (pytest) |
| **HTTP verification** | smoke.py against running server |
| **Carbon math** | SCI specification (ISO/IEC 21031:2024) |
| **Providers** | 4 (Electricity Maps, UK API, recorded, synthetic) |
| **Zones** | 4 (DE, US-CAL-CISO, IN-WE, GB) |
| **RBAC roles** | 5 (platform admin → viewer) |
| **External LLM tokens for scheduling** | 0 (always) |
| **Offline operation** | Fully functional |
| **Build tools required** | None (no npm, webpack, CDN) |
| **Standards referenced** | SCI (ISO/IEC 21031:2024), GHG Protocol |

### Key Technical Choices

- **Deterministic decisions** over LLM-generated plans — auditability, testability, zero token cost.
- **Exhaustive candidate search** over heuristic shortcuts — guaranteed optimal within the grid.
- **Append-only audit** over mutable logs — immutable evidence for ESG reporting.
- **Multi-provider with honest fallback** over "works only with paid API" — always functional, never dishonest.
- **Human-in-the-loop for critical jobs** over fully autonomous — responsible AI for high-stakes operations.

---

### Thank You

**Verdant** — A greener window. The same deadline.

*Repository: [See README for setup and run instructions]*
*Demo video: [Link to be added]*
