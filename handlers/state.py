# handlers/state.py
"""Shared state management for handlers."""

# State management for Prodamus email collection
# Maps user_id -> course_id for users awaiting email input
prodamus_awaiting_email: dict[int, str] = {}

