# Phase 9: Service Catalog + Events / MongoDB CRUD - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Developers can register, view, and deregister services through the dashboard; every platform
action (platform started, service registered, service deregistered) writes to a TTL-bounded
events feed; launchpad gets its own in-cluster MongoDB (`mongo:7` manifests embedded in
`charts/launchpad/templates/mongodb/`, database name `launchpad`) — which also flips the
launchpad pod from NotReady to Ready (closing the D-08 consequence accepted in Phase 8).

In scope: CAT-01..05, FEED-01..03, DEP-03. Out of scope: Makefile `up-all` + smoke targets
(DEP-04/05 → Phase 10), any real deployment pipeline behind the onboard form (later PRD),
editing a registration after onboard (not in requirements).

</domain>

<decisions>
## Implementation Decisions

### Registration form fields (CAT-02)
- **D-01:** Lean IDP field set: `name`* (unique slug), `repo_url`*, `owner`*, `description`
  (optional), `environment` (dropdown: dev/staging/prod). * = required.
- **D-02:** Format validation (CAT-03): `name` must match `^[a-z0-9-]{2,40}$` and be unique
  in MongoDB (unique index on `name`); `repo_url` must parse as an http(s) URL; `owner`
  non-empty with a max length. Invalid input never writes a document.
- **D-03:** The slug is the service's URL identity: detail page at `/catalog/<name>`
  (human-readable, demo-friendly). Requires the unique index on `name`.

### CSRF + validation mechanics (CAT-03)
- **D-04:** Use **Flask-WTF** (new pinned dependency) — `CSRFProtect` extension + `FlaskForm`
  classes for field validators and error collection. No hand-rolled CSRF.
- **D-05:** `SECRET_KEY` is supplied in-cluster via the existing launchpad chart Secret
  (alongside `MONGO_URI`; values.yaml placeholder, local-dev only, never a real credential —
  T-08-02 pattern, secretKeyRef only), with a dev default in app config outside the cluster.
- **D-06:** Invalid form → classic **full-page re-render** with inline field-level errors and
  previously-entered values preserved. No htmx form choreography (avoids the CSRF-token-in-
  swapped-fragment footgun).

### Catalog + detail presentation (CAT-01, CAT-04, CAT-05)
- **D-07:** Catalog list is a Pico-styled `<table>`: name (link to detail), environment,
  owner, registered-at. Consistent with the kubectl-style tables on /diagnostics.
- **D-08:** Deregistration confirmation is a **server-rendered confirm page**:
  delete button on detail → `GET /catalog/<name>/delete` renders "Deregister <name>? This
  cannot be undone" with a CSRF-protected POST form + cancel link. Zero JS, no native
  `confirm()` (blocks browser automation), fully testable with the existing client fixture.
- **D-09:** Empty catalog shows a CTA empty state ("No services registered yet" + prominent
  "Onboard your first service" button). The detail page renders that service's related events
  by **reusing the same event-row partial** the /feed page uses — one template, two consumers.

### Events feed behavior (FEED-01..03)
- **D-10:** TTL index on `ts` with **7-day** expiry (`expireAfterSeconds=604800`), configurable
  via app config so smoke can verify expiry with a short TTL. TTL correctness is verified live
  via smoke only — mongomock cannot verify expiry timing (documented in conftest.py).
- **D-11:** /feed polls via the established visibility-guarded htmx pattern (D-04 lineage from
  Phases 6-8) every **15s** through a new `/partials/feed` fragment endpoint. Newest first.
- **D-12:** `platform_started` fires **once per process on first readiness** — emitted when the
  app factory has wired extensions AND Mongo is reachable, guarded by a per-process flag so
  gunicorn worker restarts and repeated `create_app()` calls in tests don't spam the feed.
  Event types: `platform_started`, `service_registered`, `service_deregistered` (FEED-02).

### Locked by ROADMAP success criteria (not re-decided here)
- `POST /catalog/new` persists, fires `service_registered`, redirects to catalog (SC #1)
- Deregistration removes the document and fires `service_deregistered` (SC #4)
- `mongo:7` manifests embedded in `charts/launchpad/templates/mongodb/`, database name
  `launchpad`; the field-guide-api chart is left untouched (SC #6 / DEP-03)
- `make test-launchpad` passes mongomock-backed (SC #5)

### Claude's Discretion
- Event document schema details (beyond `ts` + type + service name), feed page size cap,
  catalog sorting, environment badges, exact detail-page section layout, event icons.
- Mongo manifest specifics beyond the SC: mirror `charts/field-guide-api/templates/mongodb/`
  (deployment/pvc/secret/service) per established Phase 8 mirroring discipline.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec & requirements
- `.planning/ROADMAP.md` §"Phase 9: Service Catalog + Events / MongoDB CRUD" — goal + 6 success criteria (the locked contract)
- `.planning/REQUIREMENTS.md` — CAT-01..05, FEED-01..03, DEP-03 (full requirement text + traceability)

### MongoDB manifests analog (mirror this)
- `charts/field-guide-api/templates/mongodb/` — deployment.yaml, pvc.yaml, secret.yaml, service.yaml — the four-file analog for `charts/launchpad/templates/mongodb/` (database name `launchpad`)
- `charts/launchpad/templates/secret.yaml` — existing Secret carrying `MONGO_URI` placeholder (extend with `SECRET_KEY`, keep serverSelectionTimeoutMS=2000)

### Existing app patterns (reuse, do not rebuild)
- `apps/launchpad/app/extensions.py` + `app/__init__.py` — mongo singleton + app factory wiring (Phase 7)
- `apps/launchpad/app/routes/partials.py` — HX-Request fragment/full-page branching pattern (status-cards, cluster-state) for the new `/partials/feed`
- `apps/launchpad/app/routes/pages.py` — `/catalog` and `/feed` stub routes with stable names ("Phase 9 fills in real content")
- `apps/launchpad/app/templates/diagnostics.html` — visibility-guarded htmx polling trigger syntax to copy for the feed
- `apps/launchpad/tests/conftest.py` — mongomock-backed test harness; document the TTL limitation here (Phase 9 research flag)

### Prior phase context
- `.planning/phases/08-helm-chart-k8s-diagnostics/08-CONTEXT.md` — D-08 (readinessProbe consequence this phase resolves), D-05..07 chart conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Mongo singleton (`app/extensions.py`, Flask-PyMongo 3.0.1) — catalog/events collections hang off the same client
- Partials blueprint + HX-Request branching — `/partials/feed` follows status-cards/cluster-state exactly
- Pico CSS table styling already proven on /diagnostics tables
- `status-card--degraded/--ok` CSS modifiers exist for state badges if wanted

### Established Patterns
- Never-raise data helpers returning plain dicts (status.py, cluster_state.py) — event/catalog data access should follow
- Fixed generic error strings, never `str(exception)` in HTML (T-08-06 discipline)
- Module-attribute imports for monkeypatchable seams (`from app import k8s` lesson — plan-check BLOCKER 3; apply the same to any new service/event modules the tests patch)
- Many small lowercase conventional commits

### Integration Points
- `/catalog` and `/feed` page routes exist as stubs — fill templates, don't rename routes
- `charts/launchpad/values.yaml` `mongoUri` placeholder currently points nowhere — Phase 9's in-chart Mongo Service becomes the real target (pod flips to Ready per D-08 resolution)
- `sidebar` nav already links both pages (Phase 6)

</code_context>

<specifics>
## Specific Ideas

- The live-demo moment to protect: register a service in one tab, watch it appear in the
  polling feed — this is why D-11 chose 15s polling over render-on-load.
- Deregister flow must be screenshot-friendly and browser-automation-safe (no native dialogs).

</specifics>

<deferred>
## Deferred Ideas

- Editing a service registration after onboard (PATCH/edit form) — not in CAT-01..05; candidate
  for a later phase if the catalog grows.

</deferred>

---

*Phase: 9-Service Catalog + Events / MongoDB CRUD*
*Context gathered: 2026-07-12*
