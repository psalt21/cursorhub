"""Configuration management for CursorHub."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


CONFIG_DIR = Path.home() / ".cursorhub"
CONFIG_FILE = CONFIG_DIR / "config.json"
BACKUP_DIR = CONFIG_DIR / "backups"

CURSOR_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "Cursor"
CURSOR_WORKSPACE_STORAGE = CURSOR_SUPPORT_DIR / "User" / "workspaceStorage"
CURSOR_GLOBAL_STORAGE = CURSOR_SUPPORT_DIR / "User" / "globalStorage"

def _find_cursor_app() -> str:
    """Auto-detect the Cursor app path."""
    candidates = [
        "/Applications/Cursor.app",
        "/Applications/Cursor - Personal.app",
        "/Applications/Cursor - Work.app",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return "/Applications/Cursor.app"


DEFAULT_CONFIG: dict[str, Any] = {
    "projects": [],
    "backup_dir": str(BACKUP_DIR),
    "cursor_app": _find_cursor_app(),
}


def ensure_dirs() -> None:
    """Create config and backup directories if they don't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config from disk, creating default if missing."""
    ensure_dirs()
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    """Write config to disk."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single value from the config."""
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> dict[str, Any]:
    """Set a single value in the config. Returns the updated config."""
    config = load_config()
    config[key] = value
    save_config(config)
    return config


def add_project(
    name: str,
    path: str,
    repo: str = "",
    created_via: str = "",
    prompt_filename: str = "",
    prompt_variables: Any = None,
) -> dict[str, Any]:
    """Add a project to the config. Returns the updated config.

    Args:
        name: Display name for the project.
        path: Filesystem path to the project folder.
        repo: Optional Git repository URL.
        created_via: How the project was created ("prompt", "clone", "blank", or "").
        prompt_filename: The starter prompt used, if any.
        prompt_variables: Template variable values used, if any.
    """
    from datetime import datetime

    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())

    # Don't add duplicates
    for p in config["projects"]:
        if p["path"] == abs_path:
            p["name"] = name  # Update name if re-adding
            if repo:
                p["repo"] = repo
            save_config(config)
            return config

    project: dict[str, Any] = {
        "name": name,
        "path": abs_path,
        "created_at": datetime.now().isoformat(),
    }
    if repo:
        project["repo"] = repo
    if created_via:
        project["created_via"] = created_via
    if prompt_filename:
        project["prompt_filename"] = prompt_filename
    if prompt_variables:
        project["prompt_variables"] = prompt_variables

    config["projects"].append(project)
    save_config(config)
    return config


def remove_project(path: str) -> dict[str, Any]:
    """Remove a project by path (from active list only). Returns the updated config."""
    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())
    config["projects"] = [p for p in config["projects"] if p["path"] != abs_path]
    save_config(config)
    return config


def archive_project(path: str) -> dict[str, Any]:
    """Move a project from active to archived. Returns the updated config."""
    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())

    # Find the project in the active list
    project = None
    remaining = []
    for p in config.get("projects", []):
        if p["path"] == abs_path:
            project = p
        else:
            remaining.append(p)

    if project is None:
        return config  # Not found; nothing to archive

    config["projects"] = remaining
    archived = config.setdefault("archived_projects", [])

    # Don't double-archive
    if not any(a["path"] == abs_path for a in archived):
        archived.append(project)

    save_config(config)
    return config


def unarchive_project(path: str) -> dict[str, Any]:
    """Move a project from archived back to active. Returns the updated config."""
    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())

    archived = config.get("archived_projects", [])
    project = None
    remaining = []
    for p in archived:
        if p["path"] == abs_path:
            project = p
        else:
            remaining.append(p)

    if project is None:
        return config  # Not found in archive

    config["archived_projects"] = remaining
    projects = config.setdefault("projects", [])

    # Don't add duplicate
    if not any(p["path"] == abs_path for p in projects):
        projects.append(project)

    save_config(config)
    return config


def delete_project(path: str, delete_files: bool = False) -> dict[str, Any]:
    """Permanently delete a project from both active and archived lists.

    If *delete_files* is True, also delete the project folder from disk.
    Returns the updated config.
    """
    import shutil

    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())

    config["projects"] = [p for p in config.get("projects", []) if p["path"] != abs_path]
    config["archived_projects"] = [
        p for p in config.get("archived_projects", []) if p["path"] != abs_path
    ]
    save_config(config)

    if delete_files:
        target = Path(abs_path)
        if target.exists() and target.is_dir():
            shutil.rmtree(target, ignore_errors=True)

    return config


def get_workspace_mappings() -> dict[str, list[str]]:
    """Scan Cursor's workspace storage and return {folder_path: [hash, ...]} mappings.

    This tells us which workspace hashes Cursor has for each project folder.
    A project with multiple hashes means Cursor created duplicate workspace entries
    (which is the root cause of lost chat history).
    """
    mappings: dict[str, list[str]] = {}

    if not CURSOR_WORKSPACE_STORAGE.exists():
        return mappings

    for entry in CURSOR_WORKSPACE_STORAGE.iterdir():
        if not entry.is_dir():
            continue
        ws_file = entry / "workspace.json"
        if not ws_file.exists():
            continue
        try:
            with open(ws_file, "r") as f:
                data = json.load(f)
            folder_uri = data.get("folder", "")
            if folder_uri.startswith("file://"):
                folder_path = unquote(urlparse(folder_uri).path)
                mappings.setdefault(folder_path, []).append(entry.name)
        except (json.JSONDecodeError, KeyError):
            continue

    return mappings


def auto_discover_projects(projects_root: str = "") -> list[dict[str, str]]:
    """Auto-discover projects from Cursor's workspace storage.

    Returns a list of project dicts ready to be added to config.
    """
    mappings = get_workspace_mappings()
    discovered = []
    for folder_path in sorted(mappings.keys()):
        path = Path(folder_path)
        if projects_root and not folder_path.startswith(projects_root):
            continue
        if path.exists():
            discovered.append({
                "name": path.name.replace("-", " ").title(),
                "path": folder_path,
            })
    return discovered
