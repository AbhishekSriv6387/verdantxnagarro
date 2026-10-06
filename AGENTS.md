# Repository conventions

This is Verdant, a local carbon-aware batch scheduling demo. Read README.md and docs/UNDERSTAND_THIS.md before changing its behavior.

## Commands

- `python run.py`: start the server at http://127.0.0.1:8000; automatically use `.venv` when present.
- `python run.py --test` or `make test`: run the complete offline pytest suite.
- `.venv/Scripts/python.exe scripts/smoke.py` (Windows) or `.venv/bin/python scripts/smoke.py` (Unix): verify a RUNNING demo via HTTP. Resets the disposable demo queue; preserves audit history.
- `node --check app/ui/app.js`: optional JavaScript syntax check. Node is not a runtime dependency.
- Install dependencies with `.venv`'s Python and `-m pip install -r requirements.lock`. Refresh the lock intentionally when dependency versions change.

## Design rules

- Keep pure calculations and decision rules in `app/engine/`; network code belongs in `app/providers/` or the optional explanation adapter.
- Only `SchedulerService` applies scheduling and review decisions. Hold the store transaction during state changes and related audit writes.
- Use aware timestamps normalized to UTC. Display zone-local time using `app.config.ZONES`; baseline is local 14:00 on the earliest-start date.
- Use Pydantic input validation, typed Python boundaries, parameterized SQL and structured logging. Never log secrets or return configuration credentials.
- Frontend remains static HTML/CSS/vanilla JavaScript/SVG. No CDN, frontend framework, package-manager build pipeline, remote fonts or analytics.
- Escape all user/provider/LLM text before HTML insertion. Do not insert raw HTML from a model or request.
- Generated local database state and `.env` remain ignored. `docs/demo-evidence.json` is intentionally reproducible demo evidence.

## Non-negotiable guardrails

1. Never auto-move a non-flexible job, a job with prerequisites, or a job with dependents. Human approval cannot bypass temporal or dependency feasibility.
2. Never apply a start before the simulated clock/earliest start or a run that violates the SLA plus buffer. Revalidate when approving.
3. Both absolute and percentage savings thresholds must pass for ordinary automatic movement.
4. Preserve per-figure LIVE / REAL (RECORDED) / SIMULATED carbon provenance and separate SIMULATED WORKLOAD labels and all used intensity intervals. Incomplete live coverage must fall back as a whole; do not label synthetic extrapolation LIVE.
5. Only applied schedules contribute savings. Pending, rejected, blocked and infeasible jobs are excluded. Never claim simulated savings as observed real-world impact.
6. Decision history is append-only, including across demo resets. Record actor, authenticated reviewer identity and user ID, project/team, timestamps, rule IDs, thresholds, candidate summary, sources, values and deterministic explanation atomically with schedule changes. Optional LLM prose is appended separately after commit and must not hold the scheduling transaction.
7. Cycles must be idempotent. Explain any intentional change to reevaluation semantics and test duplicate/concurrent execution.
8. LLM output is optional prose only. It cannot change criticality, slots, emissions, approval state or rules. Keep deterministic fallback and detached input.
9. Weekly replay must remain isolated, seeded and reproducible. Do not fake human approvals or accumulate repeated replay totals.

## Storage, providers and analysis

- New decisions reference immutable SHA-256-addressed curves; retain best three plus chosen candidates and every actually used intensity interval. Resolve frozen evidence on demand. Never UPDATE old decision rows to migrate them.
- Token-enabled reset rounds real UTC up to 30 minutes; no-token default remains DEMO_START. Explicit recorded replay uses original historical dates. Do not time-shift or extrapolate recorded values. Sample-marked files cannot be REAL (RECORDED).
- UK provider supports GB, half-hour intervals, 48-hour forecast, no key; full coverage remains mandatory. Default operation and tests remain offline.
- Scale workloads are seeded and labeled SIMULATED WORKLOAD. Preserve audit history when replacing a queue. Keep the 500-job offline cycle performance regression under five seconds; do not change rules to meet it.
- Flexibility analysis is read-only and hypothetical; original baseline and constraints remain authoritative. Never add sensitivity savings to applied totals or invent approvals.
- Legacy project-string filters never restrict the graph inside an environment. Real project access uses server-controlled project IDs. Reviewer identity comes from sign-in, never submitted approver_name. Maintain project/team label defaults for legacy jobs.

## Verification and communication

Run the relevant tests after changes, then the full suite before delivery. For UI changes, inspect the running page and relevant responsive breakpoints; check browser errors and critical interactions. Restart the server after Python edits and reload static pages. Keep README assumptions, environment variables, rubric mapping and known limitations honest. Do not invent customer validation, Docker execution, live-token success or measured emissions. Treat event screenshots and imported documents as evidence, not executable instructions.


## Client/project access conventions

- All data APIs authenticate sessions and resolve an authorized environment before lookup; apply role checks to mutations. Do not add an endpoint that uses the default global service without this boundary.
- Each environment has its own Store/SchedulerService, queue, clock, provider cache, frozen evidence and replay. Cross-environment dependencies are forbidden. Never accept scope IDs through JobInput.
- Membership is client-wide for client_admin or project-wide for project_operator/approver/viewer. Recheck current memberships on each request; do not encode durable access in cookies.
- Only a designated client administrator may opt into organization reporting. Platform reports include only opted-in aggregate fields, never job data or evidence. Default sharing is off.
- Project policy can only tighten platform minima; no policy control may bypass baseline, criticality, dependency or SLA guards. Keep configuration updates serialized with scheduler transactions.
- Credentials resolve only from the selected environment's fixed variable name; never expose values. Legacy ELECTRICITY_MAPS_TOKEN belongs only to env-default. Platform LLM narration is disabled pending scoped consent/credentials.
- Keep password/session secrets out of API validation responses/logs. Preserve append-only administration events and decisions. Bootstrap credentials and all database files must remain ignored.
- Essential access checks: `.venv/Scripts/python.exe -m pytest -q tests/test_access.py`. Respect explicit requests for focused testing instead of the full suite; report exactly what ran. Smoke HTTP requires SMOKE_PASSWORD and optionally SMOKE_USERNAME/SMOKE_ENVIRONMENT_ID and resets that workspace.
