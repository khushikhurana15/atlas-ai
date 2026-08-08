"""
This file sets up the connection to the Postgres database.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import DATABASE_URL

# pool_pre_ping=True: before handing out a connection from the pool,
# SQLAlchemy sends a quick "are you still alive?" check first. Neon
# (our free Postgres host) closes idle connections aggressively, so
# without this, a stale/dead connection can get reused and every
# query on it fails - exactly the "works, works, works, then
# everything breaks" pattern we saw. This adds a tiny bit of latency
# per request but makes the connection self-healing.
#
# pool_recycle=280: also proactively discard any connection older
# than ~4.5 minutes, before Neon's own timeout has a chance to kill
# it from its side.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
)

SessionLocal = sessionmaker(bind=engine)


def get_db_session():
    """Returns a new database session whenever one is needed."""
    return SessionLocal()