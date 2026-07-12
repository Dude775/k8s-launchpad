# Phase 9: Service Catalog + Events / MongoDB CRUD - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 9-service-catalog-events-mongodb-crud
**Areas discussed:** Registration form fields, CSRF + validation approach, Catalog + detail presentation, Events feed behavior

---

## Registration form fields

| Option | Description | Selected |
|--------|-------------|----------|
| Lean IDP set | name* (unique slug), repo_url*, owner*, description, environment dropdown | ✓ |
| Minimal trio | name*, repo_url*, description | |
| Extended platform set | Lean set + team, runtime, health_url, tags | |

**User's choice:** Lean IDP set

| Option | Description | Selected |
|--------|-------------|----------|
| Format-validated | slug pattern + uniqueness; http(s) URL parse; owner max length | ✓ |
| Presence-only | required fields just non-empty | |
| Strict + normalized | format rules + normalization + duplicate-URL detection | |

**User's choice:** Format-validated

| Option | Description | Selected |
|--------|-------------|----------|
| Slug in URL | /catalog/my-api, unique index on name | ✓ |
| ObjectId in URL | /catalog/665f1c... | |

**User's choice:** Slug in URL

---

## CSRF + validation approach

| Option | Description | Selected |
|--------|-------------|----------|
| Flask-WTF | CSRFProtect + FlaskForm, one new pinned dependency | ✓ |
| Hand-rolled session token | zero new deps, hand-rolled validation | |
| You decide | planner picks | |

**User's choice:** Flask-WTF

| Option | Description | Selected |
|--------|-------------|----------|
| Chart Secret + dev default | SECRET_KEY joins MONGO_URI in chart Secret; dev fallback locally | ✓ |
| Generated at deploy time | helm randAlphaNum per install (rotates on upgrade) | |
| Env/.env only | out of chart entirely | |

**User's choice:** Chart Secret + dev default

| Option | Description | Selected |
|--------|-------------|----------|
| Full-page re-render | classic POST re-render, inline errors, preserved input | ✓ |
| htmx partial swap | hx-post form fragment swap (CSRF-in-fragment footgun) | |
| You decide | planner picks | |

**User's choice:** Full-page re-render

---

## Catalog + detail presentation

| Option | Description | Selected |
|--------|-------------|----------|
| Table | Pico-styled table: name, environment, owner, registered-at | ✓ |
| Cards grid | status-card style tiles | |
| You decide | planner picks | |

**User's choice:** Table

| Option | Description | Selected |
|--------|-------------|----------|
| Confirm page | server-rendered GET /catalog/<name>/delete + CSRF POST + cancel | ✓ |
| htmx inline two-step | button swaps to confirm/cancel pair | |
| hx-confirm attribute | native confirm() — ruled out (blocks browser automation) | |

**User's choice:** Confirm page

| Option | Description | Selected |
|--------|-------------|----------|
| CTA empty state + reuse feed rows | onboard CTA; shared event-row partial | ✓ |
| Plain empty text + custom detail list | minimal empty line, bespoke detail markup | |
| You decide | planner picks | |

**User's choice:** CTA empty state + reuse feed rows

---

## Events feed behavior

| Option | Description | Selected |
|--------|-------------|----------|
| 7 days | expireAfterSeconds=604800, configurable for smoke | ✓ |
| 24 hours | tighter, risks empty feed next day | |
| 1 hour | quick to verify, empty feed in real demos | |

**User's choice:** 7 days

| Option | Description | Selected |
|--------|-------------|----------|
| Poll every 15s | visibility-guarded htmx via /partials/feed | ✓ |
| Render on load only | refresh to see new events | |
| You decide | planner picks | |

**User's choice:** Poll every 15s

| Option | Description | Selected |
|--------|-------------|----------|
| First readiness after boot | once per process, Mongo reachable, per-process guard | ✓ |
| Every create_app() call | noisy — tests/worker restarts spam feed | |
| Deployment-event only | written by smoke, not runtime | |

**User's choice:** First readiness after boot

---

## Claude's Discretion

- Event document schema details (beyond ts + type + service name)
- Feed page size cap, catalog sorting, environment badges
- Detail-page section layout, event icons
- Mongo manifest specifics beyond SC #6 (mirror field-guide-api's four files)

## Deferred Ideas

- Editing a service registration after onboard (PATCH/edit form) — future phase candidate
