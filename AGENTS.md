# AGENTS.md — volt-be

## Hard stops — read first

- Never commit `.env`. It is gitignored; it holds real secrets.
- Never edit `migrations/` files by hand — only `manage.py makemigrations` touches those.
- Never run `manage.py migrate` without confirming with the owner first.
- Never force-push any branch.
- Never commit secrets or credentials of any kind.
- Never use `pip install`; use `uv add` to add dependencies (ask first — see below).

## Known WIP — do not extend

`users/api.py` is an unfinished personal experiment with `django-bolt`. It is experimental code — do not extend it, import from it, or treat it as canonical in any way. All auth and API work must follow the DRF implementation in `users/views.py`. Leave the file in place — do not delete it.

---

## Package manager & Python

- **`uv`**, not pip. Lock file is `uv.lock`. Install everything: `uv sync --all-groups`.
- Python >= 3.12. Runtime: Django 6.x + **Django REST Framework** (DRF).

## Commands
```bash
uv sync --all-groups                          # install all deps incl. dev group
uv run python manage.py runserver             # dev server
uv run python manage.py makemigrations        # create migration (then ask before migrate)
uv run python manage.py migrate               # ask owner before running
uv run ruff check .                           # lint — manual only, not automatic
uv run ruff format .                          # format — manual only, not automatic

# Tests — Django app tests (require DB)
uv run python manage.py test users activities

# Tests — platform-client unit tests (no DB, pure pytest)
uv run pytest activities/services/platforms/tests/

# Run one pytest test
uv run pytest activities/services/platforms/tests/test_github.py::test_get_user_info_success

# Run one Django TestCase class
uv run python manage.py test activities.tests.PlatformAccountTest
```

> **Note:** ruff lint/format are not run automatically. IDE format-on-save handles formatting. Only run them manually when asked.

---

## Boundaries

### Always do
- Keep `# noqa: S106` on hardcoded test passwords — ruff bandit false positives.
- Use `django.utils.timezone.now()` or `datetime.fromtimestamp(..., tz=UTC)` — `USE_TZ = True`.
- Prefer `save(update_fields=[...])` and queryset `.update()` over full `.save()`.
- Wrap all data-mutation side effects in `transaction.atomic()`.
- Use DRF serializers for all API input validation and response formatting — no manually built dicts for API input/output.
- Scope business logic in the app's `services/` folder; keep views thin.
- Put shared utilities, base classes, and mixins in `common/` — not duplicated per app.

### Ask first
- Adding a new `uv` dependency.
- Adding a new Django app (`INSTALLED_APPS` + migration).
- Running `manage.py migrate` against any real database.
- Changing `CORS_ALLOWED_ORIGINS`, JWT lifetimes, or anything else in `volt/settings.py`.
- Running `ruff check` or `ruff format` as part of a task.

### Never do
- Edit migration files by hand.
- Use `pip install`.
- Return manually built dicts as API responses when a serializer should own that output.
- Introduce `print()` outside management commands or WIP views (ruff T20; use `logger.*`).
- Use timezone-unaware datetimes.

---

## Views — DRF style guide

The project uses **DRF**. Choose the view style that fits the endpoint's purpose:

**`generics.*` — use for standard CRUD on a model.** Reference: `PlatformListCreateView`, `PlatformUpdateDestroyView`, `GenerateRequestView`, `ActivitiesListView`, `MetricsRetrieveView` in `activities/views.py`.

**`APIView` — use for non-CRUD or multi-source responses.** Reference: `UserPlatformMetadataListView` in `activities/views.py` — assembles data from a service and a non-model serializer.

**`@api_view` — use for simple one-off endpoints.** Reference: all five views in `users/views.py` (`generate_otp`, `verify_otp`, `refresh_token_view`, `logout_view`, `complete_profile`).

---

## Serializers

- Use `ModelSerializer` for model-backed request/response shapes.
- Use `serializers.Serializer` (base class) for non-model inputs (e.g. `EmailOnlySerializer`, `OTPSerializer`) and non-model responses (e.g. `UserPlatformMetadataSerializer`).
- Cross-field validation goes in the serializer's `validate()` method, not in the view.

---

## API routing map

Full URL conf is in `volt/urls.py`. The two app confs are mounted with no prefix. Canonical source: `users/urls.py` and `activities/urls.py`.

**`users` app**

| Path | Method(s) | View | Purpose |
|---|---|---|---|
| `otp/generate/` | POST | `generate_otp` | Generate + email an OTP; creates an `OTPSessions` row |
| `otp/verify/` | POST | `verify_otp` | Verify OTP; creates/fetches `User`; returns access token + sets `HttpOnly` refresh cookie |
| `refresh/` | POST | `refresh_token_view` | Rotate refresh token from cookie; returns new access token |
| `logout/` | POST | `logout_view` | Blacklists refresh token; bumps `token_version`; deletes cookie |
| `profile/complete/` | POST | `complete_profile` | Set `username` on a newly-created user after OTP sign-up |

**`activities` app**

| Path | Method(s) | View | Purpose |
|---|---|---|---|
| `platforms/` | GET | `PlatformListCreateView` | List user's linked platform accounts |
| `platforms/` | POST | `PlatformListCreateView` | Add a new platform account |
| `platforms/<str:platform>/` | GET, PUT, PATCH | `PlatformUpdateDestroyView` | Retrieve or update a platform account |
| `platforms/<str:platform>/` | DELETE | `PlatformUpdateDestroyView` | Remove a linked platform account |
| `generate/` | POST | `GenerateRequestView` | Create a `GenerationRequest` and run a full platform sync (currently synchronous — see Celery section) |
| `activities/` | GET | `ActivitiesListView` | List activity rows; accepts `?platform=`, `?start_date=`, `?end_date=` query params |
| `metrics/` | GET | `MetricsRetrieveView` | Return `UserMetrics` + list of `GenerationRequest` metric snapshots |
| `platforms-metadata/` | GET | `UserPlatformMetadataListView` | Return per-platform stored metadata dict keyed by platform name |

**Schema / dev tools** (registered in `volt/urls.py`): `api/schema/`, `api/schema/swagger-ui/`, `api/schema/redoc/`.

---

## Error response format

For endpoints using `@api_view`, the current convention in `users/views.py` is:

- **Validation failure (400):** `{"error": "Validation failed", "details": serializer.errors}`
- **Auth / business failure (401/403):** `{"error": "<descriptive message>"}`
- **Success:** `{"message": "<descriptive message>", ...additional fields}`

Follow this shape for all new `@api_view` endpoints. Do not return a raw `str(e)` as the `error` value except for unexpected exceptions where no better message is available.

For endpoints using `generics.*` or `APIView`, DRF serialises validation errors automatically (field-keyed or `non_field_errors`). Do not manually override this with a custom shape — let DRF own it.

---

## Celery — background tasks

- **App definition:** `volt/celery.py` defines the Celery app; `volt/__init__.py` imports it so Django loads it on startup.
- **Auto-discovery:** `app.autodiscover_tasks()` is used. Any file named `tasks.py` inside an app in `INSTALLED_APPS` is auto-discovered — no manual registration needed.
- **Broker / result backend:** Redis. Configured via `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` env vars (see `volt/settings.py`). Default: `redis://localhost:6379/0`.
- **Serialisation:** JSON only (`CELERY_TASK_SERIALIZER = "json"`).
- **Where task files live:** one per app (or sub-package), named `tasks.py`. Current task file: `common/email/tasks.py` — `send_otp_email_task`.
- **How to define a new task:** use `@shared_task`. Reference: `common/email/tasks.py`.
- **How to call a task from a view or service:** use `.delay()`. Reference: `users/views.py` — `send_otp_email_task.delay(email, otp)`.
- **Celery Beat:** not configured. No periodic tasks exist yet. Do not add a `beat_schedule` without asking the owner first.
- **Known pending work:** `activities/views.py` (`GenerateRequestView`) has a `# TODO: move this to async (Celery)` comment — the full platform sync currently runs synchronously and blocks the HTTP request. Do not extend the synchronous path; ask the owner before moving it to a task.

---

## Project structure rules

### `common/` — shared cross-app code
`common/` exists. Currently contains one module: `common/email/service.py` — which sends OTP email via Django's mail backend. Any utility needed by more than one app goes here, not duplicated.

### `services/` — business logic per app
Each app owns a `services/` folder. Keep views thin: views handle HTTP (deserialize input, serialize output, return `Response`). Services own all business logic, DB orchestration, and external API calls. Reference: `activities/services/` — `SyncService`, `MetricsService`, `ActivityService`, and per-platform clients under `activities/services/platforms/`.

### Platform clients
All platform clients return a uniform dict with `{"status": "success"|"error", ...}`. Use `SyncService._is_error_payload(data)` to check — do not re-implement. Network errors raise `PlatformNetworkError`/`PlatformTimeoutError` internally; they never bubble to callers as raw exceptions.

---

## Database schema

**`users` app** (`db_table` names in parentheses)

- **User** (`users`) — custom `AbstractBaseUser`. Fields: `id` (PK int), `email` (unique), `username` (unique), `token_version` (int, JWT invalidation), `is_active`, `is_staff`, `is_superuser`, `created_at`, `last_login`. No FK relations; this is the AUTH_USER_MODEL.
- **OTPSessions** (`otp_sessions`) — Fields: `id`, `email`, `otp` (bcrypt hash), `created_at`, `expires_at` (10 min TTL), `verified` (bool), `is_valid` (bool). No FK to User (email-keyed only).

**`activities` app**

- **PlatformAccount** (`platform_accounts`) — FK to `User`. Fields: `id`, `platform` (TextChoices: codechef/codeforces/leetcode/hackerrank/github), `username`, `metadata` (JSONField), `last_fetched` (datetime, nullable), `fetch_error` (text, nullable). Unique together: `(user, platform)`.
- **GenerationRequest** (`generation_requests`) — FK to `User`. Fields: `id`, `status` (pending/processing/completed/failed), `created_at`, `last_synced_at`, `error_message`, `svg_cache`, `gen_active_days`, `gen_longest_streak`, `gen_total_activities`.
- **Activity** (`activities`) — FK to `User`, FK to `GenerationRequest`. Fields: `id`, `platform`, `activity_date` (date), `activity_count` (int), `metadata` (JSONField, nullable). Unique together: `(user, platform, activity_date)`.
- **UserMetrics** (`user_metrics`) — OneToOne to `User`. Fields: `id`, `total_active_days`, `current_streak`, `longest_streak`, `total_activities`, `total_questions_solved`, `easy_questions_solved`, `medium_questions_solved`, `hard_questions_solved`, `total_contests`, `updated_at` (auto).

---

## GenerationRequest ↔ Activity relationship

- `Activity` holds a **non-nullable FK to `GenerationRequest`** (`on_delete=CASCADE`) in addition to its FK to `User`. The DB uniqueness constraint is `(user, platform, activity_date)` — `generation_request` is **not** part of the constraint.
- `ActivityService.bulk_save()` (`activities/services/activity_service.py`) uses `update_or_create` keyed on `(user, platform, activity_date)`. Duplicate rows cannot be created under normal single-sync flow — the unique constraint is respected and `update_or_create` handles it correctly.
- On a re-sync, existing `Activity` rows for a given `(user, platform, activity_date)` are **updated in place**, and their `generation_request` FK is reassigned to the new `GenerationRequest`. This means a re-sync effectively migrates activity rows to the new request.
- **Cascade risk:** deleting a `GenerationRequest` will cascade-delete all `Activity` rows pointing at it. Because rows are reassigned on each sync, deleting an old `GenerationRequest` is only safe after a successful re-sync has reassigned its rows. No code currently deletes `GenerationRequest` rows.
- See `activities/services/activity_service.py` and `activities/services/sync_service.py` (`_persist_activity_data`) for the full write path.

---

## Testing

- **Framework**: `django.test.TestCase` for anything touching models/views; plain `pytest` for pure-Python platform clients.
- **Auth in API tests**: create a `RefreshToken.for_user(user)` and call `client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")`.
- **Mocking**: use `unittest.mock.patch` / `patch.object`. Never make real network calls in tests.
- **Minimum a new test should cover**: happy path, a validation failure path, and auth enforcement (unauthenticated = 401/403).
- No coverage minimum is set; no CI pipeline exists yet.

> **Note:** Test coverage is not yet mature. Revisit and tighten this section once coverage is established.

---

## Environment variables

- All secrets and config live in `.env`, loaded via `python-dotenv` in `settings.py`.
- Never hardcode a secret, API key, or credential in code — always read it from `.env` via `os.getenv`.
- If a task requires a new environment variable, add it to `.env.example` (create one if it doesn't exist) with a placeholder value — never a real one — and ask the owner to set the real value.
- Never print, log, or commit the contents of `.env`.

---

## Git conventions
- Commit prefix style from history: `feat:`, `Add:`, `Refactor:`, `update:`, `remove:`.
- No branch naming convention or PR template found in repo. *(Ask owner — guessed: `feat/`, `fix/`, `refactor/` prefixes.)*
- No CI pipeline configured.

---

## TODOs — owner confirmation needed

- **Sync race condition:** if `generate/` is ever moved to a Celery task (see TODO in `activities/views.py`) and two sync jobs for the same user run concurrently, `update_or_create` on `Activity` could produce a PostgreSQL deadlock or `IntegrityError` on the `(user, platform, activity_date)` unique constraint. Options are `select_for_update` on the lookup or serialising per-user tasks via a dedicated queue. *(Needs owner confirmation before the async migration is implemented.)*
