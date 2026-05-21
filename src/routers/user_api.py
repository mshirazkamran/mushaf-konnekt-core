import os
import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from src.repository.database import get_session
from src.repository.models import User
from src.services.qf_oauth import refresh_access_token

router = APIRouter(prefix="/qf-proxy", tags=["qf-proxy"])

QF_API_BASE_URL = os.environ.get(
    "QF_API_BASE_URL", "https://apis-prelive.quran.foundation"
)
QF_CLIENT_ID = os.environ.get("QF_CLIENT_ID_PROD")


def _get_user_from_authorization(authorization: str, session: Session) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    session_token = authorization.split(" ")[1]
    user = session.exec(select(User).where(User.session_token == session_token)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not QF_CLIENT_ID:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")

    return user


async def _refresh_if_needed(user: User, session: Session, force: bool = False) -> None:
    should_refresh = force or (
        user.expires_at is not None and time.time() > user.expires_at - 60
    )
    if not should_refresh:
        return

    if not user.refresh_token:
        raise HTTPException(
            status_code=401,
            detail="Access token expired and no refresh token available",
        )
    try:
        tokens = await refresh_access_token(user.refresh_token)
        user.access_token = tokens.access_token
        user.expires_at = int(time.time()) + tokens.expires_in
        if tokens.refresh_token:
            user.refresh_token = tokens.refresh_token
        session.commit()
    except Exception as e:
        raise HTTPException(
            status_code=401, detail=f"Failed to refresh access token: {e}"
        )


def _qf_headers(user: User) -> dict:
    return {
        "x-auth-token": user.access_token,
        "x-client-id": QF_CLIENT_ID,
    }


def _is_expired_or_inactive_token_error(response: httpx.Response) -> bool:
    if response.status_code not in (401, 403):
        return False

    body = response.text.lower()
    return (
        "expired or inactive" in body
        or "invalid_token" in body
        or "access token is expired" in body
        or "access token" in body
        and "expired" in body
    )


async def _forward_request(
    method: str,
    path: str,
    user: User,
    session: Session,
    request: Request | None = None,
    params: dict | None = None,
) -> Response | dict | list:
    json_body = None if request is None else await request.json()

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{QF_API_BASE_URL}{path}",
            headers=_qf_headers(user),
            params=params,
            json=json_body,
        )

        if _is_expired_or_inactive_token_error(response):
            await _refresh_if_needed(user, session, force=True)
            response = await client.request(
                method,
                f"{QF_API_BASE_URL}{path}",
                headers=_qf_headers(user),
                params=params,
                json=json_body,
            )

    if response.status_code == 204:
        return Response(status_code=204)

    if response.status_code >= 400:
        print(f"\n\nQFF ERROR: {response.text}\n\n")
        raise HTTPException(
            status_code=response.status_code, detail=f"QF API Error: {response.text}"
        )

    if response.headers.get("content-type", "").startswith("application/json"):
        return JSONResponse(content=response.json(), status_code=response.status_code)

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get("content-type"),
    )


@router.get("/bookmarks")
async def get_bookmarks(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", "/auth/v1/bookmarks", user, session, params=params
    )


@router.post("/bookmarks")
async def add_bookmark(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "POST", "/auth/v1/bookmarks", user, session, request=request
    )


@router.delete("/bookmarks/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "DELETE", f"/auth/v1/bookmarks/{bookmark_id}", user, session
    )


@router.get("/bookmarks/collections")
async def get_bookmark_collections(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", "/auth/v1/bookmarks/collections", user, session, params=params
    )


@router.get("/notes")
async def get_notes(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request("GET", "/auth/v1/notes", user, session, params=params)


@router.get("/notes/by-verse/{verse_key}")
async def get_notes_by_verse(
    verse_key: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", f"/auth/v1/notes/by-verse/{verse_key}", user, session, params=params
    )


@router.get("/notes/{note_id}")
async def get_note_by_id(
    note_id: str,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request("GET", f"/auth/v1/notes/{note_id}", user, session)


@router.post("/notes")
async def add_note(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "POST", "/auth/v1/notes", user, session, request=request
    )


@router.put("/notes/{note_id}")
async def update_note(
    note_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "PUT", f"/auth/v1/notes/{note_id}", user, session, request=request
    )


@router.patch("/notes/{note_id}")
async def patch_note(
    note_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "PATCH", f"/auth/v1/notes/{note_id}", user, session, request=request
    )


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request("DELETE", f"/auth/v1/notes/{note_id}", user, session)


@router.get("/collections")
async def get_collections(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", "/auth/v1/collections", user, session, params=params
    )


@router.get("/collections/all")
async def get_all_collections_with_resources(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", "/auth/v1/collections/all", user, session, params=params
    )


@router.get("/collections/{collection_id}")
async def get_collection_by_id(
    collection_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    params = dict(request.query_params)
    return await _forward_request(
        "GET", f"/auth/v1/collections/{collection_id}", user, session, params=params
    )


@router.post("/collections")
async def add_collection(
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "POST", "/auth/v1/collections", user, session, request=request
    )


@router.post("/collections/{collection_id}/bookmarks")
async def add_collection_bookmark(
    collection_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "POST",
        f"/auth/v1/collections/{collection_id}/bookmarks",
        user,
        session,
        request=request,
    )


@router.delete("/collections/{collection_id}/bookmarks")
async def delete_collection_bookmark_by_details(
    collection_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "DELETE",
        f"/auth/v1/collections/{collection_id}/bookmarks",
        user,
        session,
        request=request,
    )


@router.delete("/collections/{collection_id}/bookmarks/{bookmark_id}")
async def delete_collection_bookmark_by_id(
    collection_id: str,
    bookmark_id: str,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "DELETE",
        f"/auth/v1/collections/{collection_id}/bookmarks/{bookmark_id}",
        user,
        session,
    )


@router.post("/collections/{collection_id}")
async def update_collection(
    collection_id: str,
    request: Request,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "PUT", f"/auth/v1/collections/{collection_id}", user, session, request=request
    )


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    authorization: str = Header(...),
    session: Session = Depends(get_session),
):
    user = _get_user_from_authorization(authorization, session)
    await _refresh_if_needed(user, session)

    return await _forward_request(
        "DELETE", f"/auth/v1/collections/{collection_id}", user, session
    )
