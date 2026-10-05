# Verdant improvement build log

Session date: 4 October 2026 (Asia/Calcutta). Codex implemented the requested changes sequentially in this workspace. No parallel agents were used. No decision threshold, fixed 14:00 baseline definition, scheduling rule or guardrail was relaxed.

## Changes and step gates

1. Added SHA-256-addressed immutable curves, compact candidate evidence (best three plus chosen), frozen evidence retrieval and lazy evidence rendering. Existing audit rows remain untouched. Full suite: **81 passed**. Provider refresh test confirms old evidence and chart data are unchanged.
2. Moved optional narration after scheduling commit and outside the store lock. Append-only explanation rows reference the original decision ID; failures leave deterministic decisions intact. Full suite: **82 passed**. A concurrent reader test verifies no transaction/lock is held during narration; detached mutation cannot change outcomes.
3. Token-enabled reset uses current UTC rounded up to 30 minutes; seed jobs follow that clock. No-token default stays fixed. Added GB, UK no-key 48-hour half-hour forecast adapter and recorded-data loader. Full suite: **89 passed**. Coverage fixtures exercise gaps, overlaps, invalid values, wrong zones and cache behavior. Public historical UK data was actually fetched and bundled with raw response, exact values, original timestamps and source metadata. Recorded values are never time-shifted.
4. Added seeded POST /api/demo/scale (default 25, maximum 500), a UI control, separate SIMULATED WORKLOAD labels, varied ETL/report/ML jobs, protected categories, dependency chains and impossible windows. Indexed graph lookups, reused identical curve requests per cycle and removed unused candidate interval serialization. Full suite: **90 passed**. Separate 500-job offline cycle: **2.215 seconds** on this machine; regression requires under five seconds and duplicate-cycle idempotence. Network and LLM latency are outside this offline expectation.
5. Added read-only flexibility endpoint and chart for +/-1, 2, 4 and 8-hour start windows. Original baseline, clock, deadline/buffer, protection and dual thresholds remain intact. Frozen curves are reused. Hypothetical totals are separate from applied savings. Full suite: **91 passed**. Tests check isolation, original baseline, excluded protected jobs and provider-refresh invariance. A timestamp-format assertion was fixed to compare equivalent UTC instants.
6. Added validated project/team fields with legacy defaults, project filtering and rollups in API/dashboard/exports, and required self-reported reviewer names in immutable audit records. Full suite: **92 passed**. Tests cover name validation, audit attribution, filtered exports and rollup reconciliation.
7. Updated README, AGENTS, UNDERSTAND_THIS, environment example and local API help. Added final regression checks for immutable curves, evidence after reset, recorded-mode provenance and cross-project dependency guards. Fixed UTF-8/newline handling in edited frontend files, stale sensitivity responses and filters after a project disappears. Recorded JSON lives in `app/providers/recordings/` so the existing generated-data ignore rules cannot omit it from Git or Docker context.

## Verification

- Full offline suite was run after every numbered implementation step, with failures fixed before proceeding. Final suite: **95 passed**. One existing Starlette/httpx deprecation warning remains; dependencies were not changed.
- `node --check app/ui/app.js` passed.
- Running server uses a separate ignored `data/verification.db`, not the user's normal demo database.
- `.venv/Scripts/python.exe scripts/smoke.py` passed against the running server: offline assets, OpenAPI, cycle/idempotence, frozen chart, approval/rejection, audit, JSON/CSV exports, replay, add job, clock advance and reset.
- Default fixed synthetic figures remain unchanged: 15 applied jobs, **21013.508599999997 g** modeled daily savings; seven-day replay **167143.517135 g** on 105 applied jobs out of 175. `docs/demo-evidence.json` was reproduced by HTTP verification.
- Browser checks exercised generation and processing of 500 jobs, project filtering/rollups, reviewer-named approval, frozen evidence expansion and the sensitivity chart. Desktop (1440x1000), tablet (768x1024) and mobile (390x844) layouts were inspected. No page-level horizontal overflow or browser warnings/errors were found. Narrow charts/tables scroll within their panels. The filtered-project reset correctly returns to the default queue. Screenshots are saved in `docs/screenshots/`.

## Honest limitations

No real workloads were dispatched; no measured workload emissions, customer validation, authenticated identity, paid Electricity Maps success or Docker execution is claimed. UK live forecast behavior uses HTTP fixtures; a successful public historical-data fetch is separately verified. Recorded grid estimates support hindsight modeling, not forecast-accuracy claims. No-token UK mode retains the fixed clock and falls back if that date lacks coverage. Provider network calls still run inside the scheduling transaction; optional LLM calls run after commit but can delay the cycle response. SQLite triggers are not a cryptographic ledger against an administrator. Project/team names and reviewer attribution do not provide authentication, authorization or tenancy.

`git diff --check` passed (Git emits only its normal LF-to-CRLF conversion notices). No production deployment, commit or push was performed.
