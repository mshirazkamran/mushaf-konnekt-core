from sqlmodel import SQLModel, Field
from typing import Optional

class User(SQLModel, table=True):
    sub: str = Field(primary_key=True)
    email: Optional[str] = Field(default=None)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    access_token: str
    refresh_token: str
    expires_at: Optional[int] = Field(default=None)
    session_token: Optional[str] = Field(default=None, index=True)
    quran_recitation_progress: float = Field(default=0.0)
