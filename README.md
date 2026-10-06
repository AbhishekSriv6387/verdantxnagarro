# Verdant — Carbon-Aware Batch Job Scheduler Agent

**A greener window. The same deadline.**

Verdant finds lower-carbon execution windows for enterprise batch jobs, automatically moves independent flexible jobs, and asks a human before changing critical or dependency-linked work. It is a complete local hackathon demo with FastAPI, SQLite, a vanilla-JavaScript dashboard, and no frontend build or CDN requirements.

**All displayed savings are modeled SCI estimates.** The default dataset is prominently labeled **SIMULATED**. The app dispatches no real workloads and makes no claim of measured emissions reductions or completed customer validation.

**🎬 Demo video:** https://nagarro-my.sharepoint.com/:v:/p/abhishek_srivastava04/IQDo9_6vL5JYSJ4wjpMCfT7PAdGIg46VXuybIGwdBVCeasg?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=UhhIsJ

### Hackathon Deliverables

| Deliverable | Location | Description |
|---|---|---|
| **README** | This file | Setup, run instructions, sample data, known limitations |
| **Agent design document** | [docs/agent-design.md](docs/agent-design.md) | Architecture diagram, goal, users, data sources, tools, orchestration, decision points, human oversight, failure handling |
| **Pitch deck** | [docs/pitch-deck.md](docs/pitch-deck.md) | 10 slides: problem, solution, agent workflow, methodology, results, impact, efficiency, demo walkthrough, roadmap, summary |
| **Augmentation log** | [docs/augmentation-log.md](docs/augmentation-log.md) | AI usage across the SDLC: tasks attempted, outputs accepted/modified/rejected, errors identified, corrective steps |
| **Demo video** | *To be recorded* | 3–5 minutes of the agent running (not a slide walkthrough) |
| **Developer guide** | [docs/UNDERSTAND_THIS.md](docs/UNDERSTAND_THIS.md) | Presenter script, rubric mapping, 90-day pilot plan, jury Q&A |

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

Open **http://127.0.0.1:8000** and sign in. On first launch, username is `admin`; set `VERDANT_ADMIN_PASSWORD` (12+ characters) beforehand, or read the randomly generated password in `data/carbon.db.control.bootstrap.txt` (beside the control database if DATABASE_PATH differs). Change it in **Clients, access & account**, then delete the bootstrap file. No external account, carbon token, internet connection, Node.js, or build step is needed after dependencies are installed. `requirements.txt` declares supported ranges; `requirements.lock` records the exact verified dependency set. For an air-gapped environment, download these wheels on a connected machine first.

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
4. Open **Approval inbox**, enter a comment (reviewer identity comes from sign-in), and approve **Daily revenue report**. Its schedule and accounting update only after approval. Reject another proposal to show that rejected changes receive no savings credit.
5. Expand **Decision log → Inspect complete decision evidence**. Show rule IDs, intensity intervals, candidate starts, margins, source, and actor.
6. Click **Replay 7 days**: 175 seeded jobs, about **167,144 g / 167.1 kg CO₂e** of modeled savings on 105 applied schedules, roughly **40.7%**. This is a separate experiment and leaves the active queue untouched.
7. Export a CSV or JSON report. Advance the demo clock to show simulated completion.

The complete presenter script, plain-English walkthrough, rubric mapping and 90-day pilot proposal are in [docs/UNDERSTAND_THIS.md](docs/UNDERSTAND_THIS.md). Reproducible HTTP verification results are in [docs/demo-evidence.json](docs/demo-evidence.json).

## What is implemented

- Typed job input with explicit timezone offsets, supported zones, bounded workload parameters, and server-controlled baseline/status.
- Exhaustive 30-minute candidate search using exact time-weighted carbon intensity over each run; deterministic earliest-start tie breaking.
- SLA deadline minus runtime minus safety buffer; no starts before the simulated clock or prerequisite completion.
- Dual savings threshold, default **5% AND 5 g**, with independent flexible jobs only eligible for automatic movement.
- Approval/rejection with authenticated reviewer identity and required human comment; stale approvals are rejected and dependency feasibility is checked again when applying.
- Append-only SQLite audit records enforced with triggers; decisions reference content-addressed frozen curves; used intensity intervals, best three plus chosen candidates, rules, thresholds, actor and both timestamps are retained. Legacy audit rows remain untouched.
- Explicit LIVE / REAL (RECORDED) / SIMULATED carbon provenance and separate SIMULATED WORKLOAD labels. No averaging of live readings with synthetic filler inside a decision.
- Persistent simulated clock, isolated weekly replay, reset with audit-history retention, browser queue watcher, and SCI exports.
- Responsive dark dashboard, SVG charts, source badges, queue filters, approval inbox, log filters and add-job form.
- Optional text-only OpenAI adapter remains available to standalone SchedulerService consumers. The authenticated platform currently disables external LLM narration for all workspaces; deterministic explanations remain authoritative.


## Client and project platform (October 2026)

The platform separates **client → project → environment** using stable server-generated IDs. Open **Clients, access & account** in the sidebar (`/admin`) to create a client, project, environment and assigned users. New environments start empty; add a job or explicitly generate/reset a SIMULATED WORKLOAD. A name such as Production does not turn this demo into a real workload executor.

Existing jobs/history remain in **Local demo / Default project / Demo** (`client-default`, `project-default`, `env-default`). The existing database is retained; only mutable job payloads gain scope IDs. Old decisions remain append-only and belong to their original environment store. The old `project` string remains a workload-group label for compatibility; it never grants access. Team labels likewise are not security roles. New audit rows and report rows carry tenant/project/environment IDs; old evidence is returned with its store scope.

| Role | Scope and authority |
|---|---|
| Platform administrator | All workspaces and onboarding; organization reports still obey client consent |
| Client administrator | Own client, projects, users, policies, providers, jobs and approvals; can authorize its aggregate reporting |
| Project operator | Assigned project's environments: read, add jobs, cycle, scale/reset/replay/advance; cannot approve |
| Approver | Read assigned project's environments and approve/reject; cannot run cycles or replace queues |
| Viewer | Read/export assigned project's environments; cannot change scheduling or access |

Memberships are project-scoped (all its environments); environment-only role grants are not implemented. A user may have multiple roles. Administrators create local accounts with initial passwords; users can change their password and revoke all their sessions. Platform administration is bootstrapped to the initial `admin` account; there is no UI for creating additional platform administrators. Client administrators cannot link identities from unrelated clients. Platform administrators can link an existing user to another client. Removing a membership is effective on subsequent requests without requiring sign-out.

The header workspace selector controls the entire dashboard. Every data API requires a session cookie plus `?environment_id=<id>` or `X-Environment-ID`. A selector can be omitted only when the account has exactly one accessible environment. Guessed inaccessible scopes return 404; missing sign-in returns 401; insufficient role returns 403. Scope is checked before job lookup, exports, analysis, replay, reset, clock advancement or frozen evidence. `project=name` filters only groups within that authorized environment. Evidence IDs are local to an environment; always keep the environment ID with an evidence link. Public health/schema/static pages contain no workload data.

### Storage and configuration

```text
Browser sign-in / workspace selector / administration
                         |
              FastAPI authorization boundary
                 /                    \
  <DATABASE_PATH>.control.db      Authorized environment
  users / memberships             isolated SQLite scheduler store
  clients / projects              jobs / clock / frozen audit / replay
  environments / sessions                    |
  consent / admin events          same deterministic engine + scoped provider
```

The original environment uses DATABASE_PATH. New environment databases live in its sibling `environments/<environment-id>.db`. Back up the control database AND all environment databases together. Generated state/bootstrap credentials stay under ignored `data/` by default. If customizing DATABASE_PATH outside data/, protect and ignore that directory yourself. Local file administrators retain access to all stores; this is application isolation, not separate hosts or encryption.

For Electricity Maps, `/admin` displays the exact environment variable name, e.g. `VERDANT_EM_TOKEN_<UPPERCASE_ENVIRONMENT_ID_WITH_UNDERSCORES>`. Put its value in the server environment or `.env`, restart, and select/save that environment's provider. Only that environment reads that token. No credential value is accepted by the browser configuration API or returned to users. The legacy ELECTRICITY_MAPS_TOKEN applies only to env-default. Provider choices and caches are environment-specific. Shared public recorded GB data remains available at original dates. Missing/invalid credentials retain whole-curve SIMULATED fallback. External LLM narration is intentionally disabled at the authenticated platform boundary until per-client outbound-data consent and scoped LLM credentials are implemented; the standalone adapter/tests remain available.

Project policy can raise the platform's minimum percentage savings, absolute savings and SLA buffer. It cannot weaken them or change the 14:00 baseline, criticality protection or dependency rules. Applied decisions remain frozen; approvals revalidate current temporal/dependency feasibility with the current buffer. Policy/provider changes apply to future evaluations, not automatic reconsideration of prior decisions. Restart after changing deployment-level settings; existing project policies cannot reduce deployment minima.

### Client-authorized organization reporting

Clients default to **sharing off**. An explicitly assigned client administrator changes reporting permission in `/admin`; platform-admin status alone cannot consent. `/api/organization/report` is platform-admin-only and returns client/project/environment aggregate modeled SCI totals and provenance, never job names, owners, raw decisions or credentials. Opted-out clients are omitted entirely. Revocation takes effect on the next report request; previously downloaded reports cannot be recalled. Platform administrators retain administrative workspace access independently of portfolio-report consent; consent is not a deny-access control against platform operators.

### Focused verification and limitations

For this change, use `.venv/Scripts/python.exe -m pytest -q tests/test_access.py` for essential identity/isolation/role/consent checks. The legacy API fixture now signs in; `python run.py --test` remains available but was not run in this session, per the request to minimize testing. `scripts/smoke.py` now requires SMOKE_PASSWORD (SMOKE_USERNAME defaults to admin) and accepts SMOKE_ENVIRONMENT_ID (default env-default); it resets that selected workspace. Do not point it at a workspace you need to preserve.

Local passwords use salted PBKDF2-HMAC-SHA256 (600,000 iterations); opaque eight-hour sessions are stored hashed, with HttpOnly/SameSite=Strict cookies. Login attempts are bounded per username and address. Password changes revoke all sessions; sign-out revokes the current session. Use HTTPS and SESSION_COOKIE_SECURE=true for network deployment. This is a local demo access model, not an enterprise identity product: no SSO/OIDC, MFA, email invitations, automated password recovery, client-hosted deployment automation, real workload credentials/execution adapter or security certification is claimed. The default file permissions inherit the host's access controls on Windows; protect the deployment directory. One server process is supported; provider caches, policy refresh and store locks are local to that process. Login throttling can temporarily block a shared address. No live-provider success, Docker run, measured savings or customer validation was performed in this session.

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

When an Electricity Maps token is present, reset uses current UTC rounded **up** to the next 30-minute boundary, with jobs generated relative to it. Without a token the fixed demo clock remains 9 October 2026, 00:00 UTC. Explicit recorded mode instead opens the historical replay at 15 January 2025, 00:00 UTC. The baseline remains 14:00 local on each job's earliest-start date; it is never moved to improve results. Weekly replay is always synthetic. Actual paid Electricity Maps access was not available for verification; HTTP response, retry, timeout, coverage and fallback behavior are tested with fixtures.

Synthetic curves have zone-specific base intensity, a midday solar dip, evening peak, mild overnight reduction and stable seed/time/zone-based noise. These are pedagogical scenarios, not historical reconstructions or regional forecasts.


## Public UK provider and recorded data

Set `CARBON_PROVIDER=uk` for the no-key [UK Carbon Intensity API](https://carbon-intensity.github.io/api-definitions/). It supports **GB** only and requests `/intensity/{from}/fw48h`, preserving half-hour forecast intervals. Requests have bounded retries/timeouts and a TTL cache. Complete comparison coverage is required; gaps, overlaps, invalid values, other zones and unavailable dates fall back as a whole to SIMULATED. API forecasts are labeled LIVE, not measured emissions. GB uses Europe/London, including DST. Selecting this provider seeds GB jobs; the no-token clock still stays fixed as specified, so dates outside API coverage can fall back. A live forecast integration is tested with fixtures; no successful current forecast coverage is claimed.

Set `CARBON_PROVIDER=recorded` to replay the bundled real historical GB data with GB seed jobs and the original historical clock. `app/providers/recordings/gb-response.json` is the unmodified public API response for [15-16 January 2025](https://api.carbonintensity.org.uk/intensity/2025-01-15T00:00Z/fw48h). `gb-recorded.json` preserves its `intensity.actual` values and timestamps, source URL and retrieval timestamp. The response includes the preceding 23:30 interval. This is **REAL (RECORDED)** grid-intensity data, not live data, measured workload emissions or customer validation. Recorded actual grid estimates also make this a hindsight experiment, not evidence of forecast accuracy. No historical values are shifted, repeated or extrapolated onto other dates.

Recording format: `format_version: 1`, `zone`, `source: "REAL (RECORDED)"`, `provider`, `source_url`, `retrieved_at`, and `points` with aware `start`/`end`, numerical `intensity` in g CO2e/kWh, the same `source`, and `kind: "recorded_actual"` or `"recorded_forecast"`. Sample files must set `sample: true` and are rejected by the real-data loader. A custom recording must cover the requested dates; otherwise fallback is SIMULATED. This loader validates format/provenance metadata, not the authenticity of an arbitrary file supplied by an administrator.

## Workload scale, flexibility and projects

`POST /api/demo/scale` with `{"n":25}` generates 1-500 seeded illustrative jobs and replaces only the active queue/run, preserving audit history and clock. The dashboard has the same control. These are **SIMULATED WORKLOAD**, including when their carbon source is LIVE or REAL (RECORDED). The generator uses approximately 75% flexible (including 5% deliberately infeasible), 15% hard-deadline and 10% business-critical jobs, ETL/report/ML duration and power ranges, and small dependency chains. These distributions are examples, not measured enterprise telemetry. It assigns three example projects and teams. The default 25-job reset scenario and weekly replay remain unchanged.

A measured local offline 500-job cycle completed in 2.215 seconds during this session; the regression test requires under five seconds. This is a local test result, not a production throughput guarantee. Per-cycle dependency indexes eliminate repeated whole-queue relationship scans. Identical curve requests are reused within a cycle; all candidate starts and decision rules remain unchanged. Network requests and enabled per-job LLM narration are excluded from this offline performance expectation.

`GET /api/analysis/flexibility` and **Analyze flexibility** compare +/-1h, +/-2h, +/-4h and +/-8h start windows around each job's **original 14:00 local baseline on its earliest-start date**. Windows are clipped to original earliest start, current clock, runtime, deadline and buffer. The unchanged engine and dual thresholds evaluate independent flexible jobs with feasible baselines. Protected, linked, rejected and infeasible jobs are excluded; no approvals are invented. Existing decisions use frozen curves, unevaluated jobs use the selected provider, and sources/exclusions are returned per scenario and job. These are hypothetical modeled savings, never added to applied totals; state and audit history remain unchanged. Changing queue state invalidates the displayed analysis.

Jobs accept `project` and `team`, both defaulting to `default`. The dashboard project selector filters queue, approvals, carbon cards, current reports/exports, audit list and sensitivity. `?project=name` is supported on state, jobs, report, current export, logs and flexibility endpoints. Reports include per-project rollups; weekly replay remains its separate global seeded experiment. The legacy `project` string is now a workload-group label/filter inside one authorized environment. Scheduling and dependency checks consider that entire environment queue. Stable `project_id` identifies the actual access-controlled project; cross-environment dependencies are rejected.

Approvals and rejections require a signed-in approver/client administrator/platform administrator and a `comment`. The server records the session user ID and display name; a supplied legacy `approver_name` cannot impersonate another reviewer. Old job records load with default project/team fields; old audit rows remain immutable and readable. New curves and optional explanation records also have append-only triggers. Complete evidence is available on demand at `/api/logs/{id}/evidence`; only the best three and chosen candidate are retained inline, and all candidates can be reconstructed using the frozen curve and recorded rules.

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
| `CARBON_PROVIDER` | `auto` | `auto`, `synthetic`, `electricity_maps`, `uk`, or `recorded` |
| `RECORDED_CARBON_PATH` | `app/providers/recordings/gb-recorded.json` | Version 1 recorded intensity JSON |
| `ELECTRICITY_MAPS_TOKEN` | empty | Legacy token for env-default only; never inherited by new environments |
| `VERDANT_ADMIN_PASSWORD` | generated on first launch | Initial local admin password, 12+ characters; ignored after account exists |
| `SESSION_COOKIE_SECURE` | false | Set true behind HTTPS; local HTTP demo uses false |
| `VERDANT_EM_TOKEN_<ENV_ID>` | empty | Per-environment Electricity Maps credential; hyphens in ID become underscores, uppercase |
| `PROVIDER_TIMEOUT_SECONDS` | `3` | Timeout per provider HTTP operation |
| `PROVIDER_RETRIES` | `1` | Additional retries per endpoint, maximum 3 |
| `PROVIDER_CACHE_SECONDS` | `300` | Zone data cache TTL |
| `ENABLE_LLM_EXPLANATIONS` | `false` | Explicitly opt in to external narration |
| `OPENAI_API_KEY` | empty | Optional OpenAI key |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Configurable Responses-compatible text model |

The standalone optional narration adapter (disabled by the authenticated platform) sends only a detached decision summary (numbers, rules, source and deterministic explanation) to OpenAI with `store=false`. Names, owners and credentials are not included. External service charges and that service's data policies apply when explicitly enabled. Model access is account-dependent; any request failure falls back to deterministic text. No LLM is used to infer or downgrade criticality; users supply it explicitly.

## API and verification

The entirely local API reference is at `/docs`; the machine-readable schema is `/openapi.json`.

```text
GET  /api/health, /api/state, /api/jobs, /api/approvals, /api/report
GET  /api/jobs/{id}/curve
GET  /api/logs/{decision_id}/evidence
GET  /api/analysis/flexibility?project=default
GET  /api/logs?actor=human&outcome=APPROVED&all_runs=false
GET  /api/report/export?format=csv|json&scope=current|replay
POST /api/jobs                         JobInput JSON (see OpenAPI)
POST /api/agent/cycle                  {}
POST /api/approvals/{id}               {"action":"approve","approver_name":"Reviewer name","comment":"Reviewed SLA"}
POST /api/clock/advance                {"minutes":60}
POST /api/demo/reset                  {}
POST /api/demo/scale                  {"n":25} (1-500; replaces queue, retains history)
POST /api/demo/replay                 {}
```

`422` is invalid input; `409` is a conflicting/expired action; `404` is an unknown job. Timestamps must include `Z` or an offset. The add-job UI explicitly uses UTC input; display times use each job's IANA timezone. Input bounds: runtime 1–720 minutes, positive power up to 10,000 kW, a positive earliest/deadline window at most 48 hours, and at most 20 existing prerequisites.

With the server running and SMOKE_PASSWORD set for an authorized account (see client/project setup above), execute `.venv\Scripts\python.exe scripts\smoke.py` on Windows or `.venv/bin/python scripts/smoke.py` on Unix. **This explicitly resets demo jobs**, checks real HTTP routes and writes `docs/demo-evidence.json`; it leaves a clean evaluated queue ready to present. Earlier audit history remains available through `all_runs=true`.

## Docker

```bash
docker build -t verdant .
docker run --rm -p 127.0.0.1:8000:8000 -v verdant-data:/app/data verdant
```

Container runs as a non-root user. `.env`, local databases and virtual environments are excluded from the image. Use environment flags to opt into providers. Docker CLI was not installed in the build environment, so the Docker image has not been built or executed here.

## Assumptions and deliberate limits

- This is a local, single-process demo with password sign-in, scoped roles, environment isolation and bounded login attempts. It has no enterprise SSO/MFA, general API quotas or real Airflow/Kubernetes integration. Bind to loopback by default; a network pilot needs HTTPS, enterprise identity integration and independent security review.
- One run has constant estimated power and runtime. No shared-cluster capacity, concurrency limits, calendars, data locality, tariff cost, retry behavior, or runtime uncertainty beyond the safety buffer is modeled.
- Baseline is always 14:00 local on the earliest-start date, even if that counterfactual is infeasible. Infeasible baseline replacements always require review and are flagged in the report. No emergency reschedule is silently treated as normal automatic carbon optimization.
- The 30-minute grid is aligned in UTC. Supported zones have whole-hour or half-hour offsets, so local half-hour alignment also holds; IANA rules account for DST.
- SQLite transaction serialization protects concurrent agent cycles in one process. The audit table forbids UPDATE/DELETE through SQLite triggers, but this is not a cryptographically tamper-proof ledger against a database administrator.
- The live curve cache can delay recovery by up to its TTL. Provider requests remain synchronous inside the scheduling transaction. Optional explanations run synchronously **after commit**, outside the store lock, and append to a separate immutable explanation table; a slow model can delay the cycle HTTP response but cannot hold the scheduling transaction. Narration failures leave deterministic evidence intact; use the synthetic mode for a predictable stage demo.
- No forecasts are asserted to be ground truth. Savings use attributional grid intensity; no claim is made about marginal/consequential grid emissions or certified carbon credits.
- Customer validation is outstanding. The developer guide supplies an interview and pilot plan, not invented interview findings.

## References

- [Green Software Foundation SCI specification](https://sci.greensoftware.foundation/) — method and functional unit.
- [Electricity Maps V4 forecast reference](https://app.electricitymaps.com/docs/reference/carbon-intensity/forecast) — request parameters, hourly forecast shape and units.
- [OpenAI text-generation guide](https://developers.openai.com/api/docs/guides/text) — optional Responses API narration adapter.

Hackathon theme, rubric weights and the 90-day production-pilot emphasis were taken from the three user-provided event screenshots. They were treated as context, not instructions to submit forms or contact anyone.
