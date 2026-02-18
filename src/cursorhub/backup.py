"""Backup and restore Cursor workspace data (chat history, composer state, etc.)."""

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from cursorhub.config import (
    BACKUP_DIR,
    CURSOR_GLOBAL_STORAGE,
    CURSOR_WORKSPACE_STORAGE,
    get_workspace_mappings,
    load_config,
)


def create_backup(label: str = "") -> Path:
    """Create a timestamped backup of all Cursor workspace databases.

    Copies:
    - Every workspace's state.vscdb (per-project chat history)
    - The global state.vscdb (cross-project data)

    Returns the path to the backup directory.
    """
    config = load_config()
    backup_root = Path(config.get("backup_dir", str(BACKUP_DIR))).expanduser()
    backup_root.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if label:
        dir_name = f"{timestamp}_{label}"
    else:
        dir_name = timestamp

    backup_dir = backup_root / dir_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up = {"workspaces": 0, "global": False, "total_bytes": 0}

    # Back up per-workspace databases
    if CURSOR_WORKSPACE_STORAGE.exists():
        ws_backup_dir = backup_dir / "workspaces"
        ws_backup_dir.mkdir(exist_ok=True)

        mappings = get_workspace_mappings()
        # Create a reverse map: hash -> folder name (for labeling)
        hash_to_name = {}
        for folder, hashes in mappings.items():
            name = Path(folder).name
            for h in hashes:
                hash_to_name[h] = name

        for entry in CURSOR_WORKSPACE_STORAGE.iterdir():
            if not entry.is_dir():
                continue
            state_db = entry / "state.vscdb"
            if not state_db.exists():
                continue

            # Name the backup after the project for readability
            label_name = hash_to_name.get(entry.name, entry.name)
            dest_dir = ws_backup_dir / f"{label_name}__{entry.name}"
            dest_dir.mkdir(exist_ok=True)

            # Copy the SQLite database safely using backup API
            _safe_copy_sqlite(state_db, dest_dir / "state.vscdb")

            # Also copy workspace.json for reference
            ws_json = entry / "workspace.json"
            if ws_json.exists():
                shutil.copy2(ws_json, dest_dir / "workspace.json")

            backed_up["workspaces"] += 1
            backed_up["total_bytes"] += (dest_dir / "state.vscdb").stat().st_size

    # Back up global storage
    global_db = CURSOR_GLOBAL_STORAGE / "state.vscdb"
    if global_db.exists():
        global_backup_dir = backup_dir / "global"
        global_backup_dir.mkdir(exist_ok=True)
        _safe_copy_sqlite(global_db, global_backup_dir / "state.vscdb")
        backed_up["global"] = True
        backed_up["total_bytes"] += (global_backup_dir / "state.vscdb").stat().st_size

    # Write a manifest
    manifest = {
        "timestamp": timestamp,
        "workspaces_backed_up": backed_up["workspaces"],
        "global_backed_up": backed_up["global"],
        "total_bytes": backed_up["total_bytes"],
    }
    import json
    with open(backup_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    return backup_dir


def _safe_copy_sqlite(src: Path, dest: Path) -> None:
    """Copy a SQLite database safely using the SQLite backup API.

    This handles the case where Cursor might have the database open
    and locked. The backup API creates a consistent snapshot.
    """
    try:
        src_conn = sqlite3.connect(str(src))
        dest_conn = sqlite3.connect(str(dest))
        src_conn.backup(dest_conn)
        dest_conn.close()
        src_conn.close()
    except sqlite3.Error:
        # Fall back to file copy if SQLite backup fails
        shutil.copy2(src, dest)


def list_backups() -> list[dict]:
    """List all existing backups, newest first."""
    config = load_config()
    backup_root = Path(config.get("backup_dir", str(BACKUP_DIR))).expanduser()

    if not backup_root.exists():
        return []

    backups = []
    for entry in sorted(backup_root.iterdir(), reverse=True):
        if not entry.is_dir():
            continue
        manifest_file = entry / "manifest.json"
        if manifest_file.exists():
            import json
            with open(manifest_file, "r") as f:
                manifest = json.load(f)
            manifest["path"] = str(entry)
            manifest["name"] = entry.name
            backups.append(manifest)
        else:
            backups.append({
                "name": entry.name,
                "path": str(entry),
            })

    return backups
