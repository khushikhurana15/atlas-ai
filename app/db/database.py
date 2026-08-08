"""
This file sets up the connection to the Postgres database.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# Engine = the actual connection to the database
engine = create_engine(DATABASE_URL)

# Session = one "conversation" with the database (sending queries, saving data)
SessionLocal = sessionmaker(bind=engine)


def get_db_session():
    """Returns a new database session whenever one is needed."""
    return SessionLocal()