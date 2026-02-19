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
CURSOR_STORAGE_JSON = CURSOR_SUPPORT_DIR / "User" / "globalStorage" / "storage.json"

DEFAULT_PROFILE = "__default__"  # sentinel for "no profile / use Cursor default"

# ---------------------------------------------------------------------------
# Port registry
# ---------------------------------------------------------------------------

# Starting port for each variable-name prefix (ranges are 100 wide)
PORT_RANGES: dict[str, int] = {
    "frontend": 3000,
    "client":   3100,
    "web":      3200,
    "backend":  8000,
    "api":      8100,
    "server":   8200,
    "worker":   9000,
    "queue":    9100,
    "job":      9200,
    "other":    4000,   # fallback for unrecognised prefixes
}


def _port_range_for(var_name: str) -> int:
    """Return the base port for a port variable name like 'frontend_port'."""
    prefix = var_name.replace("_port", "").split("_")[0].lower()
    return PORT_RANGES.get(prefix, PORT_RANGES["other"])


def get_all_allocated_ports() -> set[int]:
    """Return every port already assigned to any project (active or archived)."""
    config = load_config()
    used: set[int] = set()
    for lst in (config.get("projects", []), config.get("archived_projects", [])):
        for project in lst:
            for port in project.get("ports", {}).values():
                if isinstance(port, int):
                    used.add(port)
    return used


def allocate_ports(port_var_names: list[str]) -> dict[str, int]:
    """Assign a unique port to each variable name (e.g. 'frontend_port').

    Ports are guaranteed not to conflict with any existing project.
    """
    used = get_all_allocated_ports()
    assignments: dict[str, int] = {}
    for var in port_var_names:
        base = _port_range_for(var)
        port = base
        while port in used or port in assignments.values():
            port += 1
        assignments[var] = port
        used.add(port)
    return assignments


def set_project_ports(path: str, ports: dict[str, int], merge: bool = True) -> dict[str, Any]:
    """Store port assignments for a project.

    If *merge* is True (default), merges with existing ports.
    If *merge* is False, replaces all ports.
    """
    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())
    for lst in (config.get("projects", []), config.get("archived_projects", [])):
        for p in lst:
            if p["path"] == abs_path:
                if merge:
                    existing = p.get("ports", {})
                    existing.update(ports)
                    p["ports"] = existing
                else:
                    p["ports"] = dict(ports)
                save_config(config)
                return config
    return config


def is_port_variable(var_name: str) -> bool:
    """Return True if *var_name* should be treated as an auto-assigned port."""
    return var_name.endswith("_port") or var_name == "port"


def list_cursor_profiles() -> list[dict[str, str]]:
    """Return all Cursor profiles available on this machine.

    Each entry: {"name": "Work", "id": "-20e14fb3"} (id is Cursor's internal location key).
    Always includes a synthetic Default entry first.
    """
    profiles = [{"name": "Default", "id": DEFAULT_PROFILE}]
    try:
        if CURSOR_STORAGE_JSON.exists():
            with open(CURSOR_STORAGE_JSON, "r") as f:
                data = json.load(f)
            for p in data.get("userDataProfiles", []):
                name = p.get("name", "").strip()
                loc  = p.get("location", "")
                if name:
                    profiles.append({"name": name, "id": loc})
    except Exception:
        pass
    return profiles


def set_project_profile(path: str, profile_name: str) -> dict[str, Any]:
    """Set (or clear) the Cursor profile for a project. Returns updated config."""
    config = load_config()
    abs_path = str(Path(path).expanduser().resolve())
    for lst in (config.get("projects", []), config.get("archived_projects", [])):
        for p in lst:
            if p["path"] == abs_path:
                if profile_name and profile_name != DEFAULT_PROFILE:
                    p["cursor_profile"] = profile_name
                else:
                    p.pop("cursor_profile", None)
                save_config(config)
                return config
    return config


def open_in_cursor(path: str, cursor_app: str = "") -> None:
    """Open *path* in Cursor, respecting any profile configured for the project."""
    import subprocess

    config = load_config()
    if not cursor_app:
        cursor_app = config.get("cursor_app", _find_cursor_app())

    abs_path = str(Path(path).expanduser().resolve())

    # Find profile for this project
    profile_name = ""
    for lst in (config.get("projects", []), config.get("archived_projects", [])):
        for p in lst:
            if p["path"] == abs_path:
                profile_name = p.get("cursor_profile", "")
                break

    cursor_bin = str(Path(cursor_app) / "Contents" / "MacOS" / "Cursor")
    if Path(cursor_bin).exists() and profile_name:
        subprocess.Popen([cursor_bin, "--profile", profile_name, abs_path])
    elif profile_name:
        subprocess.Popen(["open", "-a", cursor_app, "--args",
                          "--profile", profile_name, abs_path])
    else:
        subprocess.Popen(["open", "-a", cursor_app, abs_path])

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
