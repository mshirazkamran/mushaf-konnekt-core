from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI


def main():
    print("Hello from mushaf-konnekt-backend!")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    # Startup logic
    print("Application starting up...")
    yield
    # Shutdown logic
    print("Application shutting down...")


app = FastAPI(title="Mushaf Konnekt Backend", version="0.0.1", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Welcome to Mushaf Konnekt Backend"}


if __name__ == "__main__":
    main()
