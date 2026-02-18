"""Starter prompt management for CursorHub projects."""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from cursorhub.config import CONFIG_DIR


PROMPTS_DIR = CONFIG_DIR / "prompts"
_TAXONOMY_FILE = CONFIG_DIR / "taxonomy.json"

# Legacy directory for backward-compat migration
_LEGACY_TEMPLATES_DIR = CONFIG_DIR / "templates"

# Frontmatter regex: matches --- ... --- block at the start of a file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse optional YAML-style frontmatter from a prompt file.

    Returns (metadata_dict, body_without_frontmatter).
    Supports simple key: value pairs only (no nested YAML).
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw = match.group(1)
    body = text[match.end():]
    meta: dict[str, str] = {}
    for line in raw.strip().split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
    return meta, body


def _build_frontmatter(meta: dict[str, str]) -> str:
    """Build a frontmatter block string from a metadata dict.

    Only includes non-empty values. Returns empty string if no metadata.
    """
    lines = []
    for key, value in meta.items():
        if value:
            lines.append(f"{key}: {value}")
    if not lines:
        return ""
    return "---\n" + "\n".join(lines) + "\n---\n"


def _set_meta_field(content: str, field: str, value: str) -> str:
    """Set or update a single field in the frontmatter of a prompt's content."""
    meta, body = _parse_frontmatter(content)
    if value:
        meta[field] = value
    elif field in meta:
        del meta[field]
    fm = _build_frontmatter(meta)
    return fm + body


def _set_category_in_content(content: str, category: str) -> str:
    """Set or update the category in the frontmatter of a prompt's content."""
    return _set_meta_field(content, "category", category)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _migrate_templates_to_prompts() -> None:
    """One-time migration: copy .md files from ~/.cursorhub/templates/ to ~/.cursorhub/prompts/.

    Non-destructive — does not delete the old templates directory.
    """
    if _LEGACY_TEMPLATES_DIR.exists() and not PROMPTS_DIR.exists():
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        for f in _LEGACY_TEMPLATES_DIR.glob("*.md"):
            dest = PROMPTS_DIR / f.name
            if not dest.exists():
                shutil.copy2(f, dest)
        # Also migrate .history/ if it exists
        legacy_history = _LEGACY_TEMPLATES_DIR / ".history"
        if legacy_history.exists():
            new_history = PROMPTS_DIR / ".history"
            if not new_history.exists():
                shutil.copytree(legacy_history, new_history)


def ensure_prompts_dir() -> Path:
    """Create prompts directory if it doesn't exist, migrating legacy templates first."""
    _migrate_templates_to_prompts()
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROMPTS_DIR


# ---------------------------------------------------------------------------
# Taxonomy persistence (environments & categories survive even if no prompt uses them)
# ---------------------------------------------------------------------------

def _load_taxonomy() -> dict:
    """Load the taxonomy file (environments and categories lists)."""
    if _TAXONOMY_FILE.exists():
        try:
            return json.loads(_TAXONOMY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"environments": [], "categories": []}


def _save_taxonomy(data: dict) -> None:
    """Save the taxonomy file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _TAXONOMY_FILE.write_text(json.dumps(data, indent=2))


def add_environment(name: str) -> None:
    """Add a new environment to the persistent taxonomy."""
    tax = _load_taxonomy()
    if name not in tax["environments"]:
        tax["environments"].append(name)
        tax["environments"].sort()
        _save_taxonomy(tax)


def remove_environment(name: str) -> None:
    """Remove an environment from the persistent taxonomy."""
    tax = _load_taxonomy()
    if name in tax["environments"]:
        tax["environments"].remove(name)
        _save_taxonomy(tax)


def add_category(name: str) -> None:
    """Add a new category to the persistent taxonomy."""
    tax = _load_taxonomy()
    if name not in tax["categories"]:
        tax["categories"].append(name)
        tax["categories"].sort()
        _save_taxonomy(tax)


def remove_category(name: str) -> None:
    """Remove a category from the persistent taxonomy."""
    tax = _load_taxonomy()
    if name in tax["categories"]:
        tax["categories"].remove(name)
        _save_taxonomy(tax)


# ---------------------------------------------------------------------------
# Listing / reading
# ---------------------------------------------------------------------------

def list_prompts() -> list[dict[str, str]]:
    """List all available starter prompts.

    Returns list of dicts with 'name', 'filename', 'path', 'preview',
    'environment', 'category'.
    """
    ensure_prompts_dir()
    prompts = []
    for f in sorted(PROMPTS_DIR.glob("*.md")):
        raw_content = f.read_text().strip()
        meta, body = _parse_frontmatter(raw_content)
        category = meta.get("category", "")
        environment = meta.get("environment", "")

        lines = body.split("\n")
        title = f.stem.replace("-", " ").replace("_", " ").title()
        preview = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
            elif stripped and not stripped.startswith("#"):
                preview = stripped[:120]
                break

        prompts.append({
            "name": title,
            "filename": f.name,
            "path": str(f),
            "preview": preview,
            "environment": environment,
            "category": category,
        })
    return prompts


def list_environments() -> list[str]:
    """Return a sorted list of all known environments (from prompts + taxonomy)."""
    envs = set()
    for p in list_prompts():
        env = p.get("environment", "")
        if env:
            envs.add(env)
    tax = _load_taxonomy()
    envs.update(tax.get("environments", []))
    return sorted(envs)


def list_categories() -> list[str]:
    """Return a sorted list of all known categories (from prompts + taxonomy)."""
    cats = set()
    for p in list_prompts():
        cat = p.get("category", "")
        if cat:
            cats.add(cat)
    tax = _load_taxonomy()
    cats.update(tax.get("categories", []))
    return sorted(cats)


def get_prompt(filename: str) -> Optional[str]:
    """Read a starter prompt's full content by filename (including frontmatter)."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text()
    return None


def get_prompt_body(filename: str) -> Optional[str]:
    """Read a starter prompt's body content (without frontmatter) by filename."""
    content = get_prompt(filename)
    if content is None:
        return None
    _, body = _parse_frontmatter(content)
    return body


def get_prompt_metadata(filename: str) -> dict[str, str]:
    """Read a starter prompt's frontmatter metadata by filename."""
    content = get_prompt(filename)
    if content is None:
        return {}
    meta, _ = _parse_frontmatter(content)
    return meta


# ---------------------------------------------------------------------------
# Creating / editing / deleting
# ---------------------------------------------------------------------------

def create_prompt(name: str, content: str, category: str = "",
                   environment: str = "") -> Path:
    """Create a new starter prompt file. Returns the path.

    If category/environment are provided, they're stored in the frontmatter.
    """
    ensure_prompts_dir()
    filename = name.lower().replace(" ", "-").replace("_", "-")
    if not filename.endswith(".md"):
        filename += ".md"
    path = PROMPTS_DIR / filename

    # Add metadata frontmatter if provided
    if environment:
        content = _set_meta_field(content, "environment", environment)
    if category:
        content = _set_meta_field(content, "category", category)

    path.write_text(content)

    from cursorhub.analytics import log_event
    log_event("prompt_created", prompt_filename=filename,
              category=category, environment=environment)

    return path


def edit_prompt(filename: str, new_content: str) -> Path:
    """Edit an existing starter prompt, saving the old version for history."""
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Starter prompt not found: {filename}")

    # Save a versioned backup before editing
    history_dir = PROMPTS_DIR / ".history" / path.stem
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = history_dir / f"{path.stem}_{timestamp}.md"

    # Compute diff size for analytics
    old_content = path.read_text()
    diff_chars = abs(len(new_content) - len(old_content))

    shutil.copy2(path, backup_path)

    # Write the new content
    path.write_text(new_content)

    from cursorhub.analytics import log_event
    log_event("prompt_edited", prompt_filename=filename, diff_chars=diff_chars)

    return path


def set_prompt_category(filename: str, category: str) -> Path:
    """Change the category of an existing prompt (preserves body, updates frontmatter)."""
    content = get_prompt(filename)
    if content is None:
        raise FileNotFoundError(f"Starter prompt not found: {filename}")
    new_content = _set_category_in_content(content, category)
    # Don't create a history entry just for a category change
    path = PROMPTS_DIR / filename
    path.write_text(new_content)
    return path


def set_prompt_environment(filename: str, environment: str) -> Path:
    """Change the environment of an existing prompt (preserves body, updates frontmatter)."""
    content = get_prompt(filename)
    if content is None:
        raise FileNotFoundError(f"Starter prompt not found: {filename}")
    new_content = _set_meta_field(content, "environment", environment)
    path = PROMPTS_DIR / filename
    path.write_text(new_content)
    return path


def rename_category(old_name: str, new_name: str) -> int:
    """Rename a category across all prompts that use it. Returns count of updated prompts."""
    count = 0
    for p in list_prompts():
        if p.get("category", "") == old_name:
            set_prompt_category(p["filename"], new_name)
            count += 1
    # Update taxonomy
    remove_category(old_name)
    add_category(new_name)
    return count


def rename_environment(old_name: str, new_name: str) -> int:
    """Rename an environment across all prompts that use it. Returns count of updated prompts."""
    count = 0
    for p in list_prompts():
        if p.get("environment", "") == old_name:
            set_prompt_environment(p["filename"], new_name)
            count += 1
    # Update taxonomy
    remove_environment(old_name)
    add_environment(new_name)
    return count


def rename_prompt(old_filename: str, new_name: str) -> str:
    """Rename a starter prompt.

    Updates the filename AND the # heading inside the file.
    History directory is also renamed.
    Returns the new filename.
    """
    old_path = PROMPTS_DIR / old_filename
    if not old_path.exists():
        raise FileNotFoundError(f"Starter prompt not found: {old_filename}")

    # Derive new filename from new_name
    new_filename = new_name.lower().replace(" ", "-").replace("_", "-")
    if not new_filename.endswith(".md"):
        new_filename += ".md"
    new_path = PROMPTS_DIR / new_filename

    if new_path.exists() and new_path != old_path:
        raise FileExistsError(f"A prompt named '{new_filename}' already exists.")

    # Update the # heading inside the file content
    content = old_path.read_text()
    meta, body = _parse_frontmatter(content)

    # Replace the first # heading, or add one
    lines = body.split("\n")
    heading_replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith("# "):
            lines[i] = f"# {new_name}"
            heading_replaced = True
            break
    if not heading_replaced:
        lines.insert(0, f"# {new_name}\n")
    body = "\n".join(lines)
    new_content = _build_frontmatter(meta) + body
    old_path.write_text(new_content)

    # Rename the file
    if new_path != old_path:
        old_path.rename(new_path)

        # Rename history directory if it exists
        old_hist = PROMPTS_DIR / ".history" / old_path.stem
        new_hist = PROMPTS_DIR / ".history" / new_path.stem
        if old_hist.exists() and not new_hist.exists():
            old_hist.rename(new_hist)

    return new_filename


def delete_prompt(filename: str) -> None:
    """Delete a starter prompt file. History is preserved."""
    path = PROMPTS_DIR / filename
    if path.exists():
        path.unlink()
        from cursorhub.analytics import log_event
        log_event("prompt_deleted", prompt_filename=filename)


def get_prompt_history(filename: str) -> list[dict[str, Any]]:
    """Get the edit history for a starter prompt.

    Returns list of dicts with 'filename', 'path', 'timestamp', 'size'.
    Most recent first.
    """
    stem = Path(filename).stem
    history_dir = PROMPTS_DIR / ".history" / stem
    if not history_dir.exists():
        return []

    history = []
    for f in sorted(history_dir.glob("*.md"), reverse=True):
        # Parse timestamp from filename like "my-prompt_20260212_143055.md"
        name_parts = f.stem.split("_")
        if len(name_parts) >= 3:
            ts_str = f"{name_parts[-2]}_{name_parts[-1]}"
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                display_ts = dt.strftime("%b %d, %Y at %I:%M %p")
            except ValueError:
                display_ts = ts_str
        else:
            display_ts = f.stem

        history.append({
            "filename": f.name,
            "path": str(f),
            "timestamp": display_ts,
            "size": f.stat().st_size,
        })
    return history


def get_history_content(filename: str, history_filename: str) -> Optional[str]:
    """Read the content of a specific history version."""
    stem = Path(filename).stem
    path = PROMPTS_DIR / ".history" / stem / history_filename
    if path.exists():
        return path.read_text()
    return None


def restore_history_version(filename: str, history_filename: str) -> Path:
    """Restore a prompt from a history version.

    Saves the current version to history first, then overwrites with the old version.
    """
    # Save current version to history first
    edit_prompt(filename, get_prompt(filename) or "")

    # Read the history version and overwrite
    content = get_history_content(filename, history_filename)
    if content is None:
        raise FileNotFoundError(f"History version not found: {history_filename}")

    path = PROMPTS_DIR / filename
    path.write_text(content)

    from cursorhub.analytics import log_event
    log_event("history_restored", prompt_filename=filename,
              history_version=history_filename)

    return path


# ---------------------------------------------------------------------------
# Template variables
# ---------------------------------------------------------------------------

_VARIABLE_RE = re.compile(r"\{\{(\w+)\}\}")


def parse_variables(content: str) -> list[str]:
    """Find all unique {{variable_name}} placeholders in content.

    Returns variable names in order of first appearance, deduplicated.
    """
    seen = set()
    result = []
    for match in _VARIABLE_RE.finditer(content):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def fill_variables(content: str, values: dict[str, str]) -> str:
    """Replace all {{variable_name}} placeholders with their values.

    Any variable not in the values dict is left as-is.
    """
    def replacer(match):
        name = match.group(1)
        return values.get(name, match.group(0))
    return _VARIABLE_RE.sub(replacer, content)


# ---------------------------------------------------------------------------
# Applying to projects
# ---------------------------------------------------------------------------

def apply_prompt_to_project(prompt_filename: str, project_path: str,
                            variables: Optional[dict[str, str]] = None) -> str:
    """Apply a starter prompt to a project.

    - If variables dict is provided, substitutes {{name}} placeholders first
    - Saves the prompt as a Cursor rule file in the project (.cursor/rules/)
    - Returns the (substituted) prompt body content (caller can copy to clipboard)
    """
    body = get_prompt_body(prompt_filename)
    if body is None:
        raise FileNotFoundError(f"Starter prompt not found: {prompt_filename}")

    # Substitute template variables if provided
    if variables:
        body = fill_variables(body, variables)

    project = Path(project_path)
    project.mkdir(parents=True, exist_ok=True)

    # Save as a Cursor rule so it's always available in chats
    rules_dir = project / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)

    rule_file = rules_dir / "project-prompt.mdc"
    rule_content = f"""---
description: Project setup prompt and instructions
globs:
alwaysApply: true
---

{body}
"""
    rule_file.write_text(rule_content)

    from cursorhub.analytics import log_event
    var_names = list(variables.keys()) if variables else []
    log_event("prompt_applied", prompt_filename=prompt_filename,
              project_path=project_path, variable_names=var_names)

    return body
