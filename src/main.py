from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn

from fastapi import FastAPI
from src.repository.database import create_db_and_tables
from src.routers import auth, user_api



@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup logic
    print("Application starting up...")
    create_db_and_tables()
    yield
    # Shutdown logic
    print("Application shutting down...")

app = FastAPI(title="Mushaf Konnekt Backend", version="0.0.1", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(user_api.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Mushaf Konnekt Backend"}


def main():
    print("Hello from mushaf-konnekt-backend!")
    uvicorn.run(app=app, port=8000, host="0.0.0.0")
    
if __name__ == "__main__":
    main()
