# Understand Verdant

## What you have built

Verdant is a working proof of a simple idea: when a batch job has room in its schedule, choose a cleaner electricity window without missing its deadline. A nightly report, an ETL pipeline or a model-training run often does not have to start at one exact minute. The app quantifies that flexibility, changes safe schedules, and leaves sensitive decisions with a person.

The project fits the hackathon's **Sustainability** theme and also demonstrates enterprise workflow improvement. The screenshots emphasize specific user pain, measurable evidence, responsible engineering and a credible 90-day pilot. Those priorities shaped the demo: its output is a proposed/applied schedule with a transparent estimate and an audit trail.

Suggested one-line challenge statement:

> We are helping data-platform and ML-operations teams move flexible batch workloads from fixed daytime schedules to lower-carbon windows, measured by modeled grams CO₂e per run and deadline compliance.

Use “modeled” until you have actual production measurements. This prototype does not execute real ETL or ML work, and no customer interviews were performed during its creation.

## The experience, from start to finish

Open the dashboard. By default it contains the fixed demo clock and 25 sample jobs. With an Electricity Maps token, reset rounds current UTC up to the next half-hour and seeds jobs relative to it. Explicit recorded mode uses the historical archive date. Every job has a duration, estimated power, location, earliest start, deadline and criticality. Three jobs form an extract → transform → publish chain. One backfill is deliberately too large for its deadline.

When you press **Run agent cycle**, the app gathers intensity data, evaluates pending jobs and saves its decisions. A flexible, independent job can move automatically. A business-critical job can receive a proposal, but no changed schedule appears until a person approves it. A dependent job waits until its prerequisite has an applied schedule, then gets its own review.

The dashboard updates its totals only for applied schedules. Pending proposals show potential savings in the inbox but do not make the impact cards look artificially better. Rejected proposals are not dispatched and receive no credit. The event history records the reasoning and the human's comment.

The clock advances only when you ask. After an applied run's modeled finish time passes, the app labels it completed. “Completed” here means simulated completion. It is not a claim that a data pipeline actually ran.

## Why this is an agent

It observes state (queue, clock, dependencies, carbon data), evaluates a constrained decision, acts within explicit authority, and escalates when authority is insufficient. You can enable the browser watcher to repeat that cycle every 30 seconds. The decisions are deterministic, which makes this financial/operational-style approval workflow easier to audit and test.

An LLM is not required for the scheduler to be agentic. The optional OpenAI layer can rephrase a completed decision, but it has no scheduling tool and receives a detached copy. A test gives that plug-in deliberately malicious behavior and confirms that protected jobs still cannot be moved. Criticality is always explicit; there is no AI classification that silently downgrades an important workload.

## Follow the modules

### `models.py`: the input contract

Pydantic defines the allowed job fields. It rejects missing timezone offsets, negative power, excessive runtimes, unsupported zones, duplicate dependencies and an invalid window. The API creates the job ID, baseline and status. Callers cannot create a job that is already “approved.”

The four supported zones (including GB) use IANA timezones. Their baseline is 14:00 on the local date of earliest start, stored internally as UTC. The UI's add-job form takes explicit UTC timestamps to avoid browser-local ambiguity; the table and chart then show each job's local time.

### `config.py`: the knobs

Environment settings control PUE, embodied allocation, savings thresholds, safety buffer, providers, storage and optional narration. Defaults are deliberately usable without secrets. Non-finite or unreasonable settings are rejected early.

### `providers/carbon.py`: where intensity comes from

The common provider interface returns a curve made of intervals. Each interval says when it starts/ends, its intensity, its source and whether it is a forecast/history/latest/synthetic observation.

The synthetic provider generates repeatable zone-specific curves. Stable hashing of seed, zone and time ensures that results do not change because a different job happened to request data first. A solar dip, evening peak and small noise make it useful for demonstrations. They do not make it real historical grid data.

The Electricity Maps adapter uses authenticated HTTPS, timeouts, retries and caching. It requests latest, history and a 48-hour forecast. If available data cannot cover every hour needed for a fair comparison, the fallback provider replaces the whole curve with synthetic data and labels it accordingly. There is no hidden live/synthetic interpolation.

The integration function computes an exact duration-weighted mean. A 45-minute run straddling two half-hour bins must give more weight to the bin containing more of that run. It rejects gaps and overlapping intervals.

### `engine/scheduler.py`: the decision

This module has no database and no network. It receives a job, queue, clock, curve and configuration and returns an evidence-rich decision.

It enumerates every 30-minute start that satisfies the earliest start, current time, dependency finish, deadline and buffer. It calculates SCI for each, chooses the smallest value, and uses the earlier start to break ties. It compares the chosen run with the fixed baseline.

If both savings thresholds pass, and the job is independent and flexible, it can move. If the job is protected, it asks for approval. If no worthwhile improvement exists and the baseline is feasible, it retains the baseline. If no candidate exists, it explains why. An infeasible baseline forces human review before any replacement, even for a flexible job.

### `service.py`: the only place that changes schedules

The service coordinates the pure decision and its database update. Optional LLM prose is requested only after commit, outside the lock, and appended against the original decision ID; deterministic evidence commits with the schedule. It applies both inside one transaction so you cannot get a changed schedule with a missing log. Duplicate cycles skip already-applied jobs and proposals. A fingerprint prevents repeated identical blocked-job decisions at the same clock/dependency state.

Approval reads the stored proposal and rechecks feasibility against the current clock and prerequisites. A person cannot approve yesterday's window. Human comments are mandatory. The signed-in reviewer identity and user ID become part of the audit record; roles are checked before review.

The service also handles seeding, time advancement, reports and isolated replay. The replay uses the same decision engine but fresh seven-day synthetic workloads. It never invents human approvals, changes the active clock, or adds replay savings to the active daily total.

### `store/sqlite.py`: the memory

SQLite stores jobs, demo state, decisions, content-addressed frozen curves and separately appended optional explanations. Jobs and state may change. Decision records can only be inserted: database triggers block UPDATE and DELETE. Reset starts a new run ID and queue while retaining old decision records, accessible with “Include past demo runs.” A write lock and transaction protect concurrent cycles in the supported single-process deployment.

This is durable and useful for a demo, but a database administrator can still alter files or drop triggers. Do not describe it as a cryptographically tamper-proof enterprise ledger.

### `api/main.py`: the public surface

FastAPI validates requests and exposes routes for jobs, cycles, approvals, clock, replay, reports and logs. It serves all dashboard assets locally. Even the API reference is local, rather than loading Swagger JavaScript from a CDN. OpenAPI remains available for integration tools.

Cross-origin writes are blocked, HTML has a restrictive content policy, SQL is parameterized, and CSV text cells are protected from spreadsheet formula interpretation. These complement the new local sign-in, scoped roles and environment isolation; enterprise identity integration and deployment security still need a pilot review.

### `ui/`: the presentation

The dashboard uses only HTML, CSS and JavaScript. SVG makes the curve and replay chart portable and offline. Source labels appear near carbon numbers. The chart uses a frozen copy of the curve that generated the decision, so refreshing a provider does not rewrite the evidence behind a past choice.

The UI escapes arbitrary text before HTML insertion. Keyboard-operable controls, focus indicators, semantic forms, chart descriptions and responsive layouts support a practical demo across screen sizes.

### `tests/` and `scripts/smoke.py`: the evidence

Tests exercise the arithmetic, time weighting, search and tie breaking, dozens of SLA windows, criticality and dependency restrictions, both thresholds, malformed providers, fallback, approvals, stale decisions, immutable logs, concurrent cycles, persistence, narration isolation and reporting.

The smoke script makes actual HTTP requests to a running server, checks important routes, and writes `docs/demo-evidence.json`. It resets only demo queue state and leaves an evaluated showcase afterward. Read that file for precise numbers from the verified configuration.

## The carbon math, with numbers

Suppose a job needs **10 kW for 90 minutes** and PUE is **1.4**:

```text
IT energy:          10 kW × 1.5 h = 15 kWh
Including overhead: 15 kWh × 1.4 = 21 kWh
Baseline intensity: 400 g CO2e/kWh
Cleaner intensity:  100 g CO2e/kWh
Embodied allocation M: 20 g per run (example; default is 0)

Baseline SCI = 21 × 400 + 20 = 8,420 g CO2e/run
Chosen SCI   = 21 × 100 + 20 = 2,120 g CO2e/run
Difference   = 6,300 g = 6.3 kg CO2e/run
Reduction    = 6,300 / 8,420 × 100 = about 74.8%
```

SCI is `((E × I) + M) / R`. Here R is **one run**, so the reported unit is grams per run. M is unchanged between alternatives and therefore cancels in the absolute delta. A nonzero M still changes the reduction percentage.

The actual synthetic demo has less extreme savings than that teaching example. Its default first cycle models around **21,014 g avoided** on **15 applied schedules**, or **39.8%** versus those runs' baseline. Multiplying that daily workload by seven gives about **147,095 g**. The independent seven-day replay varies durations, power and the noise pattern, so its result is about **167,144 g** across **105 applied schedules out of 175 evaluated**. The two weekly numbers answer different questions; neither is an additional savings bucket.

Do not turn these numbers into a production promise. Forecasts can be wrong, jobs can run longer, and estimated power can differ from measured power. For a pilot, collect metered/runtime telemetry and re-evaluate actual intensity after execution. This model uses average attributional intensity, not marginal grid-emission consequences. It is also a scheduling optimization, not an energy-efficiency claim: identical jobs use the same modeled kWh before and after.

## Map the project to the hackathon rubric

The weights below match the supplied event screenshot. These are evidence you can present and gaps to close, not self-awarded scores.

| Jury criterion | Weight | Evidence in this project | What strengthens the submission |
|---|---:|---|---|
| Measurable real-world impact | 25 | Per-run SCI, aggregate grams/percent, exact counterfactual, reproducible week, exportable evidence | Replace estimated power with actual workload telemetry and validate realized reductions |
| Customer or user validation | 15 | A concrete data-platform/ML-ops workflow, review UI, defined persona and interview plan below | Interview real owners and attach permissioned notes; currently **not completed** |
| Technical execution | 15 | Working offline app, deterministic exhaustive search, provider interface/fallback, persistent approvals and automated tests | Run the live provider with your entitlement and a real scheduler in shadow mode |
| Production readiness | 15 | Input validation, transactional writes, idempotence, logging, caching, Dockerfile, locked dependencies, error states | Integrate enterprise SSO/MFA with existing scoped roles; add workload adapter, telemetry, resource constraints, migrations and operations |
| Effective Codex leverage | 15 | Codex implemented backend, frontend, tests, provider fixtures and docs; ran tests, HTTP checks and browser checks | Show this conversation and specific test-driven corrections, plus AGENTS.md for continuation |
| Responsible engineering | 10 | Non-bypassable SLA/approval rules, honest source labels, no unapproved savings, constrained optional LLM | Get security review and deployment-specific data handling/approval policies |
| Reuse and scale potential | 5 | Small provider/engine/service modules, zone model, OpenAPI and exports | Demonstrate a second workload type/team or add a thin Airflow/Kubernetes adapter |

For Codex leverage, show concrete work rather than claiming productivity percentages you did not measure: generated constraint tests, detected the offline Swagger dependency, added frozen chart provenance, and verified the complete review loop. No parallel-agent contribution or customer research should be claimed.

## User validation: honest next steps

Target three people: a data-platform scheduler owner, an ML-operations engineer, and the business owner of a critical report. With their permission, review a recent week's schedules and identify genuine flexibility.

Ask:

1. Which start times are real business requirements, and which are inherited defaults?
2. What breaks if a job shifts by one, three or six hours?
3. Which downstream dependencies and data-freshness expectations are missing from a simple deadline?
4. What evidence would you need to approve a recommendation?
5. Who can authorize an automatic change, and what is the rollback path?
6. Can you provide runtime, power/energy, baseline start and completion data for a shadow comparison?

Record interview date, role (anonymized if appropriate), exact pain point, permission to quote, observed constraint, acceptance/rejection reason and resulting product change. Do not fill this with invented answers. A prototype usability session is useful but is not evidence of realized carbon savings.

Suggested pilot acceptance targets, to agree with users rather than report as achieved: zero unauthorized critical-job movements, zero scheduler-induced SLA misses, 100% source/evidence completeness, and a positive net measured carbon delta after accounting for retries and displaced work. Set a savings target only after examining the real fleet.

## A credible 90-day production pilot

| Period | Work | Exit evidence |
|---|---|---|
| Days 1–15 | Interview owners; select one queue and authorized zones; inventory dependencies, calendars and data-freshness limits | Signed-off eligibility rules and baseline workload dataset |
| Days 16–30 | Add read-only Airflow/Kubernetes adapter, real carbon entitlement and measured energy/runtime inputs | Shadow recommendations compared with unchanged actual runs |
| Days 31–45 | Integrate enterprise identity with existing scoped roles and authenticated audit; harden secrets management, retention and monitoring | Security review, rollback procedure and dry-run validation |
| Days 46–60 | Add capacity constraints and uncertainty-aware duration/forecast margins | Stress tests, failure recovery and no induced SLA violations in shadow mode |
| Days 61–75 | Enable a small allowlisted flexible queue with a kill switch | Daily measured execution outcomes and approvals reviewed with owners |
| Days 76–90 | Expand only if results justify it; reconcile actual carbon and operational burden | Pilot decision memo: measured impact, reliability, cost and user acceptance |

Production accounting should preserve baseline policy before making changes, distinguish forecast from realized intensity, and report coverage and exclusions alongside any claimed improvement. A useful first integration is a schedule-proposal adapter; job execution should remain with the existing orchestrator.

## Your two-minute presenter script

**0:00–0:20 — The pain.** “Our batch jobs often start at convenient fixed times. Electricity's carbon intensity changes during the day. Verdant asks whether the same work can run in a cleaner window while preserving its deadline.” Show the SIMULATED badge and state the demo boundary.

**0:20–0:45 — Autonomous action.** Click Run agent cycle. “Fifteen independent flexible jobs now have lower-carbon schedules. This first cycle estimates about 21 kg avoided. Repeating the cycle is safe.” Click again and show the no-duplicate response.

**0:45–1:05 — Explain one decision.** Select Warehouse refresh. Point to baseline and chosen markers. “We compare every feasible half-hour start, include PUE, integrate intensity over the whole run, and require both a minimum percentage and absolute saving. The deadline buffer is enforced by code.”

**1:05–1:25 — Human control.** Open the approval inbox and approve Daily revenue report with a short comment. “Business-critical and linked jobs stay with an owner. Approval rechecks time and dependencies; only then do we apply and count the change.”

**1:25–1:45 — Evidence and scale.** Open its decision log, then replay seven days. “Here are the inputs, rules, actor and candidate windows. Our repeatable 175-job scenario estimates about 167 kg avoided on 105 applied runs. We exclude unapproved and impossible work.”

**1:45–2:00 — Honest pilot ask.** “These are modeled results, not production claims. We want one platform team and one queue for a 90-day pilot: shadow real schedules, meter energy, validate constraints, then allowlist safe changes.”

## Likely jury questions

**Why not always run at night?** Cleaner periods depend on the zone and generation mix. Solar-rich grids can be cleaner midday; the point is to compare data, not replace one fixed-time rule with another.

**What if the carbon API fails?** The demo remains usable with a clearly labeled synthetic curve. In a real pilot, policy should decide whether to keep the original schedule or require review when data is unavailable; synthetic production optimization should not be enabled by default.

**What if the deadline is impossible?** The app records `NO_FEASIBLE_WINDOW`, leaves the job unresolved and credits no savings. It does not invent extra capacity or relax the deadline.

**Can the AI bypass controls?** Scheduling authority is deterministic Python code. Optional model prose is kept separate and tested for attempted decision mutation.

**Where is real validation?** It has not happened yet. Present the prototype and interview plan honestly; attach real permissioned feedback when collected.

**What is missing before production?** Enterprise SSO/MFA, real execution integration, measured energy, capacity contention, operational calendars, prediction uncertainty, migrations, high availability and organization-specific compliance controls. The Dockerfile is provided but Docker execution was not available in this build environment.

## Reading references

The [SCI specification](https://sci.greensoftware.foundation/) defines the calculation framework. [Electricity Maps forecast documentation](https://app.electricitymaps.com/docs/reference/carbon-intensity/forecast) defines the provider's API shape. The [OpenAI text guide](https://developers.openai.com/api/docs/guides/text) supports the optional narration adapter. The three event screenshots supplied by the user are the source for the hackathon theme, weights and pilot emphasis.


## Additions from the October 2026 improvement session

- Curves are stored once by SHA-256 content hash. New decisions retain best three plus chosen candidates, the full candidate count, thresholds and all actually used intensity intervals. The evidence endpoint resolves original frozen data; a provider refresh cannot rewrite it. Existing audit rows and all append-only triggers remain intact.
- The UK Carbon Intensity adapter supplies no-key GB half-hour forecasts for 48 hours, using the same complete-coverage-or-whole-fallback policy. In no-token mode the fixed clock can request dates unavailable from a live API; the source then honestly says SIMULATED. Recorded mode uses bundled actual grid estimates from the public API for 15-16 January 2025, at original dates, labeled REAL (RECORDED). They are neither measured job emissions nor live forecasts. README documents selection, format and source URL.
- The workload generator replaces the active queue with up to 500 seeded jobs, retaining audit history. Every generated workload is SIMULATED WORKLOAD independently of carbon provenance. The distributions are illustrative, not customer-validated. A 500-job offline local cycle was measured at 2.215 seconds; network and optional LLM latency are separate limitations.
- Flexibility sensitivity is a read-only, hypothetical analysis of +/-1, 2, 4 and 8-hour start windows around the original fixed baseline. It clips windows to all original constraints and excludes protected, linked, rejected or baseline-infeasible jobs. It uses frozen evidence for evaluated jobs and preserves both thresholds. Its chart never changes applied-savings totals.
- Project and team fields default to `default`. Dashboard/report filters and project rollups make workload attribution visible, but do not isolate tenants or alter cross-project dependency guards. Reviewer names are required authenticated audit identity; local roles now enforce access.

See [BUILD_LOG.md](BUILD_LOG.md) for session changes and actual verification. Default demo figures in this guide remain the fixed synthetic scenario only; do not apply them to live, recorded, scaled or filtered workloads.


## How the client/project model now works

Verdant has a central directory and separate scheduler databases for each environment. A client owns projects, and projects own environments. The directory stores stable IDs, local users, memberships, project policies, provider choices and client reporting consent. A project operator sees only assigned projects; an approver can review their jobs but cannot run cycles; a viewer can read/export only. Client administrators manage their own clients. The bootstrap platform administrator maintains the service and can administer all workspaces.

`app/access.py` implements hashed local passwords, expiring hashed sessions, login throttling, membership resolution and environment-specific service creation. `app/api/access.py` implements onboarding, configuration, role grants/revocation, client consent, organization aggregates and password changes. `app/api/main.py` authenticates every data request and authorizes its environment/action before invoking the existing SchedulerService. Each environment owns its clock, queue, provider/cache, logs, evidence and replay; cross-environment dependencies are rejected. The shared pure scheduler math and safety rules are unchanged.

`app/ui/login.html` is sign-in. `/admin` is client/project/environment onboarding, access management, provider and stricter-policy configuration, reporting consent and password change. The dashboard selector chooses the active client/project/environment. Existing project strings are preserved as workload groups, while server-controlled project IDs define actual access boundaries. New environments start empty; demo generation is explicit.

An Electricity Maps credential is resolved from a variable tied to the environment ID, never from another workspace. The API displays the variable name/configured flag, not the token. The old global token belongs only to the original demo. External LLM narration is disabled in this authenticated deployment until client-specific outbound consent/credentials exist; deterministic explanations always work.

Only a designated client administrator can opt their client into organization reporting. The platform report contains approved aggregate fields and source labels; no job details or evidence. Opt-out takes effect immediately for subsequent requests. Platform administrators still have workspace administration access, so report consent is not isolation against an administrator. Local file administrators can access the database files. The next enterprise step is SSO/MFA, deployment hardening and an independent access-control review, not a claim that the demo is enterprise-certified.

A short demonstration: sign in as admin; create Client A, its Analytics project and a Development environment; create an operator and an approver; select the environment and explicitly reset/generate a simulated workload. Sign in as operator and run a cycle; approval controls are unavailable. Sign in as approver, review a protected job and show the authenticated audit identity. Sign in as a client administrator to authorize aggregate reporting, then use the platform account to show that only opted-in clients contribute to the organization view. Revoke consent and refresh to show removal. Present all savings as modeled.

These additions strengthen the technical, governance and reuse evidence in the rubric. They do not establish customer validation, realized emissions savings, enterprise SSO or production readiness. See README for exact roles, first-login steps, storage layout and limitations.
