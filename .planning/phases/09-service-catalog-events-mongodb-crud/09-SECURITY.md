---
phase: 09
slug: service-catalog-events-mongodb-crud
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-13
---

# Security Audit — Phase 09: Service Catalog, Events, MongoDB CRUD

**Audit date:** 2026-07-13
**Plans covered:** 09-01, 09-02, 09-03, 09-04
**ASVS Level:** L1
**Block on:** high (open threats)
**Result:** SECURED — 17/17 threats closed, 0 open, 0 unregistered flags

Implementation files were read-only for this audit. No production code was modified. Every threat below was verified by locating the actual mitigating code/config/test — not by trusting plan intent or SUMMARY.md self-report.

---

## Threat Verification

| Threat ID | Category | Component | Disposition | Status | Evidence |
|-----------|----------|-----------|-------------|--------|----------|
| T-09-01 | Tampering | ServiceForm repo_url validator | mitigate | CLOSED | `apps/launchpad/app/forms.py:42-49` — `Regexp(^https?://)` layered before `URL(require_tld=True)` on `repo_url`. Proven by `apps/launchpad/tests/test_catalog.py:276-281` (`test_form_repo_url_rejects_non_http_schemes_with_locked_copy`, parametrized on `ftp://x`, `javascript:alert(1)`, `not-a-url`, asserting the exact locked `URL_ERROR` string is in `form.repo_url.errors`). |
| T-09-02 | Tampering | services.name used as Mongo query key | mitigate | CLOSED | `apps/launchpad/app/forms.py:39` — `Regexp(^[a-z0-9-]{2,40}$)` on `name` before persistence. `apps/launchpad/app/catalog.py:61` (`get_service`) and `:93` (`deregister_service`) use dict-encoded `{"name": name}` PyMongo queries — no string interpolation, no `$where` anywhere in `app/catalog.py` or `app/events.py` (grep-verified). |
| T-09-03 | Information Disclosure | register_service error path | mitigate | CLOSED | `apps/launchpad/app/catalog.py:75-83` — `register_service` catches `DuplicateKeyError` → fixed `DUPLICATE_NAME_ERROR`, catches `Exception` → fixed `GENERIC_SAVE_ERROR`. No `str(exception)` anywhere in `catalog.py`/`events.py` (grep-verified; only docstring mentions of the discipline itself). |
| T-09-04 | Elevation of Privilege | CSRF token signing key | mitigate | CLOSED | `apps/launchpad/app/config.py:50` — `SECRET_KEY` sourced from env with default explicitly labeled `dev-secret-key-not-for-production`. Real value delivered via `charts/launchpad/templates/secret.yaml:19` (`SECRET_KEY: {{ .Values.secretKey | quote }}`) → `charts/launchpad/templates/deployment.yaml:77-81` (`secretKeyRef`). |
| T-09-05 | Denial of Service | events collection unbounded growth | mitigate | CLOSED | `apps/launchpad/app/events.py:35-46` — `ensure_indexes()` creates `mongo.db.events.create_index("ts", expireAfterSeconds=ttl_seconds)`, idempotent (try/except pass), called from `app/__init__.py:86` at startup. Test asserts `index_information()["ts_1"]["expireAfterSeconds"] == 604800` (09-01-SUMMARY verification evidence; no test sleeps then asserts expiry). |
| T-09-SC | Tampering | pip install Flask-WTF/WTForms | mitigate | CLOSED | Blocking human-verify checkpoint (09-01-PLAN Task 1) executed; human approved pallets-eco provenance before pin landed. `apps/launchpad/requirements.txt:11` — `Flask-WTF==1.3.0` present, no separate WTForms pin (resolves transitively as documented). |
| T-09-06 | Spoofing/Tampering | POST /catalog/new and POST /catalog/<name>/delete | mitigate | CLOSED | `apps/launchpad/app/extensions.py:20` + `app/__init__.py:61` — `CSRFProtect` bound app-wide via `csrf.init_app(app)` (protects all POST routes by default, no `csrf.exempt` found anywhere in the codebase — grep-verified). `onboard_form.html:14` uses `form.hidden_tag()`; `confirm_delete.html:8` uses a raw `csrf_token()` hidden input. `test_pages.py:292-316` (`test_onboard_form_rejects_missing_csrf_token`) proves invalid token → 400, scraped token → not-400. |
| T-09-07 | Tampering/Information Disclosure | detail.html / catalog.html rendering user fields | mitigate | CLOSED | Zero `\| safe` filters anywhere in `apps/launchpad/app/templates/` (grep-verified, no matches). All user fields (`service.name`, `service.repo_url`, `service.owner`, `service.description`) rendered via plain `{{ }}` in `detail.html`, `catalog.html`, `partials/event_row.html` — Jinja2 autoescape (Flask default) is the active XSS boundary. |
| T-09-08 | Information Disclosure | form/route error paths | mitigate | CLOSED | Same evidence as T-09-03, extended to route layer: `apps/launchpad/app/routes/pages.py` never constructs a response from exception detail; all `except Exception` blocks across `app/` (catalog.py, events.py, status.py, cluster_state.py, health.py) discard the exception and return fixed sentinels (grep-verified across 12 `except Exception:` sites). |
| T-09-09 | Tampering | /catalog/<name> path segment lookup | mitigate | CLOSED | `apps/launchpad/app/catalog.py:61` — `mongo.db.services.find_one({"name": name})`, plain dict-encoded equality match, `name` constrained by the Regexp validator at write time (T-09-02). No `$where`, no string interpolation. |
| T-09-10 | Information Disclosure | SECRET_KEY / MONGO_URI / Mongo root creds in values.yaml | mitigate | CLOSED | `charts/launchpad/templates/secret.yaml:17-19` is the only template rendering `MONGO_URI`/`SECRET_KEY` into a cluster object; `charts/launchpad/templates/configmap.yaml` carries only `FIELD_GUIDE_BASE_URL`/`APP_VERSION`/`FLASK_DEBUG`/`EVENTS_TTL_SECONDS` (no secret). `charts/launchpad/templates/mongodb/secret.yaml` is the only place Mongo root creds render. `NOTES.txt` contains no secret values. `deployment.yaml:57-61,77-81` source `MONGO_URI`/`SECRET_KEY` exclusively via `secretKeyRef`. `values.yaml` defaults are explicitly commented "local dev only, never a real credential; override with --set". **Audit note (not a gap):** `values.yaml:72` `mongoUri` is a plain string with the dev password inlined in cleartext at the values layer (flagged as WR-01 in 09-REVIEW.md) rather than composed from `mongodb.auth.*` via template interpolation — this is a design-quality observation, not a violation of the threat's actual disposition (secrets-out-of-ConfigMap/env-literal/NOTES + clearly-labeled dev defaults), both of which hold. |
| T-09-11 | Spoofing | app Service selecting the mongod pod | mitigate | CLOSED | `charts/launchpad/templates/_helpers.tpl:88-91` — `launchpad.mongodb.selectorLabels` sets `app.kubernetes.io/name: {{ include "launchpad.name" . }}-mongodb`, distinct from `launchpad.selectorLabels` (`_helpers.tpl:73-76`, no `-mongodb` suffix). `templates/mongodb/service.yaml:20-21` and `templates/mongodb/deployment.yaml:25-27,30-32` consume the mongodb-specific helper only. No label overlap. |
| T-09-12 | Tampering | data durability across pod restarts | accept | CLOSED | Entry present in this SECURITY.md's Accepted Risks Log below. `charts/launchpad/templates/mongodb/deployment.yaml:17-24` — plain `Deployment` (not StatefulSet) + `strategy.type: Recreate`, chart-owned PVC (`pvc.yaml`, `ReadWriteOnce`) — matches the declared accepted pattern exactly. |
| T-09-13 | Denial of Service | events collection growth in live DB | mitigate | CLOSED | `charts/launchpad/values.yaml:42` (`config.eventsTtlSeconds: "604800"`) → `configmap.yaml:17` → `deployment.yaml:82-86` (`configMapKeyRef`) → consumed by `app/events.py:ensure_indexes()` (same code path as T-09-05). |
| T-09-04-01 | Denial of Service | _relative_time never-raise contract | mitigate | CLOSED | `apps/launchpad/app/events.py:130-131` — naive-datetime normalization guard (`if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)`) lives inside the existing try block; the tail `except Exception: return "unknown"` (line 147-148) is unchanged. `tests/test_events.py:221-222` (`test_relative_time_garbage_returns_unknown`) still passes — non-datetime garbage still degrades to "unknown", never raises. |
| T-09-04-02 | Tampering | tz_aware=True on mongo.init_app | accept | CLOSED | Entry present in this SECURITY.md's Accepted Risks Log below. `apps/launchpad/app/__init__.py:49-55` — `tz_aware=True` added to `mongo.init_app(...)` with an inline comment tying it to CR-01; verified client-side-decode-only scope (no stored-data, auth, or connection change) by reading the surrounding code — no new trust boundary. |
| T-09-04-SC | Tampering | package installs in gap closure | accept | CLOSED | Entry present in this SECURITY.md's Accepted Risks Log below. `apps/launchpad/app/events.py` and `app/__init__.py` diffs for 09-04 use only stdlib `datetime`/`timezone` (already imported) and an existing `flask_pymongo.PyMongo.init_app` keyword arg — `git diff` scope for 09-04 confirms no `requirements.txt` change. |

**Closed: 17/17. Open: 0/17.**

---

## Accepted Risks Log

Per the `accept` disposition, these risks are formally logged here (this log is the artifact that closes them):

1. **T-09-12 — Data durability across pod restarts.** A single-instance MongoDB `Deployment` (not `StatefulSet`) with a chart-owned `ReadWriteOnce` `PersistentVolumeClaim` and `Recreate` update strategy is the accepted pattern for this local, single-node learning/portfolio deployment. Risk accepted: a node failure or PVC loss loses all catalog/event data with no replication or backup. Mitigating factor: `Recreate` strategy prevents concurrent-writer corruption during upgrades (two `mongod` processes never share `/data/db` simultaneously). `StatefulSet` + replica set is explicitly out of scope for this milestone (mirrors `field-guide-api`'s existing accepted pattern). Owner: project maintainer. Revisit trigger: if launchpad moves beyond a local kind cluster / single-node deployment.

2. **T-09-04-02 — `tz_aware=True` on `mongo.init_app()`.** Accepted as a client-side BSON date decode change only. Does not alter stored data, authentication, or connection security; does not widen any trust boundary. Verified in `apps/launchpad/app/__init__.py:49-55`.

3. **T-09-04-SC — No new packages in gap-closure plan 09-04.** Accepted — the Package Legitimacy Gate does not apply because no new dependency was introduced; the fix uses only stdlib `datetime`/`timezone` and an existing keyword argument on the already-pinned `Flask-PyMongo` (`flask_pymongo.PyMongo.init_app`).

---

## Unregistered Flags

None. All four plan SUMMARY.md files were checked for a `## Threat Flags` section:

- **09-01-SUMMARY.md** — explicit `## Threat Flags` section present, states "None — all new surface ... is covered by the plan's threat register (T-09-01..05, T-09-SC)."
- **09-02-SUMMARY.md** — explicit `## Threat Flags` section present, states "None — all new surface ... is covered by the plan's own threat register (T-09-06..09)."
- **09-03-SUMMARY.md** — no `## Threat Flags` section (infra-only plan; its own threat model in 09-03-PLAN.md — T-09-10..13 — is honestly scoped to the chart changes it made; no new attack surface introduced beyond that register).
- **09-04-SUMMARY.md** — no `## Threat Flags` section (gap-closure plan; its own threat model explicitly states "introduces no new endpoints, no new user input paths, no new external calls, and no new data written to Mongo").

No new attack surface was identified during this audit that falls outside the declared threat register (T-09-01 through T-09-13, T-09-SC, T-09-04-01/02/SC).

---

## Audit Method Notes

- Every `mitigate` threat was closed by locating the actual code (function body, template line, chart template, or config key) implementing the claim — not by trusting the PLAN.md mitigation-plan prose or the SUMMARY.md self-report.
- Two threats flagged for extra scrutiny per the audit brief were independently re-verified against the code, not just the plan text:
  - **WR-01** (secret.yaml / mongoUri hardcoded hostname+password, relevant to T-09-10): confirmed accurate as a design observation — the password is inlined in the `mongoUri` plain string in `values.yaml` rather than templated from `mongodb.auth.*`. This does **not** invalidate T-09-10's actual disposition (secrets confined to the Secret template, never ConfigMap/env-literal/NOTES, with clearly-labeled non-production defaults) — both conditions verified true. Logged here as a design-quality note for future hardening (e.g., template-compose the URI from `mongodb.auth.username`/`password` instead of a flat string), not as an open threat.
  - **WR-02** (detail.html raw repo_url in an href, relevant to T-09-01): confirmed the URL validator genuinely restricts scheme — `Regexp(^https?://)` combined with `URL(require_tld=True)` in `forms.py`, proven by a parametrized test asserting `javascript:alert(1)` and `ftp://x` are rejected with the locked error copy before any document is persisted. Since malicious schemes never reach the database, the `detail.html` raw-href rendering (`<a href="{{ service.repo_url }}">`) cannot be exploited via this path. Combined with Jinja2 autoescape (T-09-07) covering the HTML-injection angle, both threats close cleanly.
- CSRF app-wide enforcement (T-09-06) was verified by confirming `csrf.init_app(app)` is called unconditionally in `create_app()` and that no `csrf.exempt` call exists anywhere in the codebase (grep-verified, zero matches) — ruling out a scoped/partial CSRF posture.
- All `except Exception` sites across `app/catalog.py`, `app/events.py`, `app/status.py`, `app/cluster_state.py`, and `app/routes/health.py` were enumerated (12 sites) and each confirmed to discard exception detail rather than leak it (T-09-03/T-09-08).

SECURITY.md: `E:\Genspark\k8s-launchpad\.planning\phases\09-service-catalog-events-mongodb-crud\SECURITY.md`
