import json
import os
from datetime import datetime, timezone

from config import STATE_FILE, MAX_SEEN_URLS, MAX_QUEUE_SIZE

DEFAULT_STATE = {
    "last_collected": None,
    "seen_urls": [],
    "queue": [],
    "stats": {
        "total_posted": 0,
        "total_collected": 0,
        "last_posted": None,
    }
}


def load() -> dict:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    if not os.path.exists(STATE_FILE):
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return dict(DEFAULT_STATE)


def save(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state["seen_urls"] = state["seen_urls"][-MAX_SEEN_URLS:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_seen(state: dict, url: str) -> bool:
    return url in state["seen_urls"]


def mark_seen(state: dict, url: str):
    if url not in state["seen_urls"]:
        state["seen_urls"].append(url)


def add_to_queue(state: dict, item: dict):
    if len(state["queue"]) < MAX_QUEUE_SIZE:
        state["queue"].append(item)


def pop_next(state: dict) -> dict | None:
    if state["queue"]:
        return state["queue"].pop(0)
    return None


def collection_needed(state: dict, interval_hours: int) -> bool:
    if not state.get("last_collected"):
        return True
    last = datetime.fromisoformat(state["last_collected"])
    now  = datetime.now(timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (now - last).total_seconds() >= interval_hours * 3600


def mark_collected(state: dict):
    state["last_collected"] = datetime.now(timezone.utc).isoformat()


def mark_posted(state: dict):
    state["stats"]["total_posted"] += 1
    state["stats"]["last_posted"] = datetime.now(timezone.utc).isoformat()


def get_stats(state: dict) -> dict:
    return {
        "queue_size":     len(state["queue"]),
        "seen_urls":      len(state["seen_urls"]),
        "total_posted":   state["stats"].get("total_posted", 0),
        "total_collected":state["stats"].get("total_collected", 0),
        "last_posted":    state["stats"].get("last_posted"),
        "last_collected": state.get("last_collected"),
    }
