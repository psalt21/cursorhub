"""CursorHub - macOS menu bar app for managing Cursor IDE projects."""

import subprocess
from pathlib import Path

import objc
import rumps
from Foundation import NSObject

from cursorhub.backup import create_backup, list_backups
from cursorhub.config import (
    add_project,
    archive_project,
    auto_discover_projects,
    delete_project,
    list_cursor_profiles,
    load_config,
    open_in_cursor,
    remove_project,
    save_config,
    set_project_ports,
    set_project_profile,
    unarchive_project,
)
from cursorhub.prompts import PROMPTS_DIR


class _DeferHelper(NSObject):
    """Tiny helper to run a Python callable after a delay on the main thread."""

    def initWithCallback_(self, callback):
        self = objc.super(_DeferHelper, self).init()
        if self is None:
            return None
        self._callback = callback
        return self

    @objc.typedSelector(b"v@:@")
    def fire_(self, timer):
        if self._callback:
            self._callback()


class CursorHubApp(rumps.App):
    """Menu bar application for managing Cursor IDE projects."""

    def __init__(self):
        # Locate the menu bar icon from the package resources
        icon_path = str(Path(__file__).parent / "resources" / "icon.png")
        if Path(icon_path).exists():
            super().__init__("CursorHub", icon=icon_path, quit_button=None, template=True)
        else:
            # Fallback to text if icon file is missing
            super().__init__("CursorHub", title="\u2732", quit_button=None)
        self.config = load_config()
        self._picker_controller = None
        self._manager_controller = None
        self._tour_controller = None
        self._deferred_helpers = []  # prevent GC of deferred action helpers
        self._build_menu()

    def _build_menu(self):
        """Build the menu from current config."""
        self.menu.clear()

        # Active projects section
        projects = self.config.get("projects", [])
        archived = self.config.get("archived_projects", [])

        if projects:
            self.menu.add(rumps.MenuItem("--- Projects ---", callback=None))
            for project in projects:
                name = project["name"]
                path = project["path"]
                exists = Path(path).exists()
                profile = project.get("cursor_profile", "")
                profile_badge = f"  [{profile}]" if profile else ""
                label = (name if exists else f"{name}  (missing)") + profile_badge

                sub = rumps.MenuItem(label)

                open_item = rumps.MenuItem("Open in Cursor", callback=self._open_project)
                open_item._project_path = path
                sub.add(open_item)

                sub.add(rumps.separator)

                profile_item = rumps.MenuItem(
                    f"Profile: {profile or 'Default'}  ▸ Change...",
                    callback=self._change_profile
                )
                profile_item._project_path = path
                profile_item._project_name = name
                sub.add(profile_item)

                # Ports
                ports = project.get("ports", {})
                if ports:
                    port_summary = "  ".join(
                        f"{k.replace('_port','').title()}:{v}"
                        for k, v in sorted(ports.items())
                    )
                    ports_item = rumps.MenuItem(
                        f"Ports: {port_summary}  ▸ Edit...",
                        callback=self._edit_ports
                    )
                else:
                    ports_item = rumps.MenuItem(
                        "Ports: none  ▸ Add...",
                        callback=self._edit_ports
                    )
                ports_item._project_path = path
                ports_item._project_name = name
                sub.add(ports_item)

                sub.add(rumps.separator)

                archive_item = rumps.MenuItem("Archive", callback=self._archive_project)
                archive_item._project_path = path
                archive_item._project_name = name
                sub.add(archive_item)

                delete_item = rumps.MenuItem("Delete...", callback=self._delete_project)
                delete_item._project_path = path
                delete_item._project_name = name
                sub.add(delete_item)

                self.menu.add(sub)
        else:
            self.menu.add(rumps.MenuItem("No projects yet", callback=None))

        # Archived projects section
        if archived:
            self.menu.add(rumps.separator)
            archive_sub = rumps.MenuItem(f"Archived ({len(archived)})")
            for project in archived:
                name = project["name"]
                path = project["path"]

                item_sub = rumps.MenuItem(name)

                unarchive_item = rumps.MenuItem("Unarchive", callback=self._unarchive_project)
                unarchive_item._project_path = path
                unarchive_item._project_name = name
                item_sub.add(unarchive_item)

                delete_item = rumps.MenuItem("Delete...", callback=self._delete_project)
                delete_item._project_path = path
                delete_item._project_name = name
                item_sub.add(delete_item)

                archive_sub.add(item_sub)

            self.menu.add(archive_sub)

        self.menu.add(rumps.separator)

        # Feedback section — show if there are prompts needing feedback
        try:
            from cursorhub.analytics import get_pending_feedback, log_event
            pending = get_pending_feedback()
            if pending:
                self.menu.add(rumps.MenuItem("--- Feedback ---", callback=None))
                for fb in pending:
                    prompt_name = Path(fb["prompt_filename"]).stem.replace("-", " ").title()
                    project_name = fb["project_name"]

                    fb_sub = rumps.MenuItem(f"How did \"{prompt_name}\" work?")

                    for rating, label in [
                        (4, "Great, no changes needed"),
                        (3, "Good, but I tweaked it"),
                        (2, "It was okay"),
                        (1, "Not very useful"),
                        (0, "Skip"),
                    ]:
                        item = rumps.MenuItem(label, callback=self._submit_feedback)
                        item._fb_rating = rating
                        item._fb_prompt = fb["prompt_filename"]
                        item._fb_project = fb["project_path"]
                        item._fb_project_name = project_name
                        fb_sub.add(item)

                    self.menu.add(fb_sub)
                self.menu.add(rumps.separator)
        except Exception:
            pass

        # Actions
        self.menu.add(rumps.MenuItem("New Project...", callback=self._new_project))
        self.menu.add(rumps.MenuItem("Add Existing Project...", callback=self._add_project))
        self.menu.add(rumps.MenuItem("Scan for Projects", callback=self._scan_projects))
        self.menu.add(rumps.separator)

        self.menu.add(rumps.MenuItem("Manage Starter Prompts...", callback=self._open_prompt_manager))
        self.menu.add(rumps.MenuItem("Sync Prompts", callback=self._sync_prompts))
        self.menu.add(rumps.separator)

        # Settings
        from cursorhub.config import get_config_value
        gemini_key = get_config_value("gemini_api_key") or ""
        gemini_label = "Gemini API Key ✓" if gemini_key else "Set Gemini API Key..."
        self.menu.add(rumps.MenuItem(gemini_label, callback=self._set_gemini_key))
        self.menu.add(rumps.separator)

        # Backup
        self.menu.add(rumps.MenuItem("Backup History Now", callback=self._backup_now))
        self.menu.add(rumps.MenuItem("Show Backups", callback=self._show_backups))
        self.menu.add(rumps.separator)

        # Meta
        self.menu.add(rumps.MenuItem("Take a Tour...", callback=self._take_tour))
        self.menu.add(rumps.MenuItem("About CursorHub", callback=self._about))
        self.menu.add(rumps.MenuItem("Quit", callback=self._quit))

    def _defer_action(self, callback, delay=0.15):
        """Schedule a callback on the main run loop after a short delay.

        This lets the menu close before showing a modal dialog, preventing
        the app from freezing.
        """
        import AppKit

        helper = _DeferHelper.alloc().initWithCallback_(callback)
        self._deferred_helpers.append(helper)  # prevent GC
        AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            delay, helper, b"fire:", None, False
        )

    def _open_project(self, sender):
        """Open a project in Cursor, using its assigned profile if set."""
        from cursorhub.analytics import log_event
        path = sender._project_path
        try:
            open_in_cursor(path)
            log_event("project_opened", project_path=path)

            # Find profile name for the notification
            profile = ""
            for p in self.config.get("projects", []):
                if p["path"] == path:
                    profile = p.get("cursor_profile", "")
                    break
            detail = f"Profile: {profile}" if profile else path
            rumps.notification("CursorHub", f"Opening {sender.title}", detail)
        except Exception as e:
            rumps.notification("CursorHub", "Error", str(e))

    def _change_profile(self, sender):
        """Show a profile picker for a project."""
        import AppKit
        path = sender._project_path
        name = sender._project_name

        profiles = list_cursor_profiles()
        if len(profiles) <= 1:
            rumps.notification(
                "CursorHub",
                "No extra profiles found",
                "Create profiles in Cursor: File → Preferences → Profiles → New Profile",
            )
            return

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(f"Cursor Profile for \"{name}\"")
        alert.setInformativeText_(
            "Choose which Cursor profile to use when opening this project.\n\n"
            "Work and Personal profiles keep separate billing, extensions, and settings.\n\n"
            "Create profiles in Cursor: File → Preferences → Profiles → New Profile"
        )

        popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, 280, 26)
        )
        for p in profiles:
            popup.addItemWithTitle_(p["name"])

        # Pre-select the current profile
        current = ""
        for proj in self.config.get("projects", []):
            if proj["path"] == path:
                current = proj.get("cursor_profile", "")
                break
        for i, p in enumerate(profiles):
            if p["name"] == current or (not current and p["id"] == "__default__"):
                popup.selectItemAtIndex_(i)
                break

        alert.setAccessoryView_(popup)
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() == AppKit.NSAlertFirstButtonReturn:
            selected = profiles[popup.indexOfSelectedItem()]
            new_profile = "" if selected["id"] == "__default__" else selected["name"]
            self.config = set_project_profile(path, new_profile)
            self._build_menu()
            label = selected["name"] if new_profile else "Default"
            rumps.notification("CursorHub", f"Profile updated", f"{name} → {label}")

    def _archive_project(self, sender):
        """Move a project to the archive."""
        from cursorhub.analytics import log_event
        path = sender._project_path
        name = sender._project_name
        self.config = archive_project(path)
        self._build_menu()
        log_event("project_archived", project_path=path, project_name=name)
        rumps.notification("CursorHub", "Project Archived", f"{name} has been archived.")

    def _submit_feedback(self, sender):
        """Handle a feedback rating selection from the menu."""
        from cursorhub.analytics import log_event
        rating = sender._fb_rating
        prompt_fn = sender._fb_prompt
        project_path = sender._fb_project
        project_name = sender._fb_project_name

        if rating == 0:
            # Skip — log so we don't ask again
            log_event("feedback_skipped", prompt_filename=prompt_fn,
                      project_path=project_path)
        else:
            log_event("feedback_given", prompt_filename=prompt_fn,
                      project_path=project_path, rating=rating,
                      project_name=project_name)

        self._build_menu()  # Remove the feedback item

        if rating > 0:
            labels = {4: "Great", 3: "Good", 2: "Okay", 1: "Needs work"}
            rumps.notification("CursorHub", "Thanks for the feedback!",
                              f"Rated \"{Path(prompt_fn).stem.replace('-', ' ').title()}\": "
                              f"{labels.get(rating, '?')}")

    def _unarchive_project(self, sender):
        """Restore a project from the archive."""
        from cursorhub.analytics import log_event
        path = sender._project_path
        name = sender._project_name
        self.config = unarchive_project(path)
        self._build_menu()
        log_event("project_unarchived", project_path=path, project_name=name)
        rumps.notification("CursorHub", "Project Restored", f"{name} is back in your projects.")

    def _delete_project(self, sender):
        """Delete a project — defer the confirmation dialog so the menu closes first."""
        path = sender._project_path
        name = sender._project_name

        def _show_delete_dialog():
            try:
                import AppKit

                # --- Confirmation 1: What do you want to do? ---
                alert1 = AppKit.NSAlert.alloc().init()
                alert1.setMessageText_(f"Delete \"{name}\"?")
                alert1.setInformativeText_(
                    f"Path: {path}\n\n"
                    "This will remove the project from CursorHub.\n"
                    "You can also choose to delete the project files from disk."
                )
                alert1.setAlertStyle_(AppKit.NSAlertStyleWarning)
                alert1.addButtonWithTitle_("Remove from List")
                alert1.addButtonWithTitle_("Delete Files Too")
                alert1.addButtonWithTitle_("Cancel")
                alert1.buttons()[1].setHasDestructiveAction_(True)

                AppKit.NSApp.activateIgnoringOtherApps_(True)
                result1 = alert1.runModal()

                if result1 == AppKit.NSAlertFirstButtonReturn:
                    # "Remove from List" path — still confirm once more
                    # --- Confirmation 2: Are you sure? ---
                    alert2 = AppKit.NSAlert.alloc().init()
                    alert2.setMessageText_(f"Remove \"{name}\" from CursorHub?")
                    alert2.setInformativeText_(
                        "The project will be removed from your list.\n"
                        "Files on disk will NOT be deleted."
                    )
                    alert2.setAlertStyle_(AppKit.NSAlertStyleWarning)
                    alert2.addButtonWithTitle_("Yes, Remove It")
                    alert2.addButtonWithTitle_("Cancel")

                    if alert2.runModal() == AppKit.NSAlertFirstButtonReturn:
                        self.config = delete_project(path, delete_files=False)
                        self._build_menu()
                        from cursorhub.analytics import log_event
                        log_event("project_deleted", project_path=path,
                                  project_name=name, files_deleted=False)
                        rumps.notification("CursorHub", "Project Removed",
                                          f"{name} removed from CursorHub.")

                elif result1 == AppKit.NSAlertFirstButtonReturn + 1:
                    # "Delete Files Too" path — two more confirmations (3 total)

                    # --- Confirmation 2: Are you sure? ---
                    alert2 = AppKit.NSAlert.alloc().init()
                    alert2.setMessageText_("Are you sure?")
                    alert2.setInformativeText_(
                        f"This will permanently delete ALL files in:\n{path}\n\n"
                        "This action cannot be undone."
                    )
                    alert2.setAlertStyle_(AppKit.NSAlertStyleCritical)
                    alert2.addButtonWithTitle_("Yes, Delete Everything")
                    alert2.addButtonWithTitle_("Cancel")
                    alert2.buttons()[0].setHasDestructiveAction_(True)

                    if alert2.runModal() != AppKit.NSAlertFirstButtonReturn:
                        return

                    # --- Confirmation 3: Type the name to confirm ---
                    alert3 = AppKit.NSAlert.alloc().init()
                    alert3.setMessageText_("Final confirmation")
                    alert3.setInformativeText_(
                        f"Type \"{name}\" below to permanently delete this project "
                        "and all its files."
                    )
                    alert3.setAlertStyle_(AppKit.NSAlertStyleCritical)
                    alert3.addButtonWithTitle_("Delete Forever")
                    alert3.addButtonWithTitle_("Cancel")
                    alert3.buttons()[0].setHasDestructiveAction_(True)

                    field = AppKit.NSTextField.alloc().initWithFrame_(
                        AppKit.NSMakeRect(0, 0, 300, 24)
                    )
                    field.setPlaceholderString_(name)
                    alert3.setAccessoryView_(field)
                    alert3.window().setInitialFirstResponder_(field)

                    if alert3.runModal() != AppKit.NSAlertFirstButtonReturn:
                        return

                    typed = field.stringValue().strip()
                    if typed != name:
                        info = AppKit.NSAlert.alloc().init()
                        info.setMessageText_("Deletion cancelled")
                        info.setInformativeText_(
                            f"The name you typed didn't match.\n"
                            f"Expected: \"{name}\"\n"
                            f"You typed: \"{typed}\""
                        )
                        info.runModal()
                        return

                    self.config = delete_project(path, delete_files=True)
                    self._build_menu()
                    from cursorhub.analytics import log_event
                    log_event("project_deleted", project_path=path,
                              project_name=name, files_deleted=True)
                    rumps.notification(
                        "CursorHub", "Project Deleted",
                        f"{name} and all its files have been permanently deleted."
                    )

            except Exception as e:
                import traceback
                traceback.print_exc()
                rumps.notification("CursorHub", "Error", str(e))

        # Defer dialog so the menu closes first — prevents run loop freeze
        self._defer_action(_show_delete_dialog)

    def _new_project(self, _):
        """Open the New Project picker window."""
        from cursorhub.ui import NewProjectWindowController

        # Reuse existing controller if window is still alive
        if self._picker_controller is not None:
            try:
                self._picker_controller.showWindow()
                return
            except Exception:
                self._picker_controller = None

        self._picker_controller = NewProjectWindowController.alloc().init()
        self._picker_controller.on_project_created = self._on_project_created
        self._picker_controller.showWindow()

    def _on_project_created(self, name, path):
        """Callback when a project is created via the picker window."""
        self.config = load_config()
        self._build_menu()

    def _open_prompt_manager(self, _):
        """Open the Starter Prompt Manager window."""
        try:
            from cursorhub.ui import PromptManagerController
            # Reuse existing controller if window is still alive
            if self._manager_controller is not None:
                try:
                    self._manager_controller.showWindow()
                    return
                except Exception:
                    # Window was deallocated; create a new one
                    self._manager_controller = None
            self._manager_controller = PromptManagerController.alloc().init()
            self._manager_controller.showWindow()
        except Exception as e:
            import traceback
            traceback.print_exc()
            rumps.notification("CursorHub", "Error opening Prompt Manager", str(e))

    def _set_gemini_key(self, _):
        """Prompt the user to enter or update their Gemini API key."""
        from cursorhub.config import get_config_value, set_config_value
        import AppKit

        current = get_config_value("gemini_api_key") or ""

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Gemini API Key")
        alert.setInformativeText_(
            "Enter your Google Gemini API key to enable AI-powered prompt analysis.\n\n"
            "Get a free key at: aistudio.google.com/apikey"
        )
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Clear Key")
        alert.addButtonWithTitle_("Cancel")

        field = AppKit.NSSecureTextField.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, 320, 24)
        )
        field.setStringValue_(current)
        field.setPlaceholderString_("AIza...")
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)

        response = alert.runModal()
        if response == AppKit.NSAlertFirstButtonReturn:
            key = field.stringValue().strip()
            if key:
                set_config_value("gemini_api_key", key)
                rumps.notification("CursorHub", "Gemini API Key saved", "AI analysis is now enabled.")
            else:
                rumps.notification("CursorHub", "No key entered", "Gemini API key was not changed.")
            self._build_menu()
        elif response == AppKit.NSAlertSecondButtonReturn:
            set_config_value("gemini_api_key", "")
            rumps.notification("CursorHub", "Gemini API Key cleared", "AI analysis has been disabled.")
            self._build_menu()

    def _sync_prompts(self, _):
        """Pull the latest prompts from the configured sync repo."""
        from cursorhub.config import get_config_value, set_config_value
        import AppKit

        sync_repo = get_config_value("prompt_sync_repo") or ""

        if not sync_repo:
            # No repo configured — ask them to set one
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Sync Prompts")
            alert.setInformativeText_(
                "Enter the GitHub repo URL that holds your shared prompt library.\n\n"
                "Example: https://github.com/your-org/cursorhub-prompts\n\n"
                "Anyone with access to this repo can sync the same prompt library."
            )
            alert.addButtonWithTitle_("Save & Sync")
            alert.addButtonWithTitle_("Cancel")

            field = AppKit.NSTextField.alloc().initWithFrame_(
                AppKit.NSMakeRect(0, 0, 380, 24)
            )
            field.setPlaceholderString_("https://github.com/your-org/cursorhub-prompts")
            alert.setAccessoryView_(field)
            alert.window().setInitialFirstResponder_(field)

            if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
                return
            sync_repo = field.stringValue().strip()
            if not sync_repo:
                return
            set_config_value("prompt_sync_repo", sync_repo)

        self._defer_action(lambda: self._run_prompt_sync(sync_repo))

    def _run_prompt_sync(self, sync_repo):
        """Pull prompts from the sync repo in a background thread."""
        import threading

        def _do_sync():
            try:
                from cursorhub.prompts import PROMPTS_DIR
                import subprocess, tempfile, shutil
                from pathlib import Path

                prompts_dir = Path(PROMPTS_DIR)
                prompts_dir.mkdir(parents=True, exist_ok=True)

                with tempfile.TemporaryDirectory() as tmp:
                    result = subprocess.run(
                        ["git", "clone", "--depth=1", sync_repo, tmp + "/repo"],
                        capture_output=True, text=True, timeout=60,
                    )
                    if result.returncode != 0:
                        rumps.notification("CursorHub", "Sync failed", result.stderr.strip() or "git clone failed")
                        return

                    repo_prompts = Path(tmp) / "repo" / "prompts"
                    src = repo_prompts if repo_prompts.exists() else Path(tmp) / "repo"

                    count = 0
                    for md in src.glob("*.md"):
                        dest = prompts_dir / md.name
                        if not dest.exists() or md.read_text() != dest.read_text():
                            shutil.copy2(md, dest)
                            count += 1

                    # Also sync taxonomy if present
                    for name in ["taxonomy.json"]:
                        src_file = Path(tmp) / "repo" / name
                        if src_file.exists():
                            from cursorhub.config import CONFIG_DIR
                            shutil.copy2(src_file, Path(CONFIG_DIR) / name)

                rumps.notification("CursorHub", "Prompts synced",
                                   f"{count} prompt(s) updated from shared library.")
            except Exception as e:
                rumps.notification("CursorHub", "Sync error", str(e))

        rumps.notification("CursorHub", "Syncing prompts...", "Pulling from shared library.")
        threading.Thread(target=_do_sync, daemon=True).start()

    def _edit_ports(self, sender):
        """Show a port editor for a project."""
        import AppKit
        from cursorhub.config import get_all_allocated_ports, PORT_RANGES

        path = sender._project_path
        name = sender._project_name

        # Find current ports
        current_ports = {}
        for p in self.config.get("projects", []):
            if p["path"] == path:
                current_ports = dict(p.get("ports", {}))
                break

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(f"Ports for \"{name}\"")
        alert.setInformativeText_(
            "Each service gets a unique port across all your projects.\n"
            "Leave a field blank to remove that port assignment.\n"
            "Format: service_name = port  (e.g. frontend_port = 3001)"
        )
        alert.addButtonWithTitle_("Save")
        alert.addButtonWithTitle_("Cancel")

        # Build editable text area with current assignments
        tv = AppKit.NSTextView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, 320, 140)
        )
        tv.setEditable_(True)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(12, 0.0))

        used = get_all_allocated_ports() - set(current_ports.values())
        if current_ports:
            content = "\n".join(f"{k} = {v}" for k, v in sorted(current_ports.items()))
        else:
            # Show hints for common port vars
            content = "# Add ports like:\n# frontend_port = 3000\n# backend_port = 8000"
        tv.setString_(content)

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, 320, 140))
        scroll.setDocumentView_(tv)
        scroll.setHasVerticalScroller_(True)
        alert.setAccessoryView_(scroll)

        # Show all ports in use by other projects for reference
        if used:
            others = sorted(used)[:8]
            note = f"Ports in use by other projects: {', '.join(str(p) for p in others)}"
            alert.setInformativeText_(alert.informativeText() + f"\n\n{note}")

        if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
            return

        # Parse the edited content
        new_ports = {}
        for line in tv.string().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip()
                if key and val.isdigit():
                    new_ports[key] = int(val)

        self.config = set_project_ports(path, new_ports, merge=False)
        self._build_menu()
        rumps.notification("CursorHub", "Ports updated", f"{name}: {len(new_ports)} port(s) saved.")

    def _add_project(self, _):
        """Add a project via folder picker dialog."""
        try:
            script = (
                'set theFolder to POSIX path of '
                '(choose folder with prompt "Select a project folder:")'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return  # User cancelled

            folder_path = result.stdout.strip().rstrip("/")
            if not folder_path:
                return

            name = Path(folder_path).name.replace("-", " ").replace("_", " ").title()

            self.config = add_project(name, folder_path)
            self._build_menu()
            rumps.notification("CursorHub", "Project Added", f"{name}\n{folder_path}")
        except subprocess.TimeoutExpired:
            pass
        except Exception as e:
            rumps.notification("CursorHub", "Error", str(e))

    def _scan_projects(self, _):
        """Auto-discover projects from Cursor's workspace storage."""
        discovered = auto_discover_projects()
        added_count = 0

        for project in discovered:
            existing_paths = [p["path"] for p in self.config.get("projects", [])]
            if project["path"] not in existing_paths:
                self.config = add_project(project["name"], project["path"])
                added_count += 1

        self._build_menu()

        if added_count > 0:
            rumps.notification(
                "CursorHub",
                "Scan Complete",
                f"Found and added {added_count} new project(s).",
            )
        else:
            rumps.notification(
                "CursorHub",
                "Scan Complete",
                "No new projects found.",
            )

    def _backup_now(self, _):
        """Create a backup of all Cursor workspace data."""
        try:
            rumps.notification("CursorHub", "Backup", "Starting backup...")
            backup_dir = create_backup()
            rumps.notification(
                "CursorHub",
                "Backup Complete",
                f"Saved to {backup_dir.name}",
            )
        except Exception as e:
            rumps.notification("CursorHub", "Backup Failed", str(e))

    def _show_backups(self, _):
        """Open the backups folder in Finder."""
        config = load_config()
        backup_dir = config.get("backup_dir", str(self.config.get("backup_dir", "")))
        backup_path = Path(backup_dir).expanduser()
        backup_path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["open", str(backup_path)])

    def _take_tour(self, _):
        """Open the guided tour window."""
        from cursorhub.tour import TourWindowController
        self._tour_controller = TourWindowController.alloc().init()
        self._tour_controller.showWindow()

    def _about(self, _):
        """Show about info."""
        from cursorhub import __version__
        rumps.alert(
            title="CursorHub",
            message=(
                f"Version {__version__}\n\n"
                "A menu bar app for managing your Cursor IDE projects, "
                "chat history, and workspaces.\n\n"
                "https://github.com/philpersonal/cursorhub"
            ),
            ok="Nice",
        )

    def _quit(self, _):
        """Quit the app."""
        rumps.quit_application()


def run():
    """Entry point for the menu bar app."""
    CursorHubApp().run()
