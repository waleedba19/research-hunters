"""
state_manager.py — Per-chat state persistence (JSON file per chat_id).
State survives bot restarts and GHA job boundaries.
"""
import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, Optional
from logger import get_logger

log = get_logger("state_manager")

DEFAULT_STATE_DIR = os.path.join(os.path.dirname(__file__), "data", "state")

_lock = threading.Lock()


def _state_path(chat_id: int, state_dir: str = DEFAULT_STATE_DIR) -> str:
    os.makedirs(state_dir, exist_ok=True)
    return os.path.join(state_dir, f"chat_{chat_id}.json")


def save_chapter_state(chat_id: int, state: Dict[str, Any], state_dir: str = DEFAULT_STATE_DIR) -> None:
    """Persist per-chat state atomically. Adds timestamp + version."""
    state = dict(state)
    state["_updated_at"] = datetime.utcnow().isoformat() + "Z"
    state["_version"] = state.get("_version", 0) + 1
    path = _state_path(chat_id, state_dir)
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    log.info(f"Saved state for chat {chat_id} (v{state['_version']})")


def load_chapter_state(chat_id: int, state_dir: str = DEFAULT_STATE_DIR) -> Optional[Dict[str, Any]]:
    """Load per-chat state. Returns None if no state exists."""
    path = _state_path(chat_id, state_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Failed to load state for chat {chat_id}: {e}")
        return None


def clear_chapter_state(chat_id: int, state_dir: str = DEFAULT_STATE_DIR) -> None:
    """Delete per-chat state (used after wizard completes or on /reset)."""
    path = _state_path(chat_id, state_dir)
    with _lock:
        if os.path.exists(path):
            os.remove(path)
            log.info(f"Cleared state for chat {chat_id}")


def update_field(chat_id: int, key: str, value: Any, state_dir: str = DEFAULT_STATE_DIR) -> Dict[str, Any]:
    """Atomic read-modify-write of a single field. Returns the new state."""
    with _lock:
        state = load_chapter_state(chat_id, state_dir) or {}
        state[key] = value
        save_chapter_state(chat_id, state, state_dir)
        return state
