"""User state management for multi-step interactions."""

from typing import Optional, Dict
from threading import Lock

# In-memory state store: user_id -> state_data
_user_states: Dict[int, Dict] = {}
_state_lock = Lock()


def set_user_state(user_id: int, state: str, data: Optional[Dict] = None) -> None:
    """
    Set user state for multi-step interactions.
    
    Args:
        user_id: Telegram user ID
        state: State name (e.g., "waiting_for_prodamus_email")
        data: Optional state data (e.g., {"course_id": "123"})
    """
    with _state_lock:
        _user_states[user_id] = {
            "state": state,
            "data": data or {}
        }


def get_user_state(user_id: int) -> Optional[Dict]:
    """
    Get user state.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Dict with "state" and "data" keys, or None if no state
    """
    with _state_lock:
        return _user_states.get(user_id)


def clear_user_state(user_id: int) -> None:
    """
    Clear user state.
    
    Args:
        user_id: Telegram user ID
    """
    with _state_lock:
        _user_states.pop(user_id, None)


def is_user_in_state(user_id: int, state: str) -> bool:
    """
    Check if user is in a specific state.
    
    Args:
        user_id: Telegram user ID
        state: State name to check
        
    Returns:
        True if user is in the specified state
    """
    user_state = get_user_state(user_id)
    return user_state is not None and user_state.get("state") == state

