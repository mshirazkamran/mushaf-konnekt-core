# Mushaf Konnekt Backend Context

A FastAPI backend implementing OAuth2/OIDC token management for the Quran Foundation User APIs, backed by a PostgreSQL database.

## Architecture
- **Framework**: FastAPI (async).
- **Database**: PostgreSQL 18 (via Docker Compose), accessed via SQLModel and psycopg.
- **Dependency Management**: `uv`.

## Core Components
- `src/main.py`: Entrypoint. Initializes the database on startup and mounts routers.
- `src/repository/database.py`: SQLModel engine and DB session dependency.
- `src/repository/models.py`: Defines the `User` table (primary key: `sub`) storing tokens, expiration timestamps, and user profile data.
- `src/services/qf_oauth.py`: Internal services utilizing `httpx` and `pyjwt` to interact securely with the Quran Foundation authorization server.
- `src/routers/auth.py`:
  - `POST /auth/exchange`: Validates the `code` and `code_verifier` (PKCE) received from the Flutter client, creates/updates the User, and returns the session state.
  - `POST /auth/refresh`: Allows manual refreshing of access tokens via the stored refresh token.
- `src/routers/user_api.py`: Exposes a proxy router (`/qf-proxy/bookmarks`) acting as middleware between the client and QF User APIs. It auto-refreshes the user's `access_token` if it's within 60 seconds of expiring before forwarding requests.

## Flow Summary
1. Frontend (Flutter) generates auth URLs and executes the login callback locally.
2. Frontend sends the `authorization_code` and `code_verifier` to the `/auth/exchange` endpoint.
3. Backend exchanges these securely for an `access_token` and `id_token` using the hidden `QF_CLIENT_SECRET`.
4. Backend parses OpenID info from the `id_token` and persists the tokens in PostgreSQL.
5. All future QF API calls are proxied through the backend which manages token lifecycles proactively.
