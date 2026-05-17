import os

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

# Use local postgres configuration from docker-compose.yml as default
# In production, this should come from environment variables
DATABASE_URL = os.environ.get("DATABASE_URL", None)

# We use psycopg 3. SQLModel supports postgresql+psycopg
if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL IS NONE, CONFIGURE THE ENV PROPERLY!! ")

engine = create_engine(DATABASE_URL, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
