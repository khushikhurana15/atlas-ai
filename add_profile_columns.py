"""
One-time migration - adds 'role' and 'interests' columns to the
existing users table (needed for onboarding/personalization).

Run once with: python add_profile_columns.py
"""

from sqlalchemy import text
from app.db.database import engine

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR"))
    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS interests TEXT"))
    conn.commit()

print("Columns added! ✅")