"""Local analytics and feedback tracking for CursorHub.

All data is stored in a single SQLite database at ~/.cursorhub/analytics.db.
Nothing is ever sent externally — everything stays on the user's machine.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from cursorhub.config import CONFIG_DIR


_DB_PATH = CONFIG_DIR / "analytics.db"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Open (and create if needed) the analytics database."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event TEXT NOT NULL,
            prompt_filename TEXT,
            project_path TEXT,
            meta TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_event
        ON events (event)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_events_prompt
        ON events (prompt_filename)
    """)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

def log_event(
    event: str,
    prompt_filename: Optional[str] = None,
    project_path: Optional[str] = None,
    **meta: Any,
) -> None:
    """Record a single analytics event.

    This is the main entry point — all other modules call this.
    Silently swallows errors so analytics never break the app.

    Args:
        event: Event name (e.g. "prompt_created", "project_opened").
        prompt_filename: Associated prompt filename, if any.
        project_path: Associated project path, if any.
        **meta: Arbitrary extra data stored as a JSON blob.
    """
    try:
        conn = _get_db()
        conn.execute(
            "INSERT INTO events (timestamp, event, prompt_filename, project_path, meta) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(),
                event,
                prompt_filename,
                project_path,
                json.dumps(meta) if meta else None,
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Never let analytics break the app


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_prompt_stats(filename: str) -> dict[str, Any]:
    """Compute usage statistics for a single prompt.

    Returns a dict with:
        times_used: int — count of prompt_applied events
        last_used: str | None — ISO timestamp of most recent use
        avg_rating: float | None — average feedback rating (1-4)
        rating_count: int — number of feedback ratings
        edit_count: int — number of prompt_edited events
        projects: list[str] — paths of projects created from this prompt
    """
    try:
        conn = _get_db()

        # Times used + last used
        row = conn.execute(
            "SELECT COUNT(*) as cnt, MAX(timestamp) as last_ts "
            "FROM events WHERE event = 'prompt_applied' AND prompt_filename = ?",
            (filename,),
        ).fetchone()
        times_used = row["cnt"] if row else 0
        last_used = row["last_ts"] if row else None

        # Projects created from this prompt
        rows = conn.execute(
            "SELECT DISTINCT project_path FROM events "
            "WHERE event = 'prompt_applied' AND prompt_filename = ? "
            "AND project_path IS NOT NULL",
            (filename,),
        ).fetchall()
        projects = [r["project_path"] for r in rows]

        # Average feedback rating
        rating_row = conn.execute(
            "SELECT AVG(CAST(json_extract(meta, '$.rating') AS REAL)) as avg_r, "
            "       COUNT(*) as cnt "
            "FROM events WHERE event = 'feedback_given' AND prompt_filename = ? "
            "AND json_extract(meta, '$.rating') IS NOT NULL",
            (filename,),
        ).fetchone()
        avg_rating = round(rating_row["avg_r"], 1) if rating_row and rating_row["avg_r"] else None
        rating_count = rating_row["cnt"] if rating_row and rating_row["avg_r"] else 0

        # Edit count
        edit_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM events "
            "WHERE event = 'prompt_edited' AND prompt_filename = ?",
            (filename,),
        ).fetchone()
        edit_count = edit_row["cnt"] if edit_row else 0

        conn.close()

        return {
            "times_used": times_used,
            "last_used": last_used,
            "avg_rating": avg_rating,
            "rating_count": rating_count,
            "edit_count": edit_count,
            "projects": projects,
        }
    except Exception:
        return {
            "times_used": 0,
            "last_used": None,
            "avg_rating": None,
            "rating_count": 0,
            "edit_count": 0,
            "projects": [],
        }


def get_all_prompt_stats() -> dict[str, dict[str, Any]]:
    """Compute usage stats for all prompts at once (efficient batch query).

    Returns {filename: stats_dict} where stats_dict has the same keys
    as get_prompt_stats().
    """
    try:
        conn = _get_db()
        stats: dict[str, dict[str, Any]] = {}

        # Usage counts and last used
        for row in conn.execute(
            "SELECT prompt_filename, COUNT(*) as cnt, MAX(timestamp) as last_ts "
            "FROM events WHERE event = 'prompt_applied' AND prompt_filename IS NOT NULL "
            "GROUP BY prompt_filename"
        ).fetchall():
            fn = row["prompt_filename"]
            stats.setdefault(fn, _empty_stats())
            stats[fn]["times_used"] = row["cnt"]
            stats[fn]["last_used"] = row["last_ts"]

        # Ratings
        for row in conn.execute(
            "SELECT prompt_filename, "
            "       AVG(CAST(json_extract(meta, '$.rating') AS REAL)) as avg_r, "
            "       COUNT(*) as cnt "
            "FROM events WHERE event = 'feedback_given' AND prompt_filename IS NOT NULL "
            "AND json_extract(meta, '$.rating') IS NOT NULL "
            "GROUP BY prompt_filename"
        ).fetchall():
            fn = row["prompt_filename"]
            stats.setdefault(fn, _empty_stats())
            stats[fn]["avg_rating"] = round(row["avg_r"], 1) if row["avg_r"] else None
            stats[fn]["rating_count"] = row["cnt"]

        # Edit counts
        for row in conn.execute(
            "SELECT prompt_filename, COUNT(*) as cnt "
            "FROM events WHERE event = 'prompt_edited' AND prompt_filename IS NOT NULL "
            "GROUP BY prompt_filename"
        ).fetchall():
            fn = row["prompt_filename"]
            stats.setdefault(fn, _empty_stats())
            stats[fn]["edit_count"] = row["cnt"]

        # Projects per prompt
        for row in conn.execute(
            "SELECT prompt_filename, project_path "
            "FROM events WHERE event = 'prompt_applied' "
            "AND prompt_filename IS NOT NULL AND project_path IS NOT NULL"
        ).fetchall():
            fn = row["prompt_filename"]
            stats.setdefault(fn, _empty_stats())
            if row["project_path"] not in stats[fn]["projects"]:
                stats[fn]["projects"].append(row["project_path"])

        conn.close()
        return stats
    except Exception:
        return {}


def get_pending_feedback() -> list[dict[str, Any]]:
    """Find projects created from prompts that haven't been rated yet.

    Only returns projects created at least 1 hour ago (give the user
    time to actually try the prompt).

    Returns list of dicts with: prompt_filename, project_path, project_name, created_at.
    """
    try:
        conn = _get_db()
        cutoff = (datetime.now() - timedelta(hours=1)).isoformat()

        rows = conn.execute(
            """
            SELECT e.prompt_filename, e.project_path, e.timestamp, e.meta
            FROM events e
            WHERE e.event = 'prompt_applied'
              AND e.prompt_filename IS NOT NULL
              AND e.project_path IS NOT NULL
              AND e.timestamp < ?
              AND NOT EXISTS (
                  SELECT 1 FROM events f
                  WHERE f.event = 'feedback_given'
                    AND f.prompt_filename = e.prompt_filename
                    AND f.project_path = e.project_path
              )
              AND NOT EXISTS (
                  SELECT 1 FROM events s
                  WHERE s.event = 'feedback_skipped'
                    AND s.prompt_filename = e.prompt_filename
                    AND s.project_path = e.project_path
              )
            ORDER BY e.timestamp DESC
            LIMIT 3
            """,
            (cutoff,),
        ).fetchall()

        conn.close()

        results = []
        for r in rows:
            meta = json.loads(r["meta"]) if r["meta"] else {}
            results.append({
                "prompt_filename": r["prompt_filename"],
                "project_path": r["project_path"],
                "project_name": meta.get("project_name", Path(r["project_path"]).name),
                "created_at": r["timestamp"],
            })
        return results
    except Exception:
        return []


def get_overall_stats() -> dict[str, Any]:
    """Compute overall analytics summary.

    Returns:
        total_projects_created: int
        total_prompts_used: int (unique prompts that have been applied)
        total_prompt_applications: int
        most_used_prompt: str | None
        avg_rating_all: float | None
        events_last_30_days: int
    """
    try:
        conn = _get_db()

        total_created = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event = 'project_created'"
        ).fetchone()["cnt"]

        total_applications = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE event = 'prompt_applied'"
        ).fetchone()["cnt"]

        unique_prompts = conn.execute(
            "SELECT COUNT(DISTINCT prompt_filename) as cnt "
            "FROM events WHERE event = 'prompt_applied'"
        ).fetchone()["cnt"]

        most_used = conn.execute(
            "SELECT prompt_filename, COUNT(*) as cnt "
            "FROM events WHERE event = 'prompt_applied' AND prompt_filename IS NOT NULL "
            "GROUP BY prompt_filename ORDER BY cnt DESC LIMIT 1"
        ).fetchone()
        most_used_prompt = most_used["prompt_filename"] if most_used else None

        avg_r = conn.execute(
            "SELECT AVG(CAST(json_extract(meta, '$.rating') AS REAL)) as avg_r "
            "FROM events WHERE event = 'feedback_given' "
            "AND json_extract(meta, '$.rating') IS NOT NULL"
        ).fetchone()
        avg_rating_all = round(avg_r["avg_r"], 1) if avg_r and avg_r["avg_r"] else None

        cutoff_30d = (datetime.now() - timedelta(days=30)).isoformat()
        recent = conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE timestamp > ?",
            (cutoff_30d,),
        ).fetchone()["cnt"]

        conn.close()

        return {
            "total_projects_created": total_created,
            "total_prompts_used": unique_prompts,
            "total_prompt_applications": total_applications,
            "most_used_prompt": most_used_prompt,
            "avg_rating_all": avg_rating_all,
            "events_last_30_days": recent,
        }
    except Exception:
        return {
            "total_projects_created": 0,
            "total_prompts_used": 0,
            "total_prompt_applications": 0,
            "most_used_prompt": None,
            "avg_rating_all": None,
            "events_last_30_days": 0,
        }


def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Get the most recent analytics events for display.

    Returns list of dicts with: timestamp, event, prompt_filename, project_path, meta.
    """
    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT timestamp, event, prompt_filename, project_path, meta "
            "FROM events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {
                "timestamp": r["timestamp"],
                "event": r["event"],
                "prompt_filename": r["prompt_filename"],
                "project_path": r["project_path"],
                "meta": json.loads(r["meta"]) if r["meta"] else {},
            }
            for r in rows
        ]
    except Exception:
        return []


def compute_prompt_health(stats: dict[str, Any]) -> str:
    """Compute a health label for a prompt based on its stats.

    Returns one of: "great", "good", "needs_attention", "unused", "new".
    """
    times_used = stats.get("times_used", 0)
    avg_rating = stats.get("avg_rating")
    edit_count = stats.get("edit_count", 0)

    if times_used == 0:
        return "unused" if edit_count > 0 else "new"

    if avg_rating is not None:
        if avg_rating >= 3.5:
            return "great"
        if avg_rating >= 2.5:
            return "good"
        return "needs_attention"

    # No ratings yet but has been used
    if edit_count > times_used * 2:
        return "needs_attention"  # Edited a lot relative to usage

    return "good"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _empty_stats() -> dict[str, Any]:
    return {
        "times_used": 0,
        "last_used": None,
        "avg_rating": None,
        "rating_count": 0,
        "edit_count": 0,
        "projects": [],
    }
