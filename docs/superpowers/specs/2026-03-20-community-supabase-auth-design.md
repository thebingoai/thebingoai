# Community Edition: Supabase Auth + Database

## Context

Bingo currently uses a custom SSO service (`sso.thelead.io`) for authentication. This is being designated as the **enterprise edition**. A **community edition** is needed that uses Supabase Cloud for both authentication and database, making self-hosting simpler for community users.

The two editions will live in **separate branches/repos** — the community branch will not contain enterprise SSO code.

## Decisions

- **Auth provider**: Supabase Auth (GoTrue) via `@supabase/supabase-js` on frontend, local JWT verification on backend
- **Auth methods**: Email/password + Google OAuth
- **Database**: Supabase Cloud Postgres (replaces Docker-hosted Postgres)
- **Supabase hosting**: Supabase Cloud (supabase.com), not self-hosted
- **Code split**: Separate branches — community is default, enterprise SSO in separate branch/repo

## Architecture

### Backend: JWT Verification (replaces SSO HTTP calls)

The current flow makes an HTTP call to `sso.thelead.io/api/v1/auth/me` on every request (cached in Redis DB 3). Supabase issues standard JWTs that can be verified locally with the project's JWT secret — no network call, no Redis cache needed.

**New file `backend/services/supabase_auth.py`** (~30 lines):
```python
import jwt  # PyJWT
from pydantic import BaseModel
from backend.config import settings

class SupabaseUser(BaseModel):
    id: str        # sub claim (Supabase auth user UUID)
    email: str
    is_active: bool = True
    is_verified: bool = False

def verify_supabase_jwt(access_token: str) -> SupabaseUser | None:
    try:
        payload = jwt.decode(
            access_token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return SupabaseUser(
            id=payload["sub"],
            email=payload.get("email", ""),
            is_active=True,
            is_verified=payload.get("email_confirmed_at") is not None,
        )
    except jwt.PyJWTError:
        return None
```

**Updated `backend/auth/dependencies.py`**:
- Import `verify_supabase_jwt` instead of `validate_token`
- Change `sso_user = await validate_token(token)` → `sso_user = verify_supabase_jwt(token)` (sync, no await needed)
- Change `auth_provider="sso"` → `auth_provider="supabase"` in **both** user creation (line 84) **and** email-linking (line 68)
- User lookup stays the same: `sso_id` column stores Supabase auth user UUID
- `get_current_user() -> User` interface is completely unchanged — 20+ API files need zero changes

**Updated `backend/api/websocket.py`**:
- The WebSocket endpoint has its own `_get_user_from_token()` that directly imports `sso_client.validate_token` (bypasses `dependencies.py`)
- Must be rewritten to call `verify_supabase_jwt()` instead
- Also update `auth_provider="sso"` → `"supabase"` in the websocket's email-linking path

**Updated `backend/api/auth.py`**:
- `GET /auth/config` (renamed from `/auth/sso/config`) — returns `{ supabase_url, supabase_anon_key }`
- `GET /auth/me` — unchanged
- `POST /auth/logout` — simplified, just clears state (Supabase handles token invalidation client-side)

**Deleted files**:
- `backend/services/sso_client.py` — replaced by `supabase_auth.py`
- `backend/api/sso_webhooks.py` — Supabase handles auth events internally

**Updated `backend/config.py`**:
Remove:
```python
sso_base_url, sso_publishable_key, sso_secret_key,
sso_token_cache_ttl, sso_webhook_secret, sso_redis_url
```
Add:
```python
supabase_url: str = ""              # https://xxx.supabase.co
supabase_anon_key: str = ""         # public anon key
supabase_jwt_secret: str = ""       # JWT secret for backend verification
supabase_service_role_key: str = "" # for admin operations (optional)
database_url_direct: str = ""       # Direct Postgres URL (port 5432) for Alembic migrations
```
Add a `field_validator` on `supabase_jwt_secret` to reject empty strings (prevents trivial token forgery).

Change `enable_governance` default from `True` to `False` (community users won't have org/team tables seeded).

**Updated `backend/schemas/auth.py`**:
- Replace `SSOConfigResponse` with `AuthConfigResponse(supabase_url, supabase_anon_key)`
- Remove `SSOLogoutRequest` (no refresh token blacklisting needed)
- Keep `TokenResponse`

### Database: Supabase Cloud Postgres

Supabase provides a standard Postgres instance. SQLAlchemy connects to it with just a URL change.

**Connection string**: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres`

Changes:
- `DATABASE_URL` env var points to Supabase Postgres (uses PgBouncer on port 6543)
- Add `DATABASE_URL_DIRECT` for Alembic migrations (port 5432, bypasses PgBouncer — PgBouncer transaction mode doesn't support DDL)
- Remove `postgres` service from **both** `docker/local/docker-compose.yml` and `docker/production/docker-compose.yml`
- `backend/database/session.py` — no code changes needed
- `alembic/env.py` — update to use `settings.database_url_direct or settings.database_url`:
  ```python
  url = settings.database_url_direct or settings.database_url
  config.set_main_option('sqlalchemy.url', url)
  ```

**Note**: Supabase has its own `auth.users` table in the `auth` schema. Bingo's `users` table in `public` schema is separate. The `sso_id` column links them via the Supabase auth UUID.

### Frontend: Supabase JS Client

**Install**: `@supabase/supabase-js`

**New `frontend/composables/useSupabase.ts`**:
```typescript
import { createClient } from '@supabase/supabase-js'

let _client: ReturnType<typeof createClient> | null = null

export const useSupabase = () => {
  if (!_client) {
    const config = useRuntimeConfig()
    _client = createClient(config.public.supabaseUrl, config.public.supabaseAnonKey)
  }
  return _client
}
```

**Rewritten `frontend/stores/auth.ts`**:
- State: remove `ssoConfig`, `refreshToken` (Supabase client manages tokens)
- `login()`: `supabase.auth.signInWithPassword({ email, password })`
- `register()`: `supabase.auth.signUp({ email, password })`
- `loginWithGoogle()`: `supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo } })`
- `refreshAccessToken()`: `supabase.auth.refreshSession()`
- `logout()`: `supabase.auth.signOut()`
- `onAuthStateChange` listener syncs Supabase session → store token
- `fetchUser()`: still calls `GET /api/auth/me` with Bearer token (backend validates JWT)

**Rewritten `frontend/plugins/sso-init.ts`** → `supabase-init.ts`:
- Initialize Supabase client
- Set up `onAuthStateChange` listener to sync session → auth store
- Session restoration is automatic (Supabase persists in localStorage under its own key)

**Updated `frontend/middleware/auth.ts`**:
- Remove manual `localStorage.getItem('auth_token')` — Supabase manages its own storage key
- Read token from auth store only (populated by `onAuthStateChange` in the plugin)
- Ensure plugin runs before middleware to avoid false redirects to `/login`

**Updated `frontend/nuxt.config.ts`**:
- Remove `/sso-api/**` proxy (Supabase JS calls Supabase directly)
- Add runtime config: `supabaseUrl`, `supabaseAnonKey`

**Auth pages** — same UI, different store calls:
- `login.vue` — calls `authStore.login()` / `authStore.loginWithGoogle()`
- `register.vue` — calls `authStore.register()`
- `auth/verify.vue` — Supabase sends verification emails; page handles `?token_hash=&type=email`
- `auth/success.vue` — Supabase OAuth returns with hash fragments, handled by Supabase JS
- `auth/forgot-password.vue` — calls `supabase.auth.resetPasswordForEmail()`
- `auth/reset-password.vue` — calls `supabase.auth.updateUser({ password })`

**Updated `frontend/composables/useApi.ts`**:
- `fetchWithRefresh()`: on 401, call `supabase.auth.refreshSession()` instead of SSO refresh API
- Token injection unchanged (Bearer header from store)

### User Model Changes

`backend/models/user.py` — minimal changes:
- `sso_id` column: **keep the name** (avoid migration churn). Stores Supabase auth user UUID (`sub` claim)
- `auth_provider` default: `"supabase"` instead of `"sso"`
- All relationships unchanged

### Docker Compose Changes

Remove:
- `postgres` service (replaced by Supabase Cloud)
- `SSO_*` environment variables

Update:
- `DATABASE_URL` → Supabase connection string
- `backend` service env: add `SUPABASE_*` vars, remove `SSO_*`

Keep:
- `redis` (still used for job cache DB 0, Celery broker DB 1, Celery results DB 2)
- `qdrant` (vector storage)
- `backend`, `celery-worker`

### Migration Path (Branch Split)

1. Create `community` branch from `dev`
2. Delete: `backend/services/sso_client.py`, `backend/api/sso_webhooks.py`
3. Create: `backend/services/supabase_auth.py`
4. Rewrite: `backend/auth/dependencies.py`, `backend/api/auth.py`, `backend/schemas/auth.py`
5. Update: `backend/config.py`, `docker-compose.yml`, `.env.example`
6. Frontend: install `@supabase/supabase-js`, create `useSupabase` composable
7. Rewrite: `frontend/stores/auth.ts`, `frontend/plugins/sso-init.ts` → `supabase-init.ts`
8. Update: `frontend/nuxt.config.ts`, auth pages
9. Add Alembic migration: update `auth_provider` default to `"supabase"`
10. Update requirements.txt: add `PyJWT`, remove unused SSO deps if any

## Files Changed

| Action | File | Notes |
|--------|------|-------|
| DELETE | `backend/services/sso_client.py` | SSO HTTP client + Redis cache |
| DELETE | `backend/api/sso_webhooks.py` | SSO webhook handler |
| CREATE | `backend/services/supabase_auth.py` | ~30-line JWT verification |
| CREATE | `frontend/composables/useSupabase.ts` | Supabase client composable |
| REWRITE | `backend/auth/dependencies.py` | Swap validate_token → verify_supabase_jwt |
| REWRITE | `backend/api/auth.py` | Supabase config endpoint |
| REWRITE | `backend/schemas/auth.py` | AuthConfigResponse |
| REWRITE | `frontend/stores/auth.ts` | Supabase JS auth flows |
| REWRITE | `frontend/plugins/sso-init.ts` | → `supabase-init.ts` |
| UPDATE | `backend/config.py` | Remove sso_*, add supabase_* |
| UPDATE | `frontend/nuxt.config.ts` | Remove /sso-api proxy, add supabase runtime config |
| UPDATE | `frontend/composables/useApi.ts` | Supabase token refresh on 401 |
| UPDATE | `frontend/pages/login.vue` | Use new store methods |
| UPDATE | `frontend/pages/register.vue` | Use new store methods |
| UPDATE | `frontend/pages/auth/*.vue` | Supabase verification/reset flows |
| UPDATE | `docker-compose.yml` | Remove postgres, update env vars |
| UPDATE | `requirements.txt` | Add PyJWT |
| UPDATE | `frontend/package.json` | Add @supabase/supabase-js |
| UPDATE | `backend/api/routes.py` | Remove sso_webhooks router |
| UPDATE | `backend/api/websocket.py` | Rewrite `_get_user_from_token` to use `verify_supabase_jwt` |
| UPDATE | `backend/scripts/validate_env.py` | Check `supabase_jwt_secret` instead of `sso_secret_key` |
| UPDATE | `alembic/env.py` | Use `database_url_direct` fallback for migrations |
| UPDATE | `frontend/middleware/auth.ts` | Remove manual localStorage read, rely on store |
| UPDATE | `docker/local/docker-compose.yml` | Remove postgres, update env vars |
| UPDATE | `docker/production/docker-compose.yml` | Remove postgres, update env vars |
| UPDATE | `tests/unit/backend/conftest.py` | Update `auth_provider="sso"` → `"supabase"` in fixtures |
| UPDATE | `tests/unit/backend/test_dashboards.py` | Update auth_provider in test data |
| UPDATE | `tests/unit/backend/test_dashboard_schedule.py` | Update auth_provider in test data |
| UPDATE | `.env.example` | Supabase config vars |

## Verification

1. **Backend JWT verification**: Write a test that creates a valid Supabase-style JWT, verifies it with `verify_supabase_jwt()`, and checks the returned user fields
2. **get_current_user integration**: Test that a request with a valid Supabase JWT creates a User record and returns it
3. **Frontend login flow**: Manual test — email/password login via Supabase, verify token is sent to backend, /auth/me returns user
4. **Google OAuth flow**: Manual test — click Google login, complete OAuth, verify redirect and token exchange
5. **Token refresh**: Let access token expire, verify automatic refresh works
6. **Database connectivity**: Run `alembic upgrade head` against Supabase Postgres, verify all tables created
7. **Existing API endpoints**: Verify any protected endpoint (e.g., GET /api/connections) works with Supabase JWT
