"""Command-line interface for CursorHub."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from cursorhub import __version__
from cursorhub.config import (
    add_project,
    archive_project,
    auto_discover_projects,
    delete_project,
    load_config,
    remove_project,
    unarchive_project,
)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="cursorhub",
        description="Manage your Cursor IDE projects, chat history, and workspaces.",
    )
    parser.add_argument(
        "--version", action="version", version=f"cursorhub {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- run (start menu bar app) ---
    subparsers.add_parser("run", help="Start the CursorHub menu bar app")

    # --- list ---
    subparsers.add_parser("list", help="List all registered projects")

    # --- add ---
    add_parser = subparsers.add_parser("add", help="Add a project")
    add_parser.add_argument("path", help="Path to the project folder")
    add_parser.add_argument("--name", help="Display name (default: folder name)")
    add_parser.add_argument("--repo", default="", help="GitHub repo URL")

    # --- remove ---
    rm_parser = subparsers.add_parser("remove", help="Remove a project from CursorHub")
    rm_parser.add_argument("path", help="Path to the project folder")

    # --- archive ---
    archive_parser = subparsers.add_parser("archive", help="Archive a project")
    archive_parser.add_argument("path", help="Path to the project folder")

    # --- unarchive ---
    unarchive_parser = subparsers.add_parser("unarchive", help="Restore an archived project")
    unarchive_parser.add_argument("path", help="Path to the project folder")

    # --- delete ---
    delete_parser = subparsers.add_parser("delete", help="Permanently delete a project")
    delete_parser.add_argument("path", help="Path to the project folder")
    delete_parser.add_argument(
        "--files", action="store_true",
        help="Also delete the project folder and all its files from disk",
    )

    # --- scan ---
    subparsers.add_parser("scan", help="Auto-discover projects from Cursor's workspace storage")

    # --- open ---
    open_parser = subparsers.add_parser("open", help="Open a project in Cursor")
    open_parser.add_argument("name_or_path", help="Project name or path")

    # --- backup ---
    backup_parser = subparsers.add_parser("backup", help="Backup Cursor chat history")
    backup_parser.add_argument("--label", default="", help="Optional label for the backup")

    # --- backups ---
    subparsers.add_parser("backups", help="List all backups")

    # --- prompts ---
    subparsers.add_parser("prompts", help="List available starter prompts")

    # --- tour ---
    subparsers.add_parser("tour", help="Take a guided tour of CursorHub")

    # --- stats ---
    subparsers.add_parser("stats", help="Show analytics and usage statistics")

    # --- analyze ---
    analyze_parser = subparsers.add_parser("analyze", help="AI-powered analysis of prompts and usage (requires Gemini API key)")
    analyze_parser.add_argument("--prompt", "-p", help="Analyze a specific prompt by filename")

    # --- config ---
    config_parser = subparsers.add_parser("config", help="View or set configuration values")
    config_parser.add_argument("action", choices=["get", "set", "list"], help="Action to perform")
    config_parser.add_argument("key", nargs="?", help="Config key name")
    config_parser.add_argument("value", nargs="?", help="Value to set (for 'set' action)")

    # --- templates (deprecated alias) ---
    subparsers.add_parser("templates", help="(Deprecated) Use 'cursorhub prompts' instead")

    # --- new ---
    new_parser = subparsers.add_parser("new", help="Create a new project")
    new_parser.add_argument("name", help="Project name")
    new_parser.add_argument(
        "--prompt", "-p",
        help="Starter prompt filename (run 'cursorhub prompts' to see options)",
    )
    new_parser.add_argument(
        "--clone", "-c",
        help="Git repository URL to clone",
    )
    new_parser.add_argument(
        "--dir", default=".",
        help="Parent directory (default: current dir)",
    )
    # Keep --template as hidden alias for backward compat
    new_parser.add_argument("--template", "-t", help=argparse.SUPPRESS)

    args = parser.parse_args()

    if args.command is None:
        # Default: start the menu bar app
        _cmd_run()
        return

    commands = {
        "run": _cmd_run,
        "list": _cmd_list,
        "add": lambda: _cmd_add(args),
        "remove": lambda: _cmd_remove(args),
        "archive": lambda: _cmd_archive(args),
        "unarchive": lambda: _cmd_unarchive(args),
        "delete": lambda: _cmd_delete(args),
        "scan": _cmd_scan,
        "open": lambda: _cmd_open(args),
        "backup": lambda: _cmd_backup(args),
        "backups": _cmd_backups,
        "prompts": _cmd_prompts,
        "stats": _cmd_stats,
        "analyze": lambda: _cmd_analyze(args),
        "config": lambda: _cmd_config(args),
        "tour": _cmd_tour,
        "templates": _cmd_templates_deprecated,
        "new": lambda: _cmd_new(args),
    }

    cmd_fn = commands.get(args.command)
    if cmd_fn:
        cmd_fn()
    else:
        parser.print_help()


def _cmd_run():
    """Start the menu bar app."""
    from cursorhub.app import run
    run()


def _cmd_list():
    """List all registered projects."""
    config = load_config()
    projects = config.get("projects", [])
    archived = config.get("archived_projects", [])

    if not projects and not archived:
        print("No projects registered. Run 'cursorhub scan' to auto-discover.")
        return

    if projects:
        print(f"\n  CursorHub Projects ({len(projects)})")
        print(f"  {'=' * 50}")
        for p in projects:
            name = p["name"]
            path = p["path"]
            repo = p.get("repo", "")
            exists = Path(path).exists()
            status = "OK" if exists else "MISSING"
            print(f"  [{status}] {name}")
            print(f"         {path}")
            if repo:
                print(f"         {repo}")
    else:
        print("\n  No active projects.")

    if archived:
        print(f"\n  Archived Projects ({len(archived)})")
        print(f"  {'-' * 50}")
        for p in archived:
            name = p["name"]
            path = p["path"]
            exists = Path(path).exists()
            status = "OK" if exists else "MISSING"
            print(f"  [{status}] {name}")
            print(f"         {path}")

    print()


def _cmd_add(args):
    """Add a project."""
    path = str(Path(args.path).expanduser().resolve())
    name = args.name or Path(path).name.replace("-", " ").replace("_", " ").title()

    if not Path(path).exists():
        print(f"Warning: Path does not exist: {path}")

    add_project(name, path, args.repo)
    print(f"Added: {name} -> {path}")


def _cmd_remove(args):
    """Remove a project from CursorHub (does not delete files)."""
    path = str(Path(args.path).expanduser().resolve())
    remove_project(path)
    print(f"Removed: {path}")


def _cmd_archive(args):
    """Archive a project."""
    path = str(Path(args.path).expanduser().resolve())
    archive_project(path)
    print(f"Archived: {path}")
    print("Use 'cursorhub unarchive' to restore it.")


def _cmd_unarchive(args):
    """Restore an archived project."""
    path = str(Path(args.path).expanduser().resolve())
    unarchive_project(path)
    print(f"Restored: {path}")


def _cmd_delete(args):
    """Permanently delete a project with confirmation."""
    path = str(Path(args.path).expanduser().resolve())

    config = load_config()
    all_projects = config.get("projects", []) + config.get("archived_projects", [])
    project = next((p for p in all_projects if p["path"] == path), None)
    name = project["name"] if project else Path(path).name

    if args.files:
        print(f"\n  WARNING: This will permanently delete \"{name}\" AND all files in:")
        print(f"  {path}\n")
        try:
            confirm = input("  Type the project name to confirm: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if confirm != name:
            print(f"  Names don't match. Expected \"{name}\". Cancelled.")
            return
        delete_project(path, delete_files=True)
        print(f"  Deleted: {name} (files removed from disk)")
    else:
        try:
            confirm = input(f"  Remove \"{name}\" from CursorHub? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if confirm not in ("y", "yes"):
            print("  Cancelled.")
            return
        delete_project(path, delete_files=False)
        print(f"  Removed: {name} (files untouched)")


def _cmd_scan():
    """Auto-discover projects."""
    print("Scanning Cursor workspace storage...")
    discovered = auto_discover_projects()
    config = load_config()
    existing_paths = {p["path"] for p in config.get("projects", [])}

    added = 0
    for project in discovered:
        if project["path"] not in existing_paths:
            add_project(project["name"], project["path"])
            print(f"  + {project['name']} ({project['path']})")
            added += 1
        else:
            print(f"  . {project['name']} (already registered)")

    if added:
        print(f"\nAdded {added} project(s).")
    else:
        print("\nNo new projects found.")


def _cmd_open(args):
    """Open a project in Cursor."""
    config = load_config()
    cursor_app = config.get("cursor_app", "/Applications/Cursor.app")

    target = args.name_or_path.lower()
    for p in config.get("projects", []):
        if p["name"].lower() == target or p["path"].lower().endswith(target):
            print(f"Opening {p['name']} in Cursor...")
            subprocess.Popen(["open", "-a", cursor_app, p["path"]])
            return

    path = str(Path(args.name_or_path).expanduser().resolve())
    if Path(path).exists():
        print(f"Opening {path} in Cursor...")
        subprocess.Popen(["open", "-a", cursor_app, path])
    else:
        print(f"Project not found: {args.name_or_path}")
        print("Run 'cursorhub list' to see registered projects.")
        sys.exit(1)


def _cmd_backup(args):
    """Create a backup."""
    from cursorhub.backup import create_backup
    print("Backing up Cursor workspace data...")
    backup_dir = create_backup(label=args.label)
    print(f"Backup saved to: {backup_dir}")


def _cmd_backups():
    """List all backups."""
    from cursorhub.backup import list_backups
    backups = list_backups()
    if not backups:
        print("No backups found. Run 'cursorhub backup' to create one.")
        return
    print(f"\n  CursorHub Backups ({len(backups)})")
    print(f"  {'=' * 50}")
    for b in backups:
        name = b.get("name", "unknown")
        ws = b.get("workspaces_backed_up", "?")
        total = b.get("total_bytes", 0)
        size_mb = total / (1024 * 1024) if total else 0
        print(f"  {name}  ({ws} workspaces, {size_mb:.1f} MB)")
    print()


def _cmd_prompts():
    """List available starter prompts."""
    from cursorhub.prompts import list_prompts, PROMPTS_DIR
    prompts = list_prompts()
    if not prompts:
        print(f"No starter prompts found. Add .md files to {PROMPTS_DIR}")
        return
    print(f"\n  CursorHub Starter Prompts ({len(prompts)})")
    print(f"  {'=' * 50}")
    for p in prompts:
        print(f"  {p['filename']}")
        print(f"    {p['name']}")
        if p["preview"]:
            print(f"    {p['preview']}")
    print(f"\n  Prompts folder: {PROMPTS_DIR}")
    print(f"  Edit any .md file there to customize.\n")


def _cmd_stats():
    """Show analytics and usage statistics."""
    from cursorhub.analytics import (
        get_overall_stats, get_all_prompt_stats, get_recent_activity,
        compute_prompt_health,
    )
    from cursorhub.prompts import list_prompts

    overall = get_overall_stats()
    all_stats = get_all_prompt_stats()
    activity = get_recent_activity(10)
    prompts = list_prompts()

    name_map = {p["filename"]: p["name"] for p in prompts}

    print(f"\n  CursorHub Analytics")
    print(f"  {'=' * 50}")
    print(f"  Projects created:      {overall['total_projects_created']}")
    print(f"  Prompts applied:       {overall['total_prompt_applications']}")
    print(f"  Unique prompts used:   {overall['total_prompts_used']}")
    if overall["most_used_prompt"]:
        most_name = name_map.get(overall["most_used_prompt"],
                                  overall["most_used_prompt"])
        print(f"  Most used prompt:      {most_name}")
    if overall["avg_rating_all"] is not None:
        print(f"  Overall avg rating:    {overall['avg_rating_all']}/4")
    print(f"  Events (last 30 days): {overall['events_last_30_days']}")

    # Prompt health
    if prompts:
        print(f"\n  Prompt Health")
        print(f"  {'-' * 50}")
        for p in prompts:
            fn = p["filename"]
            stats = all_stats.get(fn, {
                "times_used": 0, "last_used": None, "avg_rating": None,
                "rating_count": 0, "edit_count": 0, "projects": [],
            })
            health = compute_prompt_health(stats)
            icon = {"great": "\u2605", "good": "\u2713", "needs_attention": "\u26a0",
                    "unused": "\u25cb", "new": "\u25cf"}.get(health, "?")
            used = stats.get("times_used", 0)
            rating = stats.get("avg_rating")
            detail = f"used {used}x"
            if rating is not None:
                detail += f", {rating}/4"
            print(f"  {icon} {p['name']}: {health.replace('_', ' ')} ({detail})")

    # Recent activity
    if activity:
        print(f"\n  Recent Activity")
        print(f"  {'-' * 50}")
        for evt in activity:
            from datetime import datetime
            try:
                ts = datetime.fromisoformat(evt["timestamp"]).strftime("%b %d %H:%M")
            except Exception:
                ts = evt["timestamp"][:16]
            event_name = evt["event"].replace("_", " ").title()
            detail = ""
            if evt.get("prompt_filename"):
                pname = name_map.get(evt["prompt_filename"], evt["prompt_filename"])
                detail = f" — {pname}"
            elif evt.get("project_path"):
                detail = f" — {Path(evt['project_path']).name}"
            print(f"  {ts}  {event_name}{detail}")

    print()


def _cmd_config(args):
    """View or set configuration values."""
    from cursorhub.config import get_config_value, set_config_value, load_config

    # Sensitive keys that should be partially masked when displayed
    sensitive_keys = {"gemini_api_key"}

    if args.action == "list":
        config = load_config()
        print(f"\n  CursorHub Configuration")
        print(f"  {'=' * 50}")
        for k, v in sorted(config.items()):
            if k in ("projects", "archived_projects"):
                print(f"  {k}: [{len(v)} items]")
            elif k in sensitive_keys and v:
                print(f"  {k}: {str(v)[:8]}...{str(v)[-4:]}")
            else:
                print(f"  {k}: {v}")
        print()

    elif args.action == "get":
        if not args.key:
            print("Error: 'get' requires a key name. Run 'cursorhub config list' to see all keys.")
            sys.exit(1)
        val = get_config_value(args.key)
        if val is None:
            print(f"  {args.key}: (not set)")
        elif args.key in sensitive_keys:
            print(f"  {args.key}: {str(val)[:8]}...{str(val)[-4:]}")
        else:
            print(f"  {args.key}: {val}")

    elif args.action == "set":
        if not args.key or args.value is None:
            print("Error: 'set' requires a key and value. Example: cursorhub config set gemini_api_key YOUR_KEY")
            sys.exit(1)
        set_config_value(args.key, args.value)
        if args.key in sensitive_keys:
            print(f"  Set {args.key}: {args.value[:8]}...{args.value[-4:]}")
        else:
            print(f"  Set {args.key}: {args.value}")


def _cmd_analyze(args):
    """Run AI-powered analysis using Gemini."""
    from cursorhub.config import get_config_value
    api_key = get_config_value("gemini_api_key")
    if not api_key:
        print("Error: No Gemini API key configured.")
        print("Set one with: cursorhub config set gemini_api_key YOUR_KEY")
        sys.exit(1)

    from cursorhub.ai_analysis import analyze_prompt, analyze_overview

    if args.prompt:
        filename = args.prompt
        if not filename.endswith(".md"):
            filename += ".md"
        print(f"\n  Analyzing prompt: {filename}")
        print(f"  Calling Gemini...\n")
        result = analyze_prompt(filename, api_key)
        print(result)
    else:
        print(f"\n  Running full portfolio analysis...")
        print(f"  Calling Gemini...\n")
        result = analyze_overview(api_key)
        print(result)


def _cmd_tour():
    """Launch the guided tour of CursorHub."""
    print("Launching CursorHub tour...")
    print("(The tour window will open. Close it when you're done.)")

    import AppKit
    from cursorhub.tour import TourWindowController

    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)

    controller = TourWindowController.alloc().init()
    controller.showWindow()

    # Run the event loop until the tour window is closed
    app.run()


def _cmd_templates_deprecated():
    """Deprecated: redirect to prompts command."""
    print("Note: 'cursorhub templates' has been renamed to 'cursorhub prompts'.")
    print()
    _cmd_prompts()


def _collect_variables(prompt_filename):
    """Check a prompt for template variables and interactively collect values.

    Returns a dict of {var_name: value}, or None if no variables.
    """
    from cursorhub.prompts import get_prompt_body, parse_variables
    body = get_prompt_body(prompt_filename)
    if body is None:
        return None
    var_names = parse_variables(body)
    if not var_names:
        return None

    print(f"\n  This prompt has {len(var_names)} template variable(s) to fill in:")
    variables = {}
    for var in var_names:
        label = var.replace("_", " ").title()
        try:
            val = input(f"  {label} ({var}): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(1)
        variables[var] = val if val else "{{" + var + "}}"
    print()
    return variables


def _cmd_new(args):
    """Create a new project (from starter prompt, git clone, or blank)."""
    from cursorhub.prompts import list_prompts, apply_prompt_to_project

    config = load_config()
    cursor_app = config.get("cursor_app", "/Applications/Cursor.app")

    # Resolve parent directory
    parent = Path(args.dir).expanduser().resolve()

    # Resolve backward-compat --template -> --prompt
    prompt_file = args.prompt or args.template
    clone_url = args.clone

    # Determine the project folder
    folder_name = args.name.lower().replace(" ", "-").replace("_", "-")
    project_path = str(parent / folder_name)

    # --- Clone mode ---
    if clone_url:
        # Convert SSH URLs to HTTPS so gh credential helper works
        ssh_match = re.match(r"^git@([^:]+):(.+)$", clone_url)
        if ssh_match:
            clone_url = f"https://{ssh_match.group(1)}/{ssh_match.group(2)}"
            print(f"Converted to HTTPS: {clone_url}")
        print(f"Cloning {clone_url}...")
        result = subprocess.run(
            ["git", "clone", clone_url, project_path],
            capture_output=False, timeout=120,
        )
        if result.returncode != 0:
            print("Error: git clone failed.")
            sys.exit(1)
        print(f"Cloned to {project_path}")

    # --- Prompt / blank mode ---
    else:
        Path(project_path).mkdir(parents=True, exist_ok=True)

    # Apply starter prompt if specified
    if prompt_file:
        if not prompt_file.endswith(".md"):
            prompt_file += ".md"
        variables = _collect_variables(prompt_file)
        prompt_content = apply_prompt_to_project(prompt_file, project_path,
                                                  variables=variables)
        subprocess.run(["pbcopy"], input=prompt_content.encode(), check=True)
        print("Starter prompt applied and copied to clipboard.")
    elif not clone_url:
        # No prompt specified and not cloning — offer interactive pick
        prompts = list_prompts()
        if prompts:
            print("\nAvailable starter prompts:")
            for i, p in enumerate(prompts, 1):
                print(f"  {i}. {p['name']} ({p['filename']})")
            print()
            try:
                choice = input("Pick a starter prompt number (or Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                choice = ""
            if choice and choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(prompts):
                    variables = _collect_variables(prompts[idx]["filename"])
                    prompt_content = apply_prompt_to_project(
                        prompts[idx]["filename"], project_path,
                        variables=variables,
                    )
                    subprocess.run(["pbcopy"], input=prompt_content.encode(), check=True)
                    print("Starter prompt applied and copied to clipboard.")
                else:
                    print("Invalid choice — skipping starter prompt.")

    # Register project
    display_name = args.name.replace("-", " ").replace("_", " ").title()
    add_project(display_name, project_path)
    print(f"Created: {display_name} -> {project_path}")

    # Open in Cursor
    subprocess.Popen(["open", "-a", cursor_app, project_path])
    print("Opening in Cursor...")
    if prompt_file or (not clone_url):
        print("Paste the clipboard into your first chat to get started!")


if __name__ == "__main__":
    main()
