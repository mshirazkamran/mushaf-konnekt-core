![Mushaf Konnekt Logo](logo/MushafKonnektLogo.png)

# Mushaf Konnekt Backend

Backend service for the **Mushaf Konnekt** app. This service handles Quran.Foundation OAuth, proxies user APIs for Bookmarks/Notes/Collections, and serves static content databases to the Flutter client.

## Concept: what this backend does
Mushaf Konnekt connects readers with the Qur’an in a fast, offline-friendly way. The Flutter app talks only to this backend, and the backend does three main jobs:

1. **Secure access to user data**
   It handles OAuth with Quran.Foundation, stores a short-lived session token for the Flutter app, and keeps access tokens refreshed. This lets users manage bookmarks, notes, and collections safely without exposing QF tokens directly to the client.

2. **Proxying user APIs**
   Every bookmark/note/collection request from Flutter is forwarded to Quran.Foundation with the correct `x-auth-token` and `x-client-id`. The backend returns QF responses unchanged so the app behaves exactly like the upstream API.

3. **Serving offline content**
   It generates SQLite databases for Qur’an content (verses, translations, footnotes) and serves them as static files so the app can download and use them offline.

In short: **Flutter → this backend → Quran.Foundation**, plus **static content delivery** for offline use.

**Portfolio:** https://mshiraz.tech

---

## What this backend does
- Authenticates users via Quran.Foundation OAuth.
- Proxies user APIs (Bookmarks, Notes, Collections) to Quran.Foundation and returns responses unchanged.
- Serves static content files from `/qf-proxy/content/` (backed by `src/static`).
- Generates SQLite content databases (via scripts) stored under `src/locked`.

---

## Content APIs used
This backend integrates with Quran.Foundation APIs:
- **OAuth (Prelive/Prod)** for token exchange and refresh
- **User APIs** for:
  - Bookmarks
  - Notes
  - Collections
- **Content APIs** for generating local SQLite databases (chapters, verses, translations, footnotes)

Configurable via environment variables:
- `QF_AUTH_BASE_URL`
- `QF_API_BASE_URL`
- `QF_CLIENT_ID_PRELIVE`, `QF_CLIENT_SECRET_PRELIVE`
- `CLIENT_ID_PROD`, `CLIENT_SECRET_PROD`
- `PROD_API_ENDPOINT`, `PROD_AUTH_ENDPOINT`

---

## Project structure
```
src/
  main.py                 # FastAPI app entrypoint
  routers/
    auth.py               # OAuth exchange + refresh
    user_api.py           # /qf-proxy endpoints (bookmarks, notes, collections)
    content.py            # /qf-proxy/content static file serving
  services/
    qf_oauth.py            # Token exchange/refresh helpers
  repository/
    database.py            # DB session + table creation
    models.py              # SQLModel User model
  scripts/
    main_database_refresher.py
    footnotes_database_refresher.py
  static/                  # Static files served to Flutter
  locked/                  # Generated SQLite databases
```

---

## Proxy endpoints (Flutter should call these)
Base URL: `http://<host>:8000/qf-proxy`

- Bookmarks: `GET/POST /bookmarks`, `DELETE /bookmarks/{id}`, `GET /bookmarks/collections`
- Notes: `GET/POST /notes`, `GET /notes/{id}`, `PATCH/PUT /notes/{id}`, `DELETE /notes/{id}`, `GET /notes/by-verse/{verseKey}`
- Collections: `GET /collections`, `GET /collections/all`, `GET /collections/{id}`, `POST /collections`, `PUT /collections/{id}`,
  `POST /collections/{id}/bookmarks`, `DELETE /collections/{id}/bookmarks`, `DELETE /collections/{id}/bookmarks/{bookmarkId}`
- Static content: `GET /content/` and `GET /content/{path}`

All proxy responses are returned to Flutter unchanged (status code + JSON body).

---

## Coding practices followed
- **Separation of concerns**: routers, services, and repository layers are separated.
- **Token safety**: refresh tokens are used to update access tokens before proxying.
- **Minimal proxying**: request bodies, query params, and JSON responses are forwarded as-is.
- **Defensive checks**: required env vars validated; token refresh is retried on QF invalid_token errors.
- **Low surprise**: no hidden background jobs; scripts are explicit and reproducible.

---

## Running locally
```bash
python -m src.main
```

---

## License
Private project for Mushaf Konnekt.
