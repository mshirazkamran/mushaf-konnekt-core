import os
import httpx
import jwt
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional

QF_AUTH_BASE_URL = os.environ.get("QF_AUTH_BASE_URL", "https://prelive-oauth2.quran.foundation")
QF_CLIENT_ID = os.environ.get("QF_CLIENT_ID_PRELIVE")
QF_CLIENT_SECRET = os.environ.get("QF_CLIENT_SECRET_PRELIVE")

class QFTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: str

class QFUserInfo(BaseModel):
    sub: str
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

async def exchange_code_for_tokens(code: str, redirect_uri: str, code_verifier: str) -> dict:
    if not QF_CLIENT_ID or not QF_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")
        
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{QF_AUTH_BASE_URL}/oauth2/token",
            auth=(QF_CLIENT_ID, QF_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to exchange token: {response.text}")
            
        token_data = response.json()
        
        # Parse id_token
        user_info = None
        if "id_token" in token_data:
            # We don't need to verify signature here because we obtained the token directly from QF via HTTPS
            decoded = jwt.decode(token_data["id_token"], options={"verify_signature": False})
            user_info = QFUserInfo(
                sub=decoded.get("sub"),
                email=decoded.get("email"),
                first_name=decoded.get("first_name"),
                last_name=decoded.get("last_name"),
            )
            
        return {
            "tokens": QFTokenResponse(**token_data),
            "user": user_info
        }

async def refresh_access_token(refresh_token: str) -> QFTokenResponse:
    if not QF_CLIENT_ID or not QF_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")
        
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{QF_AUTH_BASE_URL}/oauth2/token",
            auth=(QF_CLIENT_ID, QF_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Failed to refresh token: {response.text}")
            
        token_data = response.json()
        return QFTokenResponse(**token_data)
