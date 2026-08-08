"""
This isn't a normal tool - it doesn't fetch anything. It's how the AI
"remembers" something the user tells it about themselves (their role
or interests) during a normal conversation. The orchestrator catches
calls to this specific tool and saves the info to the database - this
file just formats what was learned.
"""


def update_user_profile(role: str = None, interests: str = None) -> dict:
    updates = {}
    if role:
        updates["role"] = role
    if interests:
        updates["interests"] = interests
    return {"status": "recorded", **updates}