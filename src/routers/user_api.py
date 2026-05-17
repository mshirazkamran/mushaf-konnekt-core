from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Session, select
import httpx
import os
from src.repository.database import get_session
from src.repository.models import User

import time
from src.services.qf_oauth import refresh_access_token

router = APIRouter(prefix="/qf-proxy", tags=["qf-proxy"])

QF_API_BASE_URL = os.environ.get("QF_API_BASE_URL", "https://apis-prelive.quran.foundation")
QF_CLIENT_ID = os.environ.get("QF_CLIENT_ID_PRELIVE")

@router.get("/bookmarks")
async def get_bookmarks(authorization: str = Header(...), session: Session = Depends(get_session)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
        
    session_token = authorization.split(" ")[1]
    user = session.exec(select(User).where(User.session_token == session_token)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not QF_CLIENT_ID:
        raise HTTPException(status_code=500, detail="OAuth credentials not configured")
        
    # Check if token is expired or about to expire in the next 60 seconds
    if user.expires_at and time.time() > user.expires_at - 60:
        if user.refresh_token:
            try:
                tokens = await refresh_access_token(user.refresh_token)
                user.access_token = tokens.access_token
                user.expires_at = int(time.time()) + tokens.expires_in
                if tokens.refresh_token:
                    user.refresh_token = tokens.refresh_token
                session.commit()
            except Exception as e:
                # If refresh fails, we can still try with the old token or fail early. 
                # Here we log and let it proceed; QF API will return 401 if it's truly expired.
                print(f"Failed to proactively refresh token: {e}")
                
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{QF_API_BASE_URL}/auth/v1/bookmarks",
            headers={
                "x-auth-token": user.access_token,
                "x-client-id": QF_CLIENT_ID
            }
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"QF API Error: {response.text}")
            
        return response.json()
