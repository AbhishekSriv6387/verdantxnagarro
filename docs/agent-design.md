# Verdant — Agent Design Document

## 1. Goal

Verdant is a carbon-aware batch-job scheduling agent that reduces the operational carbon footprint of enterprise compute workloads by intelligently shifting flexible jobs from fixed daytime schedules to lower-carbon-intensity execution windows — without ever missing a deadline.

**Challenge statement:** We help data-platform and ML-operations teams move flexible batch workloads from fixed daytime schedules to lower-carbon windows, measured by modeled grams CO₂e per run (SCI) and deadline compliance.

**Theme:** Forecasting, Scheduling & Dispatch — "Schedule flexible work against grid carbon intensity, shift loads to cleaner hours."

---

## 2. Users & Personas

| Persona | Pain Point | How Verdant Helps |
|---|---|---|
| **Data Platform Engineer** | Manages 100+ nightly ETL/ML jobs with fixed "safe" start times; no visibility into carbon impact | Automatically identifies and moves flexible jobs to cleaner windows; shows per-job SCI and aggregate savings |
| **ML Operations Lead** | Long-running training jobs block capacity at peak carbon times; manually rescheduling is error-prone | Exhaustive candidate search respects SLA, dependencies and safety buffers; zero manual slot calculation |
| **Business Insights Manager** | Critical revenue reports cannot be moved, but team lacks evidence that the current schedule is optimal | Protected jobs get proposals with transparent evidence; human approval required before any change |
| **Sustainability Officer** | Corporate ESG commitments require measurable operational carbon data | Exportable SCI reports with per-job provenance, frozen evidence and append-only audit trail |

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                   Browser (Dashboard)                    │
│   Static HTML + CSS + Vanilla JS + SVG                   │
│   Sign-in │ Workspace Selector │ Approvals │ Charts      │
└──────────────────┬───────────────────────────────────────┘
                   │ HTTPS / REST
                   ▼
┌──────────────────────────────────────────────────────────┐
│              FastAPI Application Layer                    │
│  Authentication │ Authorization │ Session Management      │
│  Role-based Access: platform_admin, client_admin,         │
│  project_operator, approver, viewer                      │
├──────────────────┬───────────────────────────────────────┤
│                  │                                        │
│    ┌─────────────▼─────────────┐                         │
│    │    SchedulerService       │  Transaction Coordinator │
│    │  (the agentic core)       │                         │
│    └──┬──────────┬──────────┬──┘                         │
│       │          │          │                             │
│       ▼          ▼          ▼                             │
│  ┌─────────┐ ┌─────────┐ ┌─────────────┐                │
│  │Providers│ │ Engine  │ │   Store     │                │
│  │(carbon) │ │(rules)  │ │ (SQLite)    │                │
│  └────┬────┘ └────┬────┘ └──────┬──────┘                │
│       │          │              │                        │
│       ▼          ▼              ▼                        │
│  Electricity  scheduler.py   Append-only                │
│  Maps / UK /  Pure SCI math  audit log                  │
│  Recorded /   Candidate      Content-addressed          │
│  Synthetic    search         frozen curves              │
│  Fallback     Guardrails     Triggers block             │
│               Tie-breaking   UPDATE/DELETE               │
│                    │                                     │
│                    ▼                                     │
│         ┌──────────────────┐                             │
│         │  explanations.py │  Optional LLM prose         │
│         │  (after commit)  │  No scheduling authority    │
│         └──────────────────┘                             │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Data Sources

### 4.1 Carbon Intensity Data

| Provider | Zone | Coverage | Authentication | Label |
|---|---|---|---|---|
| **Electricity Maps V4** | DE, US-CAL-CISO, IN-WE, GB | 48h forecast + history + latest | `auth-token` header | LIVE |
| **UK Carbon Intensity API** | GB only | 48h half-hour forecast | No key required | LIVE |
| **Recorded historical** | GB | Bundled 15-16 Jan 2025 actuals | None (local file) | REAL (RECORDED) |
| **Synthetic (default)** | All zones | Unlimited | None | SIMULATED |

**Provenance rules:**
- Each data interval retains its source (`LIVE`, `SIMULATED`, `REAL (RECORDED)`) and kind (`forecast`, `history`, `latest`, `synthetic`, `recorded_actual`).
- Complete, non-overlapping window coverage is mandatory. Incomplete live data causes whole-curve synthetic fallback.
- No interpolation between live and synthetic data within a single decision.

### 4.2 Workload Data

- **25-job default seed:** ETL pipelines, ML training jobs, and business reports across DE, US-CAL-CISO, IN-WE, and GB zones.
- **Scalable generator:** 1–500 seeded jobs with configurable complexity (dependency chains, criticality distributions, infeasible edge cases).
- All generated data is explicitly labeled **SIMULATED WORKLOAD**.

---

## 5. Tools & Components

### 5.1 Module Inventory

| Module | Responsibility | Agentic Role |
|---|---|---|
| `app/models.py` | Pydantic job schemas, baseline calculation, input validation | **Perception** — validates and normalizes input |
| `app/config.py` | Environment configuration with safety bounds | **Configuration** — defines operating constraints |
| `app/providers/carbon.py` | Carbon intensity curves with time-weighted integration | **Sensing** — observes the environment (grid state) |
| `app/providers/additional.py` | UK API and recorded-data adapters | **Sensing** — alternative data sources |
| `app/engine/scheduler.py` | Pure deterministic decision engine: SCI math, candidate search, guardrails | **Reasoning** — the decision core |
| `app/engine/sensitivity.py` | Read-only flexibility analysis across multiple time windows | **Analysis** — hypothetical scenario exploration |
| `app/engine/explanations.py` | Optional LLM-powered prose narration (text only, no authority) | **Communication** — optional human-readable summaries |
| `app/service.py` | Transaction coordinator: cycles, approvals, replay, clock | **Orchestration** — the single point of state change |
| `app/store/sqlite.py` | Persistence: jobs, state, append-only audit, frozen evidence | **Memory** — durable, tamper-resistant state |
| `app/access.py` | Identity directory, sessions, RBAC, tenant isolation | **Access control** — authentication and authorization |
| `app/api/main.py` | REST endpoints, structured logging, static delivery | **Interface** — exposes capabilities to humans/systems |
| `app/ui/` | Dashboard, admin, login (static HTML/CSS/JS/SVG) | **Presentation** — visual interface for oversight |

### 5.2 External Dependencies

| Tool | Purpose | Risk Mitigation |
|---|---|---|
| FastAPI + Uvicorn | HTTP framework and ASGI server | Standard, well-tested Python ecosystem |
| SQLite (WAL mode) | Persistence with transactional guarantees | Embedded, zero-config, single-process deployment |
| httpx | Provider HTTP client | Bounded timeouts, configurable retries, TTL cache |
| Pydantic | Input/output validation | Type safety at API boundaries |
| OpenAI API (optional) | Decision narration only | Disabled by default; `store=false`; failure falls back gracefully |

---

## 6. Orchestration & Decision Flow

### 6.1 Agent Cycle — Step by Step

```
                    ┌──────────────────┐
                    │  Trigger cycle   │
                    │  (human click or │
                    │  30s watcher)    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Acquire store   │
                    │  transaction     │
                    │  lock            │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Build JobGraph  │
                    │  index           │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  For each PENDING job:       │
              │  1. Check fingerprint        │
              │     (skip if unchanged)      │
              │  2. Fetch/reuse carbon curve │
              │  3. Compute baseline SCI     │
              │  4. Enumerate 30-min         │
              │     candidate slots          │
              │  5. Compute SCI for each     │
              │  6. Select lowest-carbon     │
              │     slot (earliest tiebreak) │
              │  7. Check dual thresholds    │
              │  8. Apply guardrails         │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Outcome routing:            │
              │                              │
              │  Flexible + independent      │
              │  + both thresholds pass?     │
              │  ──► AUTO_RESCHEDULED        │
              │                              │
              │  Protected / critical /      │
              │  has dependencies?           │
              │  ──► NEEDS_APPROVAL          │
              │                              │
              │  No worthwhile improvement   │
              │  + baseline feasible?        │
              │  ──► KEEP_NOW                │
              │                              │
              │  No feasible slot exists?    │
              │  ──► NO_FEASIBLE_WINDOW      │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  Commit: update job status,  │
              │  save decision + frozen      │
              │  evidence atomically         │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │  AFTER COMMIT (optional):    │
              │  Request LLM prose narration │
              │  outside store lock; append  │
              │  if successful               │
              └─────────────────────────────┘
```

### 6.2 Approval Flow

```
  Proposal created (NEEDS_APPROVAL)
         │
         ▼
  Human reviews in dashboard
  (reviewer identity from session)
         │
    ┌────┴────┐
    ▼         ▼
  APPROVE   REJECT
    │         │
    ▼         ▼
  Revalidate  Mark rejected;
  temporal &  no dispatch;
  dependency  no savings
  feasibility credit
    │
    ├─ PASS ──► Apply schedule; credit savings; log approval
    │
    └─ FAIL ──► Reject with "proposal expired" message
```

### 6.3 Idempotency

- Fingerprint = SHA-256 of `[clock, related-job-states]`.
- Same fingerprint → skip (no duplicate decisions).
- Applied/approved jobs are never re-evaluated.
- Concurrent cycles serialize through the store write lock.

---

## 7. Decision Points & Guardrails

### 7.1 Non-Negotiable Safety Rules

| # | Rule | Enforcement |
|---|---|---|
| 1 | **No auto-move of protected jobs** | `criticality != "flexible"` or has dependencies/dependents → `NEEDS_APPROVAL` |
| 2 | **SLA + buffer always respected** | `start + duration + safety_buffer ≤ deadline` checked for every candidate |
| 3 | **No starts before current time** | `start ≥ max(now, earliest_start, dependency_floor)` |
| 4 | **Dual savings threshold** | Both `≥ 5% AND ≥ 5g` required (configurable upward by project policy) |
| 5 | **Stale approval rejection** | Temporal and dependency feasibility re-checked at approval time |
| 6 | **Append-only audit** | SQLite triggers block UPDATE/DELETE on decision rows |
| 7 | **LLM cannot change decisions** | Prose narration runs after commit, on a detached copy, with no scheduling tool |
| 8 | **Infeasible baseline → review** | Even flexible jobs require human review when the 14:00 baseline is infeasible |

### 7.2 Decision Rules Summary

| Condition | Outcome | Savings Credited? |
|---|---|---|
| Flexible, independent, dual thresholds pass | `AUTO_RESCHEDULED` | ✅ Yes |
| No worthwhile move, baseline feasible | `KEEP_NOW` | ✅ Yes (zero delta) |
| Protected or baseline infeasible | `NEEDS_APPROVAL` | ❌ Until approved |
| Human approves after revalidation | `APPROVED` | ✅ Yes |
| Human rejects | `REJECTED` | ❌ Never |
| No feasible slot or dependencies unresolved | `NO_FEASIBLE_WINDOW` | ❌ Never |
| Clock passes scheduled finish | `COMPLETED` | ✅ Yes (simulated) |

---

## 8. Human Oversight Design

### 8.1 When Humans Are Required

1. **Business-critical jobs** — Any job with `criticality: "business_critical"` always requires explicit human approval, regardless of savings magnitude.
2. **Hard-deadline jobs** — Jobs with `criticality: "hard_deadline"` require human review before rescheduling.
3. **Dependency-linked jobs** — Jobs with upstream prerequisites or downstream dependents cannot be auto-moved. Approving a parent unlocks its child in the next cycle.
4. **Infeasible baseline** — When the standard 14:00 baseline is itself infeasible (e.g., past the deadline), any proposed replacement requires human judgment.

### 8.2 What the Reviewer Sees

- **Frozen decision evidence:** The exact carbon curve snapshot, intensity intervals, candidate start times, rule IDs, thresholds, baseline and chosen SCI values.
- **Provenance labels:** Whether data is LIVE, SIMULATED, or REAL (RECORDED).
- **SLA margin:** Remaining buffer between the proposed run's end and the deadline.
- **Dependency state:** Current status of upstream and downstream jobs.

### 8.3 What the Reviewer Cannot Do

- **Bypass temporal feasibility.** Even with approval, a proposal past its deadline is automatically rejected.
- **Bypass dependency order.** A child cannot be approved before its parent has an applied schedule.
- **Submit without a comment.** Every review action requires a mandatory text comment.
- **Impersonate another reviewer.** Identity comes from the authenticated session, not a user-submitted field.

---

## 9. Failure Handling & Resilience

| Failure Mode | Detection | Recovery | Data Impact |
|---|---|---|---|
| **Carbon API timeout/error** | httpx timeout + retry | Whole-curve synthetic fallback; labeled SIMULATED | No incorrect LIVE labels |
| **Incomplete API coverage** | Integration validates full-window coverage | Same synthetic fallback | Decision provenance is honest |
| **LLM narration failure** | Try/except after commit | Deterministic evidence preserved; prose simply absent | No scheduling state impact |
| **Concurrent agent cycles** | SQLite write lock + transactions | Serialized execution; idempotent fingerprinting | No duplicate or conflicting decisions |
| **Stale approval attempt** | Re-check `is_feasible()` at approval time | 409 Conflict; reviewer must reject and resubmit | No infeasible schedule applied |
| **Invalid job input** | Pydantic validation | 422 with field-level error messages | No partial state written |
| **Database corruption** | SQLite WAL + journaling | Standard SQLite recovery; append-only triggers protect history | Audit trail intact |
| **Missing dependencies** | `dependency_floor()` returns None | `NO_FEASIBLE_WINDOW` with explanation | Job waits; no incorrect scheduling |
| **Impossible deadline** | Candidate search finds no slots | `NO_FEASIBLE_WINDOW` logged with full evidence | Zero savings credited |

---

## 10. Carbon Math Reference

```
E (kWh) = IT_power (kW) × duration (min) / 60 × PUE
I (g CO₂e/kWh) = Σ(overlap_seconds × interval_intensity) / total_seconds
SCI (g CO₂e/run) = (E × I + M) / R     where R = 1 job run

avoided_g = baseline_SCI − chosen_SCI
reduction_pct = Σ(avoided_g) / Σ(baseline_SCI) × 100
```

**Boundary:** Job IT electricity + PUE overhead + configured embodied allocation. Network, storage, idle fleet, retries, and resource contention are excluded. Runtime and power are identical before and after; only the timing changes.

---

## 11. Security & Privacy Architecture

| Layer | Measure |
|---|---|
| **Authentication** | Salted PBKDF2-HMAC-SHA256 (600K iterations); opaque hashed sessions; HttpOnly + SameSite=Strict cookies |
| **Authorization** | Five-role RBAC: platform_admin → client_admin → project_operator → approver → viewer |
| **Tenant isolation** | Separate SQLite databases per environment; cross-environment dependencies rejected |
| **Login protection** | Per-username and per-address attempt throttling (20/15min) |
| **Input sanitization** | Pydantic validation; parameterized SQL; HTML/CSV escaping; CSP headers |
| **Audit integrity** | SQLite triggers block UPDATE/DELETE on decision/admin-event rows |
| **LLM data discipline** | Detached summary only; `store=false`; no names, owners, or credentials sent |
| **Credential isolation** | Per-environment token variables; no implicit inheritance across workspaces |

---

## 12. Sustainability of the Agent Itself

| Dimension | Implementation |
|---|---|
| **Token efficiency** | LLM is optional prose-only; zero tokens for core scheduling decisions |
| **Compute efficiency** | 500-job cycle completes in ~2.2 seconds offline; per-cycle curve reuse and indexed graph lookups |
| **Tool-call discipline** | Deterministic exhaustive search; no iterative LLM "tool use" loops |
| **Carbon awareness** | The agent schedules its own demo workloads against the same carbon data it evaluates |
| **Minimal dependencies** | Python standard library + 4 packages; no CDN, framework build, or remote fonts |
| **Offline-first** | Fully functional without internet; synthetic data labeled honestly |

---

## 13. Technology Stack Summary

| Layer | Technology | Rationale |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn | Typed, async-capable, OpenAPI auto-generation |
| Database | SQLite (WAL mode) | Zero-config, embedded, transactional |
| Frontend | Static HTML, CSS, Vanilla JS, SVG | No build step, no CDN, offline-capable |
| Carbon data | Electricity Maps V4, UK Carbon Intensity, recorded files, synthetic | Multi-provider with honest fallback |
| Optional AI | OpenAI Responses API | Prose narration only; never decisions |
| Containerization | Dockerfile (non-root) | Reproducible deployment |
| Testing | pytest (95 tests) | Unit, integration, guardrail, concurrency |
| Verification | `scripts/smoke.py` | End-to-end HTTP validation |
