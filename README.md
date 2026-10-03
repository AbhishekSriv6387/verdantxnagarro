# Verdant — Carbon-Aware Batch Job Scheduler Agent

**A greener window. The same deadline.**

Verdant finds lower-carbon execution windows for enterprise batch jobs, automatically moves independent flexible jobs, and asks a human before changing critical or dependency-linked work. It is a complete local hackathon demo with FastAPI, SQLite, a vanilla-JavaScript dashboard, and no frontend build or CDN requirements.

**All displayed savings are modeled SCI estimates.** The default dataset is prominently labeled **SIMULATED**. The app dispatches no real workloads and makes no claim of measured emissions reductions or completed customer validation.

## Run it

Python 3.11+ is required. Python 3.12 was used for verification.

```powershell
# Windows, from the repository root (one-time setup)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock

# Start the app; run.py automatically uses the local virtual environment
python run.py
```

```bash
# macOS / Linux, one-time setup
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
python3 run.py
```

Open **http://127.0.0.1:8000**. No token, account, internet connection, Node.js, or build step is needed after Python dependencies are installed. `requirements.txt` declares supported ranges; `requirements.lock` records the exact verified dependency set. For an air-gapped environment, download these wheels on a connected machine first.

```bash
python run.py --test     # one-command tests, using .venv automatically
make run                # equivalent when Make is installed
make test
```

You can also activate the virtual environment and run `python -m pytest -q`. On Windows, Make is optional.

## Two-minute demo

1. Click **Reset demo** if needed. The clock starts at **9 October 2026, 00:00 UTC** and the queue contains 25 jobs across Germany, California, and Western India.
2. Click **Run agent cycle**. The default first pass applies 15 schedules, leaves 7 proposals for review, and flags 3 blocked/infeasible jobs. Click it again: zero duplicate decisions.
3. Select **Warehouse refresh**. Compare the fixed local 14:00 baseline with the cleaner chosen window. The chart is drawn from the decision's frozen intensity data.
4. Open **Approval inbox**, enter a comment, and approve **Daily revenue report**. Its schedule and accounting update only after approval. Reject another proposal to show that rejected changes receive no savings credit.
5. Expand **Decision log → Inspect complete decision evidence**. Show rule IDs, intensity intervals, candidate starts, margins, source, and actor.
6. Click **Replay 7 days**: 175 seeded jobs, about **167,144 g / 167.1 kg CO₂e** of modeled savings on 105 applied schedules, roughly **40.7%**. This is a separate experiment and leaves the active queue untouched.
7. Export a CSV or JSON report. Advance the demo clock to show simulated completion.

The complete presenter script, plain-English walkthrough, rubric mapping and 90-day pilot proposal are in [docs/UNDERSTAND_THIS.md](docs/UNDERSTAND_THIS.md). Reproducible HTTP verification results are in [docs/demo-evidence.json](docs/demo-evidence.json).

## What is implemented

- Typed job input with explicit timezone offsets, supported zones, bounded workload parameters, and server-controlled baseline/status.
- Exhaustive 30-minute candidate search using exact time-weighted carbon intensity over each run; deterministic earliest-start tie breaking.
- SLA deadline minus runtime minus safety buffer; no starts before the simulated clock or prerequisite completion.
- Dual savings threshold, default **5% AND 5 g**, with independent flexible jobs only eligible for automatic movement.
- Approval/rejection with required human comment; stale approvals are rejected and dependency feasibility is checked again when applying.
- Append-only SQLite audit records enforced with triggers; decisions, frozen curves, intensity samples, rules, thresholds, actor, simulated timestamp and wall-clock timestamp retained.
- Explicit LIVE/SIMULATED provenance. No averaging of live readings with synthetic filler inside a decision.
- Persistent simulated clock, isolated weekly replay, reset with audit-history retention, browser queue watcher, and SCI exports.
- Responsive dark dashboard, SVG charts, source badges, queue filters, approval inbox, log filters and add-job form.
- Optional text-only OpenAI explanations. Deterministic explanations always remain authoritative.

## Architecture

```text
Browser: static HTML + CSS + vanilla JS + SVG
                  |
                  v
          FastAPI /api/*                 /docs (offline reference)
                  |
                  v
       SchedulerService (transaction coordinator)
          |               |                    |
          v               v                    v
   providers/        engine/scheduler.py   store/sqlite.py
   Electricity Maps  pure rules + SCI      jobs + state + append-only logs
      | fallback     candidate search      SQLite WAL + write lock
   Synthetic         SLA + approval rules
                          |
                          v
                  optional explanations.py
                  text output only; no scheduling authority
```

| Location | Responsibility |
|---|---|
| `app/models.py` | Job schemas, validation, fixed local 14:00 baseline |
| `app/config.py` | Validated settings and IANA zone timezones |
| `app/providers/carbon.py` | Synthetic curves, Electricity Maps client, integration and fallback |
| `app/engine/scheduler.py` | Energy, SCI, exhaustive window search and immutable rule decisions |
| `app/engine/explanations.py` | Pluggable optional narration, never decisions |
| `app/service.py` | Transactions, idempotence, approvals, clock, accounting, replay |
| `app/store/sqlite.py` | Persistence and append-only history |
| `app/api/main.py` | REST routes, structured logs, error handling, static delivery and exports |
| `app/ui/` | Offline dashboard and API reference |
| `app/seed.py` | 25 varied jobs with a three-job chain and one impossible deadline |
| `tests/` | Unit, provider, guardrail, concurrency and API tests |

## Scheduling rules and state

For each pending job, enumerate starts from `ceil_30min(max(earliest_start, simulated_now, prerequisite_finish))` through `sla_deadline - runtime - safety_buffer`. Compare all candidates with the baseline at **14:00 local on the earliest-start date**. A run's intensity is the mean weighted by exact overlapping interval duration, including partial half-hours.

| Outcome | Meaning and applied state |
|---|---|
| `AUTO_RESCHEDULED` | Both thresholds pass; flexible with no prerequisites or dependents. Set `scheduled`. |
| `KEEP_NOW` | Retain an already-feasible baseline because the move is not worthwhile. Name means **keep baseline**, not execute immediately. Set `scheduled`. |
| `NEEDS_APPROVAL` | A move involves a criticality/dependency guardrail, or the baseline itself is infeasible. Set `needs_approval`; do not apply or credit savings. |
| `NO_FEASIBLE_WINDOW` | No safe candidate, or prerequisites have no applied schedule. Keep `pending`, with reason in its decision. |
| `APPROVED` / `REJECTED` | Human review. Approval applies the frozen proposal after revalidation. Rejection leaves no dispatched schedule. |
| `COMPLETED` | Advancing the simulated clock passed an applied job's finish time; no real compute was executed. |

All candidate runs meet the deadline **including the safety buffer**. Even human approval cannot bypass time/dependency validation. Protected jobs may retain their unchanged feasible baseline, but are never automatically moved.

Pending unresolved decisions are deduplicated using the simulated clock and dependency state. Applied schedules and proposals are not reevaluated by subsequent cycles. Approve a parent, then run another cycle to unlock its child. A newly added dependent never retroactively moves an already-applied parent. To replace an expired proposal, reject it and add a fresh job/window.

The browser's **Watch queue every 30s** runs the same idempotent cycle while the dashboard is open. It does not advance the clock. There is no separate background worker or real scheduler adapter.

## Carbon math and reporting boundary

```text
E (kWh) = IT power (kW) × duration (minutes) / 60 × PUE
I (g CO2e/kWh) = time-weighted grid intensity over the complete run
SCI (g CO2e/run) = (E × I + M) / R
R = 1 job run
M = embodied grams allocated to one run (default 0)
avoided_g = baseline_SCI - chosen_SCI
reduction_pct = sum(avoided_g) / sum(included_baseline_SCI) × 100
weekly_projection = current_applied_workload_avoided_g × 7
```

The modeled system boundary is job IT electricity plus PUE overhead and configured embodied allocation. Network transfer, storage outside job power, idle fleet capacity, retry energy and resource contention are outside this boundary. Runtime and power remain identical across schedules. `M` cancels in the absolute delta if unchanged but affects the percentage denominator.

Reports include only applied scheduled/approved/completed runs in totals. Unevaluated, awaiting-approval, rejected, and infeasible jobs are excluded, counted explicitly, and never credited. JSON/CSV rows preserve provenance and inclusion flags. Mixed data across jobs is displayed as `LIVE + SIMULATED`; per-job figures are individually labeled. Weekly projection is a simple repeated-workload assumption; replay separately evaluates seven varied seeded days. Neither is a measured real-world impact claim.

## Electricity Maps and fallback

Set `ELECTRICITY_MAPS_TOKEN` in `.env` to enable the optional provider. The adapter calls V4 `carbon-intensity/latest`, `history`, and `forecast` (48-hour horizon, hourly granularity), using the **`auth-token` header**, bounded request timeouts/retries, and a per-zone TTL cache. Some endpoints require paid entitlements and some zones lack coverage.

Only complete, non-overlapping coverage of the entire comparison window is accepted. Missing token, authorization failure, timeout, invalid response, stale readings or incomplete coverage cause the **entire decision curve** to use seeded synthetic data. Latest-only readings are never extrapolated into a forecast. Each data interval retains its kind (`latest`, `history`, `forecast`, `synthetic`) and source. `LIVE` means obtained from the live API, **including API forecasts/estimates**, not direct job emission measurements.

The demo clock is intentionally fixed to the hackathon date, so a real-time token on another date may still fall back. Use the add-job API with relevant timestamps and move the demo clock appropriately for provider experiments; default replay is always synthetic. Actual paid Electricity Maps access was not available for verification; HTTP response, retry, timeout, coverage and fallback behavior are tested with fixtures.

Synthetic curves have zone-specific base intensity, a midday solar dip, evening peak, mild overnight reduction and stable seed/time/zone-based noise. These are pedagogical scenarios, not historical reconstructions or regional forecasts.

## Environment variables

Copy `.env.example` to `.env` if overriding defaults. Never commit `.env`.

| Variable | Default | Purpose |
|---|---|---|
| `HOST`, `PORT` | `127.0.0.1`, `8000` | Bind address and port |
| `DATABASE_PATH` | `data/carbon.db` | SQLite database; directory created automatically |
| `PUE` | `1.4` | IT electricity overhead multiplier |
| `EMBODIED_G_PER_RUN` | `0` | Allocated embodied emissions per job run |
| `SAVINGS_THRESHOLD_PCT` | `5` | Minimum SCI reduction percentage |
| `SAVINGS_THRESHOLD_G` | `5` | Minimum absolute grams saved |
| `SAFETY_BUFFER_MIN` | `15` | Extra time required before SLA |
| `SYNTHETIC_SEED` | `42` | Reproducible synthetic curves |
| `ELECTRICITY_MAPS_TOKEN` | empty | Optional live API credentials |
| `PROVIDER_TIMEOUT_SECONDS` | `3` | Timeout per provider HTTP operation |
| `PROVIDER_RETRIES` | `1` | Additional retries per endpoint, maximum 3 |
| `PROVIDER_CACHE_SECONDS` | `300` | Zone data cache TTL |
| `ENABLE_LLM_EXPLANATIONS` | `false` | Explicitly opt in to external narration |
| `OPENAI_API_KEY` | empty | Optional OpenAI key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Configurable Responses-compatible text model |

Optional narration sends only a detached decision summary (numbers, rules, source and deterministic explanation) to OpenAI with `store=false`. Names, owners and credentials are not included. External service charges and that service's data policies apply when explicitly enabled. Model access is account-dependent; any request failure falls back to deterministic text. No LLM is used to infer or downgrade criticality; users supply it explicitly.

## API and verification

The entirely local API reference is at `/docs`; the machine-readable schema is `/openapi.json`.

```text
GET  /api/health, /api/state, /api/jobs, /api/approvals, /api/report
GET  /api/jobs/{id}/curve
GET  /api/logs?actor=human&outcome=APPROVED&all_runs=false
GET  /api/report/export?format=csv|json&scope=current|replay
POST /api/jobs                         JobInput JSON (see OpenAPI)
POST /api/agent/cycle                  {}
POST /api/approvals/{id}               {"action":"approve","comment":"Reviewed SLA"}
POST /api/clock/advance                {"minutes":60}
POST /api/demo/reset                  {}
POST /api/demo/replay                 {}
```

`422` is invalid input; `409` is a conflicting/expired action; `404` is an unknown job. Timestamps must include `Z` or an offset. The add-job UI explicitly uses UTC input; display times use each job's IANA timezone. Input bounds: runtime 1–720 minutes, positive power up to 10,000 kW, a positive earliest/deadline window at most 48 hours, and at most 20 existing prerequisites.

With the server running, execute `.venv\Scripts\python.exe scripts\smoke.py` on Windows or `.venv/bin/python scripts/smoke.py` on Unix. **This explicitly resets demo jobs**, checks real HTTP routes and writes `docs/demo-evidence.json`; it leaves a clean evaluated queue ready to present. Earlier audit history remains available through `all_runs=true`.

## Docker

```bash
docker build -t verdant .
docker run --rm -p 127.0.0.1:8000:8000 -v verdant-data:/app/data verdant
```

Container runs as a non-root user. `.env`, local databases and virtual environments are excluded from the image. Use environment flags to opt into providers. Docker CLI was not installed in the build environment, so the Docker image has not been built or executed here.

## Assumptions and deliberate limits

- This is a trusted local, single-process demo. It has no login, authenticated approver identity, RBAC, tenancy, rate limiting, or real Airflow/Kubernetes integration. Bind to loopback by default. A real pilot needs these controls before network exposure.
- One run has constant estimated power and runtime. No shared-cluster capacity, concurrency limits, calendars, data locality, tariff cost, retry behavior, or runtime uncertainty beyond the safety buffer is modeled.
- Baseline is always 14:00 local on the earliest-start date, even if that counterfactual is infeasible. Infeasible baseline replacements always require review and are flagged in the report. No emergency reschedule is silently treated as normal automatic carbon optimization.
- The 30-minute grid is aligned in UTC. Supported zones have whole-hour or half-hour offsets, so local half-hour alignment also holds; IANA rules account for DST.
- SQLite transaction serialization protects concurrent agent cycles in one process. The audit table forbids UPDATE/DELETE through SQLite triggers, but this is not a cryptographically tamper-proof ledger against a database administrator.
- The live curve cache can delay recovery by up to its TTL. Provider requests and optional explanations are synchronous and can temporarily delay other operations; use the synthetic mode for a predictable stage demo.
- No forecasts are asserted to be ground truth. Savings use attributional grid intensity; no claim is made about marginal/consequential grid emissions or certified carbon credits.
- Customer validation is outstanding. The developer guide supplies an interview and pilot plan, not invented interview findings.

## References

- [Green Software Foundation SCI specification](https://sci.greensoftware.foundation/) — method and functional unit.
- [Electricity Maps V4 forecast reference](https://app.electricitymaps.com/docs/reference/carbon-intensity/forecast) — request parameters, hourly forecast shape and units.
- [OpenAI text-generation guide](https://developers.openai.com/api/docs/guides/text) — optional Responses API narration adapter.

Hackathon theme, rubric weights and the 90-day production-pilot emphasis were taken from the three user-provided event screenshots. They were treated as context, not instructions to submit forms or contact anyone.
