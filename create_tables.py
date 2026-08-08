"""
This script only needs to be run once - it creates the
actual tables (users, conversations) in Postgres.
"""

from app.db.database import engine
from app.db.models import Base

Base.metadata.create_all(engine)
print("Tables created! ✅")