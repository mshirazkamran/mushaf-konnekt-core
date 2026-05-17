from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from pydantic import BaseModel
from src.repository.database import get_session
from src.repository.models import User
from src.services.qf_oauth import exchange_code_for_tokens, refresh_access_token, QFTokenResponse

import time
import secrets

router = APIRouter(prefix="/auth", tags=["auth"])

class ExchangeRequest(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str

class RefreshRequest(BaseModel):
    sub: str

@router.post("/exchange")
async def exchange_token(request: ExchangeRequest, session: Session = Depends(get_session)):
    exchange_result = await exchange_code_for_tokens(
        code=request.code,
        redirect_uri=request.redirect_uri,
        code_verifier=request.code_verifier
    )
    
    tokens = exchange_result["tokens"]
    user_info = exchange_result["user"]
    
    if not user_info:
        raise HTTPException(status_code=400, detail="Missing OpenID Connect user information")
        
    expires_at = int(time.time()) + tokens.expires_in
    new_session_token = secrets.token_urlsafe(64)
        
    user = session.get(User, user_info.sub)
    if not user:
        user = User(
            sub=user_info.sub,
            email=user_info.email,
            first_name=user_info.first_name,
            last_name=user_info.last_name,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or "",
            expires_at=expires_at,
            session_token=new_session_token,
        )
        session.add(user)
    else:
        user.access_token = tokens.access_token
        user.expires_at = expires_at
        user.session_token = new_session_token
        if tokens.refresh_token:
            user.refresh_token = tokens.refresh_token
        if user_info.email:
            user.email = user_info.email
        if user_info.first_name:
            user.first_name = user_info.first_name
        if user_info.last_name:
            user.last_name = user_info.last_name
            
    session.commit()
    session.refresh(user)
    
    return {
        "message": "Login successful", 
        "sub": user.sub,
        "session_token": user.session_token
    }

@router.post("/refresh")
async def refresh_token(request: RefreshRequest, session: Session = Depends(get_session)):
    user = session.get(User, request.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")
        
    tokens = await refresh_access_token(user.refresh_token)
    
    user.access_token = tokens.access_token
    user.expires_at = int(time.time()) + tokens.expires_in
    if tokens.refresh_token:
        user.refresh_token = tokens.refresh_token
        
    session.commit()
    
    return {"message": "Token refreshed"}
