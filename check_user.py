"""
Quick check - prints out what's saved in the database for a user,
so we can confirm the onboarding/profile-save is actually working.

Run with: python check_user.py
"""

from app.db.database import get_db_session
from app.db.models import User

db = get_db_session()
users = db.query(User).all()

for user in users:
    print(f"telegram_id: {user.telegram_id}, role: {user.role}, interests: {user.interests}")

db.close()