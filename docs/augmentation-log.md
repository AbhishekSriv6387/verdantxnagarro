# Verdant — Augmentation Log (AI Usage Documentation)

> This document details the use of AI coding assistants throughout the Verdant project's software development lifecycle. It covers tasks attempted, outputs accepted, modifications made, errors identified, and corrective steps taken.

---

## 1. Summary of AI Tools Used

| Tool | Role | Scope of Use |
|---|---|---|
| **Codex (AI coding assistant)** | Primary development partner | Backend implementation, frontend UI, test creation, documentation, debugging, HTTP verification |
| **OpenAI Responses API (gpt-4.1-mini)** | Optional runtime component | Decision narration only — explicitly disabled by default; no scheduling authority |

**Important distinctions:**
- Codex was used as a **development tool** during the build phase.
- The OpenAI Responses API is an **optional runtime component** that provides prose narration of already-committed scheduling decisions. It is disabled by default and has zero authority over scheduling state.

---

## 2. Development Phases and AI Involvement

### Phase 1: Core Scheduling Engine

| Aspect | Detail |
|---|---|
| **Task** | Implement SCI-based carbon math, exhaustive candidate search, and deterministic scheduling rules |
| **AI contribution** | Generated initial implementations of `energy_kwh()`, `sci()`, `ceil_slot()`, candidate enumeration loop, and decision outcome routing |
| **Human review** | Verified all math against the SCI specification; confirmed time-weighted integration handles partial half-hour overlaps correctly |
| **Modifications** | Adjusted tie-breaking logic to use earliest-start for deterministic ordering; added explicit assertions for SLA guardrail and human-approval guardrail invariants |
| **Errors found** | Initial implementation did not correctly weight partial interval overlaps — fixed by using exact `(right - left).total_seconds()` weighting |
| **Tests created** | `test_engine.py`: SCI calculation, candidate search, tie-breaking, SLA enforcement, criticality guards, dependency ordering |

### Phase 2: Carbon Data Providers

| Aspect | Detail |
|---|---|
| **Task** | Build multi-provider carbon intensity system with honest fallback |
| **AI contribution** | Generated Electricity Maps V4 adapter, UK Carbon Intensity adapter, recorded-data loader, synthetic curve generator, and the `FallbackProvider` orchestrator |
| **Human review** | Verified API endpoint URLs, authentication headers, and response parsing against official documentation |
| **Modifications** | Changed Electricity Maps to use `auth-token` header (not `Authorization: Bearer`); added complete-coverage validation before accepting live data; ensured synthetic fallback replaces the *entire* curve, not just missing intervals |
| **Errors found** | AI initially suggested interpolating between live and synthetic data for partial coverage — rejected as dishonest; whole-curve fallback enforced instead |
| **Tests created** | `test_providers.py`: fixture-based HTTP tests for gaps, overlaps, invalid values, wrong zones, cache behavior, timeout/retry, and fallback |

### Phase 3: Transaction Coordinator (Service Layer)

| Aspect | Detail |
|---|---|
| **Task** | Implement `SchedulerService` with transactional scheduling, approval workflow, replay, and clock management |
| **AI contribution** | Generated the cycle orchestration loop, approval revalidation, fingerprint-based idempotency, replay isolation, and report aggregation |
| **Human review** | Verified that scheduling state and audit evidence commit atomically; confirmed LLM narration runs after commit and outside the store lock |
| **Modifications** | Moved optional LLM narration to after commit to prevent holding the scheduling transaction during external API calls; added `copy.deepcopy()` for the detached decision summary sent to the explainer |
| **Errors found** | Initial implementation held the store lock during optional LLM narration — identified as a potential deadlock/latency issue. Refactored to append narration separately after the scheduling transaction commits |
| **Tests created** | `test_api.py`: full cycle, idempotency, approval/rejection, stale approval rejection, clock advancement, replay isolation, export verification |

### Phase 4: Persistent Storage

| Aspect | Detail |
|---|---|
| **Task** | Build SQLite-backed persistence with append-only audit, content-addressed frozen curves, and demo reset with history retention |
| **AI contribution** | Generated the `Store` class with transaction management, job serialization, decision logging, content-addressed curve storage, and append-only triggers |
| **Human review** | Verified trigger SQL blocks UPDATE/DELETE on decision rows; confirmed frozen curves are addressed by SHA-256 content hash |
| **Modifications** | Added explicit `BEGIN IMMEDIATE` for write transactions; ensured reset creates a new `run_id` but retains all historical decision rows |
| **Errors found** | None significant — the trigger-based approach was correct from the first generation |
| **Tests created** | Guardrail tests confirming triggers reject UPDATE/DELETE attempts; persistence tests verifying data survives reset |

### Phase 5: REST API Layer

| Aspect | Detail |
|---|---|
| **Task** | Implement FastAPI routes with validation, structured logging, static delivery, and security headers |
| **AI contribution** | Generated all API routes, Pydantic request/response models, error handling, CSV/JSON export, and offline API reference page |
| **Human review** | Verified CSP headers, CORS restrictions, and CSV formula-injection protection |
| **Modifications** | Detected that the initial API reference loaded Swagger UI JavaScript from a CDN — replaced with a fully offline, locally served API reference page |
| **Errors found** | CDN dependency for Swagger UI violated the offline-first design principle. Replaced with a static HTML page listing all endpoints |
| **Tests created** | `test_api.py`: input validation, error codes, concurrent requests, export format verification |

### Phase 6: Dashboard UI

| Aspect | Detail |
|---|---|
| **Task** | Build a responsive dark dashboard with SVG charts, approval inbox, decision log, and project filters |
| **AI contribution** | Generated the complete static HTML/CSS/JS/SVG dashboard, including the carbon intensity chart, approval workflow, decision evidence expansion, replay chart, and workspace selector |
| **Human review** | Inspected at desktop (1440×1000), tablet (768×1024), and mobile (390×844) breakpoints; verified keyboard accessibility, focus indicators, and no horizontal overflow |
| **Modifications** | Fixed sidebar to use dynamic viewport height with independent scrolling; added wrapping for legends and filter controls; aligned workload input/button and reviewer field; ensured mobile layout flows navigation above the dashboard |
| **Errors found** | Initial sidebar used fixed height that caused content clipping on short viewports. Corrected with `dvh` units and overflow-y scrolling. Some UTF-8/newline handling issues in edited files were fixed |
| **Tests created** | `node --check app/ui/app.js` for syntax validation; visual browser inspections documented in BUILD_LOG.md |

### Phase 7: Authentication & Multi-Tenant Platform

| Aspect | Detail |
|---|---|
| **Task** | Add local identity management, RBAC, tenant isolation, session management, and administrative UI |
| **AI contribution** | Generated the `Directory` class with salted password hashing, hashed sessions, login throttling, membership resolution, environment-specific service creation, and the `/admin` and `/login` pages |
| **Human review** | Verified PBKDF2 iteration count (600K), session hash comparison using `hmac.compare_digest()`, HttpOnly/SameSite cookie settings, and per-environment credential isolation |
| **Modifications** | Changed bootstrap credential file to use `os.open()` with `0o600` permissions; added explicit constant-time comparison for password hashes; ensured reviewer identity comes from session, not user-submitted fields |
| **Errors found** | Initial implementation used a shared default password — changed to auto-generated password with secure file output |
| **Tests created** | `test_access.py`: 14 focused identity/isolation/role/consent checks |

### Phase 8: Content-Addressed Evidence & Scale

| Aspect | Detail |
|---|---|
| **Task** | Add SHA-256-addressed immutable curves, compact candidate evidence, workload generator, and performance optimization |
| **AI contribution** | Generated content-addressed curve storage, best-three-plus-chosen candidate retention, seeded workload generator with realistic distributions, per-cycle graph indexing, and curve reuse optimization |
| **Human review** | Verified 500-job cycle performance (2.215s); confirmed duplicate-cycle idempotency; validated that old decision rows are never UPDATE'd |
| **Modifications** | Removed unused candidate interval serialization that was inflating storage; added indexed graph lookups to eliminate repeated whole-queue relationship scans |
| **Errors found** | Initial workload generator produced unrealistic distributions — refined to 75% flexible, 15% hard-deadline, 10% business-critical with small dependency chains and deliberate edge cases |
| **Tests created** | `test_scale.py`: 500-job regression under 5 seconds; idempotency after scale |

### Phase 9: Documentation & Verification

| Aspect | Detail |
|---|---|
| **Task** | Write README, UNDERSTAND_THIS.md, BUILD_LOG.md, AGENTS.md; run full test suite and HTTP verification |
| **AI contribution** | Generated comprehensive documentation including architecture diagrams, carbon math explanations, rubric mapping, presenter script, jury Q&A, and 90-day pilot plan |
| **Human review** | Verified all claimed numbers against `demo-evidence.json`; confirmed honest framing of limitations; ensured no invented customer validation or measured impact claims |
| **Modifications** | Removed several instances where AI-generated text implied production readiness or customer validation that had not occurred; added explicit "not yet completed" markers for user interviews |
| **Errors found** | AI-generated documentation occasionally presented simulated results as if they were validated — corrected with explicit SIMULATED labels and caveat language |
| **Tests created** | Full 95-test suite passing; `smoke.py` HTTP verification; `demo-evidence.json` reproduced |

---

## 3. AI-Generated Code Acceptance Rates

| Category | Generated | Accepted As-Is | Modified | Rejected |
|---|---|---|---|---|
| Scheduling engine | Core functions | ~70% | ~25% (math precision) | ~5% (incorrect weighting) |
| Carbon providers | Adapters + fallback | ~60% | ~30% (auth headers, coverage) | ~10% (interpolation approach) |
| Service layer | Orchestration | ~65% | ~30% (lock management) | ~5% (transaction scope) |
| Storage | SQLite + triggers | ~80% | ~15% (transaction mode) | ~5% (migration approach) |
| API routes | REST endpoints | ~75% | ~20% (security headers) | ~5% (CDN dependency) |
| Dashboard UI | HTML/CSS/JS/SVG | ~60% | ~35% (layout, responsive) | ~5% (viewport issues) |
| Auth platform | Identity + RBAC | ~70% | ~25% (crypto choices) | ~5% (default passwords) |
| Tests | All test files | ~75% | ~20% (edge cases) | ~5% (false assertions) |
| Documentation | All docs | ~65% | ~30% (honesty/caveats) | ~5% (invented claims) |

---

## 4. Key Errors Identified and Corrective Actions

### Error 1: Partial Live/Synthetic Interpolation
- **What happened:** AI suggested blending live API data with synthetic fill for intervals without coverage.
- **Why it's wrong:** This would dishonestly label a mixed-provenance curve as "LIVE" and undermine evidence integrity.
- **Correction:** Enforced whole-curve fallback — if any interval lacks live coverage, the entire curve uses synthetic data with a SIMULATED label.
- **Guardrail added:** Integration function validates complete, non-overlapping coverage before returning.

### Error 2: LLM Narration Holding Store Lock
- **What happened:** Initial implementation called the OpenAI API inside the scheduling transaction.
- **Why it's wrong:** External API latency or failure could hold the SQLite write lock, blocking concurrent operations and potentially causing timeouts.
- **Correction:** Moved LLM narration to after the scheduling transaction commits, outside the store lock. Narration appends to a separate immutable explanation table.
- **Guardrail added:** Test verifies no lock is held during narration; narration failures leave deterministic evidence intact.

### Error 3: CDN Dependency for API Reference
- **What happened:** AI generated an API reference page that loaded Swagger UI JavaScript from an external CDN.
- **Why it's wrong:** Violates the offline-first design principle and introduces an external dependency.
- **Correction:** Replaced with a fully static, locally served HTML reference page.
- **Guardrail added:** AGENTS.md rule: "Frontend remains static HTML/CSS/vanilla JavaScript/SVG. No CDN."

### Error 4: Overly Optimistic Documentation
- **What happened:** AI-generated documentation occasionally framed simulated results as validated production outcomes.
- **Why it's wrong:** Claiming measured emissions reductions without production telemetry is dishonest.
- **Correction:** Added explicit SIMULATED labels, "modeled SCI estimates" language, and "not yet completed" markers for customer interviews.
- **Guardrail added:** AGENTS.md rule: "Do not invent customer validation, Docker execution, live-token success or measured emissions."

### Error 5: Shared Default Admin Password
- **What happened:** Initial bootstrap used a hardcoded default password for the admin account.
- **Why it's wrong:** Security risk — any deployment would share the same credential.
- **Correction:** Changed to auto-generated cryptographically random password written to a permissions-restricted file, or user-supplied via `VERDANT_ADMIN_PASSWORD` environment variable (minimum 12 characters).
- **Guardrail added:** `os.open()` with `0o600` permissions; bootstrap file must be deleted after first sign-in.

---

## 5. AI Usage in Testing

| Test File | Tests | AI Role | Human Corrections |
|---|---|---|---|
| `test_engine.py` | 15+ | Generated core math, search, and guardrail tests | Added precision edge cases and partial-overlap scenarios |
| `test_providers.py` | 12+ | Generated fixture-based provider tests | Added cache invalidation, timeout, and wrong-zone cases |
| `test_api.py` | 20+ | Generated HTTP integration tests | Fixed Starlette/httpx deprecation handling; added concurrent tests |
| `test_explanations.py` | 5+ | Generated narration isolation tests | Added malicious-output test confirming protected jobs remain unmoved |
| `test_projects.py` | 6+ | Generated project filter and rollup tests | Added audit attribution verification |
| `test_access.py` | 14 | Generated identity, isolation, and role tests | Added cross-tenant isolation and consent revocation tests |
| `test_scale.py` | 3 | Generated performance regression tests | Calibrated 5-second threshold from actual measurements |
| `test_sensitivity.py` | 3 | Generated flexibility analysis tests | Added original-baseline preservation checks |

**Total automated tests: 95** (all passing)

---

## 6. AI Usage in Runtime (Optional Narration)

### Architecture

```
  Scheduling Decision (committed, frozen)
        │
        ▼
  Detached summary created (copy.deepcopy)
  Fields: outcome, rule_ids, carbon values, source, explanation
  Excluded: job names, owners, credentials
        │
        ▼
  OpenAI Responses API (gpt-4.1-mini)
  Parameters: store=false, max_output_tokens=180
        │
        ├─ Success: prose appended to immutable explanation table
        │
        └─ Failure: deterministic evidence unchanged; narration absent
```

### Constraints

- **Disabled by default** (`ENABLE_LLM_EXPLANATIONS=false`).
- **Disabled by the platform** for all authenticated workspaces until per-client outbound-data consent is implemented.
- **store=false** prevents external retention of decision data.
- **No scheduling authority** — LLM output cannot change criticality, slots, emissions, approval state, or rules.
- **180-token cap** per decision narration.
- **Tested for resilience** — a dedicated test sends malicious LLM output and confirms protected jobs cannot be moved.

---

## 7. What AI Did NOT Do

| Activity | Status | Reason |
|---|---|---|
| Customer interviews | ❌ Not performed | Requires real human participants with permissioned data |
| Production deployment | ❌ Not performed | Requires enterprise infrastructure and security review |
| Docker image execution | ❌ Not verified | Docker CLI was not installed in the build environment |
| Live Electricity Maps testing | ❌ Not verified with paid token | Tested with HTTP fixtures only |
| Measured emissions reductions | ❌ Not claimed | Requires production telemetry and post-execution reconciliation |
| Security certification | ❌ Not performed | Requires independent security audit |
| Parallel agent coordination | ❌ Not used | All development was sequential, single-agent |
| Productivity percentage claims | ❌ Not made | AI contribution is described qualitatively, not with invented metrics |

---

## 8. Lessons Learned

1. **AI-generated math needs verification against specifications.** The SCI calculation looked correct but had a subtle time-weighting bug that unit tests caught. Always verify against the reference specification, not just "does it compile."

2. **AI tends toward completeness over honesty.** Multiple instances of AI-generated documentation presented simulated results as if validated. Active review and explicit honesty guardrails are essential.

3. **AI-generated security code needs cryptographic review.** Default password handling, session management, and hash algorithms all required human correction. AI chose reasonable algorithms but needed iteration counts and implementation details verified.

4. **AI excels at boilerplate with constraints.** Given clear AGENTS.md rules, the AI consistently produced code that respected guardrails. The rules file functioned as a "constitution" that prevented architectural drift across sessions.

5. **Test-driven development with AI is highly productive.** Writing tests first (or concurrently) caught errors in AI-generated code within the same session. The test suite became the ground truth that both human and AI contributions were measured against.

---

## 9. Verification Trail

| Verification | Method | Result |
|---|---|---|
| Full test suite | `python run.py --test` | 95 passed |
| JavaScript syntax | `node --check app/ui/app.js` | Passed |
| HTTP smoke test | `scripts/smoke.py` against running server | Passed; `demo-evidence.json` reproduced |
| Browser inspection | Desktop, tablet, mobile viewpoints | No overflow, no console errors |
| Git whitespace | `git diff --check` | Passed (LF/CRLF notices only) |
| Responsive layout | 1440×1000, 768×1024, 390×844, 1224×468 | All verified |

---

*This augmentation log was created for the "Prompt, Plan, Preserve" hackathon submission. It documents AI usage across the SDLC as required by the submission guidelines.*
