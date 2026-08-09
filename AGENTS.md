# AGENTS.md — volt-be

## Hard stops — read first

- Never commit `.env`. It is gitignored; it holds real secrets.
- Never edit `migrations/` files by hand — only `manage.py makemigrations` touches those.
- Never run `manage.py migrate` without confirming with the owner first.
- Never force-push any branch.
- Never commit secrets or credentials of any kind.
- Never use `pip install`; use `uv add` to add dependencies (ask first — see below).

## Known WIP — do not extend

`users/api.py` exists purely as a personal experiment with `django-bolt`. It is **not** the pattern to follow or build on. All auth and API work must use the DRF implementation in `users/views.py`. Do not import from, duplicate, or treat `users/api.py` as canonical until explicitly told otherwise. Leave the file in place — do not delete it.

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

**`generics.*` — use for standard CRUD on a model**
**`APIView` — use for non-CRUD or multi-source responses**:
**`@api_view` — use for simple one-off endpoints** (current pattern in `users/views.py`):
---

## Serializers

- Use `ModelSerializer` for model-backed request/response shapes.
- Use `serializers.Serializer` (base class) for non-model inputs (e.g. `EmailOnlySerializer`, `OTPSerializer`) and non-model responses (e.g. `UserPlatformMetadataSerializer`).
- Cross-field validation goes in the serializer's `validate()` method, not in the view.

---

## Project structure rules

### `common/` — shared cross-app code
`common/` exists. Currently contains one module: `common/email/service.py` — `EmailService`, which sends OTP email via Django's mail backend. Any utility needed by more than one app goes here, not duplicated.

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
