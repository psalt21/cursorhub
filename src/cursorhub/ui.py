"""Native macOS UI for CursorHub — New Project picker and Prompt Manager windows."""

import os
import re
import subprocess
import threading
from pathlib import Path

import AppKit
import objc
from Foundation import NSObject, NSMakeRect, NSMakeSize, NSMakeRange

from cursorhub.prompts import (
    PROMPTS_DIR,
    add_category,
    add_environment,
    apply_prompt_to_project,
    create_prompt,
    delete_prompt,
    edit_prompt,
    fill_variables,
    get_prompt,
    get_prompt_body,
    get_prompt_history,
    get_history_content,
    list_categories,
    list_environments,
    list_prompts,
    parse_variables,
    rename_category,
    rename_environment,
    rename_prompt,
    restore_history_version,
    set_prompt_category,
    set_prompt_environment,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODE_PROMPT = 0
MODE_CLONE = 1
MODE_BLANK = 2

WIN_WIDTH = 720
WIN_HEIGHT = 600

_edit_menu_installed = False

# Pattern matching SSH-style git URLs: git@host:org/repo.git
_SSH_URL_RE = re.compile(r"^git@([^:]+):(.+)$")


def _ssh_to_https(url):
    """Convert an SSH git URL to HTTPS.  Returns the URL unchanged if not SSH."""
    m = _SSH_URL_RE.match(url)
    if m:
        host, path = m.group(1), m.group(2)
        return f"https://{host}/{path}"
    return url


def _list_gh_accounts():
    """Return a list of GitHub account usernames configured in ``gh``."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout + result.stderr
        accounts = re.findall(r"Logged in to github\.com account (\S+)", output)
        return accounts or []
    except Exception:
        return []


def _switch_gh_account(username):
    """Switch the active ``gh`` account to *username*."""
    try:
        subprocess.run(
            ["gh", "auth", "switch", "--user", username],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass


def _ensure_edit_menu():
    """Install a standard Edit menu so Cmd+C/V/X/A/Z work in text fields.

    Safe to call multiple times — only installs once.
    """
    global _edit_menu_installed
    if _edit_menu_installed:
        return
    try:
        main_menu = AppKit.NSApp.mainMenu()
        if main_menu is None:
            return

        edit_menu = AppKit.NSMenu.alloc().initWithTitle_("Edit")
        for title, action, key in [
            ("Undo",       "undo:",      "z"),
            ("Redo",       "redo:",      "Z"),
            (None,         None,         None),
            ("Cut",        "cut:",       "x"),
            ("Copy",       "copy:",      "c"),
            ("Paste",      "paste:",     "v"),
            (None,         None,         None),
            ("Select All", "selectAll:", "a"),
        ]:
            if title is None:
                edit_menu.addItem_(AppKit.NSMenuItem.separatorItem())
            else:
                item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    title, action, key)
                edit_menu.addItem_(item)

        edit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Edit", None, "")
        edit_item.setSubmenu_(edit_menu)
        main_menu.addItem_(edit_item)
        _edit_menu_installed = True
    except Exception:
        pass


# ---------------------------------------------------------------------------
# NewProjectWindowController — the main picker window
# ---------------------------------------------------------------------------

class NewProjectWindowController(NSObject):
    """Controller for the New Project picker window."""

    # -- public callback set by the caller (app.py) --
    on_project_created = None  # callable(name, path)

    # Set this BEFORE calling alloc().init() to enable demo mode
    _init_demo = False

    def init(self):
        """Initialize the controller. Set _init_demo = True before calling for demo mode."""
        self = objc.super(NewProjectWindowController, self).init()
        if self is None:
            return None

        self._demo = NewProjectWindowController._init_demo
        NewProjectWindowController._init_demo = False  # reset for next use
        self._prompts = list_prompts()
        # In demo mode, show sample prompts if none exist
        if self._demo and not self._prompts:
            self._prompts = [
                {"name": "Full-Stack Web App", "filename": "_demo_web.md",
                 "path": "", "preview": "You are an expert full-stack developer..."},
                {"name": "Python CLI Tool", "filename": "_demo_cli.md",
                 "path": "", "preview": "You are a Python developer building a CLI..."},
                {"name": "Data Pipeline", "filename": "_demo_data.md",
                 "path": "", "preview": "You are a data engineer designing a pipeline..."},
            ]
            self._demo_contents = {
                "_demo_web.md": (
                    "# Full-Stack Web App\n\n"
                    "You are an expert full-stack developer. Create a modern web application with:\n"
                    "- Next.js 14 with App Router\n"
                    "- TypeScript\n"
                    "- Tailwind CSS\n"
                    "- Prisma + PostgreSQL\n\n"
                    "Start by creating the project structure and a README, then implement "
                    "user authentication with email/password and OAuth.\n\n"
                    "Create a GitHub repo and set up CI/CD with GitHub Actions."
                ),
                "_demo_cli.md": (
                    "# Python CLI Tool\n\n"
                    "You are a Python developer. Build a command-line tool with:\n"
                    "- Click for argument parsing\n"
                    "- Rich for beautiful terminal output\n"
                    "- Pydantic for config management\n\n"
                    "The tool should be installable via pip and have a comprehensive test suite."
                ),
                "_demo_data.md": (
                    "# Data Pipeline\n\n"
                    "You are a data engineer. Design and implement a data pipeline with:\n"
                    "- Python + Apache Airflow for orchestration\n"
                    "- PostgreSQL as the warehouse\n"
                    "- dbt for transformations\n\n"
                    "Include monitoring, alerting, and data quality checks."
                ),
            }
        else:
            self._demo_contents = {}

        self._selected_prompt_idx = 0
        self._mode = MODE_PROMPT

        self._build_window()
        return self

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self):
        _ensure_edit_menu()
        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
            | AppKit.NSResizableWindowMask
        )
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, WIN_WIDTH, WIN_HEIGHT),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        title = "New Project (Demo)" if self._demo else "New Project"
        self._window.setTitle_(title)
        self._window.setMinSize_(NSMakeSize(600, 480))
        self._window.setDelegate_(self)
        self._window.center()

        content = self._window.contentView()
        content.setAutoresizesSubviews_(True)

        y = WIN_HEIGHT  # build top-down, converting to bottom-up coords

        # --- Segmented control (mode picker) ---
        y -= 50
        seg = AppKit.NSSegmentedControl.alloc().initWithFrame_(
            NSMakeRect(20, y, WIN_WIDTH - 40, 32)
        )
        seg.setSegmentCount_(3)
        seg.setLabel_forSegment_("From Starter Prompt", 0)
        seg.setLabel_forSegment_("Clone Repository", 1)
        seg.setLabel_forSegment_("Blank Project", 2)
        seg.setWidth_forSegment_(200, 0)
        seg.setWidth_forSegment_(200, 1)
        seg.setWidth_forSegment_(200, 2)
        seg.setSelectedSegment_(0)
        seg.setTarget_(self)
        seg.setAction_(objc.selector(self.segmentChanged_, signature=b"v@:@"))
        seg.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        content.addSubview_(seg)
        self._seg = seg

        # --- Mode containers ---
        # We'll use a plain NSView for each mode and toggle visibility
        container_frame = NSMakeRect(20, 150, WIN_WIDTH - 40, y - 160)

        self._prompt_container = self._build_prompt_view(container_frame)
        content.addSubview_(self._prompt_container)

        self._clone_container = self._build_clone_view(container_frame)
        self._clone_container.setHidden_(True)
        content.addSubview_(self._clone_container)

        self._blank_container = self._build_blank_view(container_frame)
        self._blank_container.setHidden_(True)
        content.addSubview_(self._blank_container)

        # --- Bottom bar (shared across all modes) ---
        self._build_bottom_bar(content)

        # --- Initial state ---
        self._update_prompt_preview()

    # ------------------------------------------------------------------
    # Starter Prompt view
    # ------------------------------------------------------------------

    def _build_prompt_view(self, frame):
        container = AppKit.NSView.alloc().initWithFrame_(frame)
        container.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        cw = frame.size.width
        ch = frame.size.height
        list_width = int(cw * 0.35)

        # -- Left: prompt list label + scroll view --
        label = AppKit.NSTextField.labelWithString_("Starter Prompts:")
        label.setFrame_(NSMakeRect(0, ch - 22, list_width, 20))
        label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(12))
        container.addSubview_(label)

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 0, list_width, ch - 28)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSBezelBorder)
        scroll.setAutoresizingMask_(
            AppKit.NSViewHeightSizable
        )

        table = AppKit.NSTableView.alloc().initWithFrame_(scroll.bounds())
        col = AppKit.NSTableColumn.alloc().initWithIdentifier_("name")
        col.setWidth_(list_width - 24)
        col.setTitle_("Name")
        table.addTableColumn_(col)
        table.setHeaderView_(None)
        table.setDelegate_(self)
        table.setDataSource_(self)
        table.setRowHeight_(28)

        scroll.setDocumentView_(table)
        container.addSubview_(scroll)
        self._prompt_table = table

        # -- Right: preview label + text view --
        preview_x = list_width + 12
        preview_w = cw - preview_x

        plabel = AppKit.NSTextField.labelWithString_("Preview:")
        plabel.setFrame_(NSMakeRect(preview_x, ch - 22, preview_w, 20))
        plabel.setFont_(AppKit.NSFont.boldSystemFontOfSize_(12))
        container.addSubview_(plabel)

        preview_scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(preview_x, 0, preview_w, ch - 28)
        )
        preview_scroll.setHasVerticalScroller_(True)
        preview_scroll.setBorderType_(AppKit.NSBezelBorder)
        preview_scroll.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        tv = AppKit.NSTextView.alloc().initWithFrame_(preview_scroll.bounds())
        tv.setEditable_(False)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(12, 0.0))
        tv.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        tv.setTextContainerInset_(NSMakeSize(8, 8))
        preview_scroll.setDocumentView_(tv)
        container.addSubview_(preview_scroll)
        self._preview_text = tv

        # No-prompts hint
        if not self._prompts:
            tv.setString_(
                "No starter prompts found.\n\n"
                f"Add .md files to:\n{PROMPTS_DIR}\n\n"
                "Each .md file becomes a starter prompt you can apply to new projects."
            )

        return container

    # ------------------------------------------------------------------
    # Clone Repo view
    # ------------------------------------------------------------------

    def _build_clone_view(self, frame):
        container = AppKit.NSView.alloc().initWithFrame_(frame)
        container.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )
        cw = frame.size.width
        ch = frame.size.height

        y = ch - 30

        lbl = AppKit.NSTextField.labelWithString_("Repository URL:")
        lbl.setFrame_(NSMakeRect(0, y, 120, 20))
        lbl.setFont_(AppKit.NSFont.boldSystemFontOfSize_(12))
        container.addSubview_(lbl)

        y -= 30
        url_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(0, y, cw, 24)
        )
        url_field.setPlaceholderString_("https://github.com/user/repo.git  or  git@github.com:user/repo.git")
        url_field.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        container.addSubview_(url_field)
        self._clone_url_field = url_field

        # GitHub account selector
        y -= 36
        acct_lbl = AppKit.NSTextField.labelWithString_("GitHub Account:")
        acct_lbl.setFrame_(NSMakeRect(0, y, 110, 20))
        acct_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        container.addSubview_(acct_lbl)

        acct_popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            NSMakeRect(114, y - 2, 200, 24)
        )
        container.addSubview_(acct_popup)
        self._clone_acct_popup = acct_popup
        self._refresh_gh_accounts()

        # Starter prompt selector (optional)
        y -= 36
        prompt_lbl = AppKit.NSTextField.labelWithString_("Starter Prompt:")
        prompt_lbl.setFrame_(NSMakeRect(0, y, 110, 20))
        prompt_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        container.addSubview_(prompt_lbl)

        prompt_popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            NSMakeRect(114, y - 2, cw - 114, 24)
        )
        prompt_popup.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        container.addSubview_(prompt_popup)
        self._clone_prompt_popup = prompt_popup
        self._refresh_clone_prompts()

        y -= 30
        hint = AppKit.NSTextField.labelWithString_(
            "SSH URLs (git@...) are automatically converted to HTTPS.\n"
            "Pick a starter prompt to apply it as a Cursor rule after cloning."
        )
        hint.setFrame_(NSMakeRect(0, y, cw, 32))
        hint.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        hint.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        container.addSubview_(hint)

        return container

    def _refresh_clone_prompts(self):
        """Populate the optional starter prompt dropdown for clone mode."""
        self._clone_prompt_popup.removeAllItems()
        self._clone_prompt_popup.addItemWithTitle_("None")
        self._clone_prompt_popup.menu().addItem_(AppKit.NSMenuItem.separatorItem())
        prompts = list_prompts()
        for p in prompts:
            self._clone_prompt_popup.addItemWithTitle_(p["name"])
        self._clone_prompts_list = prompts

    def _refresh_gh_accounts(self):
        """Populate the GitHub account dropdown from ``gh auth status``."""
        self._clone_acct_popup.removeAllItems()
        accounts = _list_gh_accounts()
        if accounts:
            for acct in accounts:
                self._clone_acct_popup.addItemWithTitle_(acct)
        else:
            self._clone_acct_popup.addItemWithTitle_("(no accounts — run gh auth login)")
            self._clone_acct_popup.setEnabled_(False)

    # ------------------------------------------------------------------
    # Blank Project view
    # ------------------------------------------------------------------

    def _build_blank_view(self, frame):
        container = AppKit.NSView.alloc().initWithFrame_(frame)
        container.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )
        cw = frame.size.width
        ch = frame.size.height

        msg = AppKit.NSTextField.labelWithString_(
            "Create an empty project folder and open it in Cursor.\n\n"
            "Fill in the project name and location below, then click Create Project."
        )
        msg.setFrame_(NSMakeRect(0, ch - 80, cw, 60))
        msg.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        msg.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        container.addSubview_(msg)

        return container

    # ------------------------------------------------------------------
    # Bottom bar (project name, location, buttons) — shared
    # ------------------------------------------------------------------

    def _build_bottom_bar(self, parent):
        bw = WIN_WIDTH - 40
        y = 140

        # Project Name
        name_lbl = AppKit.NSTextField.labelWithString_("Project Name:")
        name_lbl.setFrame_(NSMakeRect(20, y, 100, 20))
        name_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        parent.addSubview_(name_lbl)

        name_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(130, y, bw - 110, 24)
        )
        name_field.setPlaceholderString_("my-awesome-project")
        name_field.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        parent.addSubview_(name_field)
        self._name_field = name_field

        # Location
        y -= 34
        loc_lbl = AppKit.NSTextField.labelWithString_("Location:")
        loc_lbl.setFrame_(NSMakeRect(20, y, 100, 20))
        loc_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        parent.addSubview_(loc_lbl)

        loc_field = AppKit.NSTextField.alloc().initWithFrame_(
            NSMakeRect(130, y, bw - 200, 24)
        )
        default_loc = str(Path.home() / "Projects")
        if not Path(default_loc).exists():
            default_loc = str(Path.home())
        loc_field.setStringValue_(default_loc)
        loc_field.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        parent.addSubview_(loc_field)
        self._location_field = loc_field

        choose_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(bw - 50, y, 80, 24)
        )
        choose_btn.setTitle_("Choose...")
        choose_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        choose_btn.setTarget_(self)
        choose_btn.setAction_(objc.selector(self.chooseLocation_, signature=b"v@:@"))
        choose_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        parent.addSubview_(choose_btn)

        # Cursor Profile
        y -= 34
        prof_lbl = AppKit.NSTextField.labelWithString_("Cursor Profile:")
        prof_lbl.setFrame_(NSMakeRect(20, y, 100, 20))
        prof_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(12))
        parent.addSubview_(prof_lbl)

        prof_popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            NSMakeRect(130, y - 2, 260, 26)
        )
        from cursorhub.config import list_cursor_profiles
        self._cursor_profiles = list_cursor_profiles()
        for p in self._cursor_profiles:
            prof_popup.addItemWithTitle_(p["name"])
        self._selected_profile = ""
        prof_popup.setTarget_(self)
        prof_popup.setAction_(objc.selector(self.profileChanged_, signature=b"v@:@"))
        parent.addSubview_(prof_popup)
        self._profile_popup = prof_popup

        hint = AppKit.NSTextField.labelWithString_(
            "Work or Personal profile keeps billing and extensions separate."
        )
        hint.setFrame_(NSMakeRect(130, y - 18, bw - 110, 16))
        hint.setFont_(AppKit.NSFont.systemFontOfSize_(10))
        hint.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        parent.addSubview_(hint)

        # --- Separator ---
        y -= 30
        sep = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(20, y, bw, 1))
        sep.setBoxType_(AppKit.NSBoxSeparator)
        sep.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        parent.addSubview_(sep)

        # --- Buttons ---
        y -= 36

        cancel_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(bw - 180, y, 90, 32)
        )
        cancel_btn.setTitle_("Cancel")
        cancel_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        cancel_btn.setTarget_(self)
        cancel_btn.setAction_(objc.selector(self.cancel_, signature=b"v@:@"))
        cancel_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        cancel_btn.setKeyEquivalent_("\x1b")  # Escape
        parent.addSubview_(cancel_btn)

        create_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(bw - 80, y, 120, 32)
        )
        create_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        create_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)

        if self._demo:
            create_btn.setTitle_("Close Demo")
            create_btn.setKeyEquivalent_("\r")
            create_btn.setTarget_(self)
            create_btn.setAction_(objc.selector(self.cancel_, signature=b"v@:@"))

            # Demo banner
            banner = AppKit.NSTextField.labelWithString_(
                "DEMO MODE \u2014 this is a preview, nothing will be created"
            )
            banner.setFrame_(NSMakeRect(20, y + 4, bw - 220, 20))
            banner.setFont_(AppKit.NSFont.systemFontOfSize_(11))
            banner.setTextColor_(AppKit.NSColor.systemOrangeColor())
            parent.addSubview_(banner)
        else:
            create_btn.setTitle_("Create Project")
            create_btn.setKeyEquivalent_("\r")
            create_btn.setTarget_(self)
            create_btn.setAction_(objc.selector(self.createProject_, signature=b"v@:@"))

        parent.addSubview_(create_btn)
        self._create_btn = create_btn

    # ------------------------------------------------------------------
    # NSTableView data source / delegate
    # ------------------------------------------------------------------

    def numberOfRowsInTableView_(self, table):
        return len(self._prompts)

    def tableView_objectValueForTableColumn_row_(self, table, col, row):
        if 0 <= row < len(self._prompts):
            p = self._prompts[row]
            env = p.get("environment", "")
            cat = p.get("category", "")
            name = p["name"]
            parts = []
            if env:
                parts.append(env)
            if cat:
                parts.append(cat)
            # Check for template variables
            content = get_prompt(p["filename"])
            if content:
                var_count = len(parse_variables(content))
                if var_count > 0:
                    parts.append(f"{var_count} var{'s' if var_count != 1 else ''}")
            if parts:
                return f"{name}  ({' / '.join(parts)})"
            return name
        return ""

    def tableViewSelectionDidChange_(self, notification):
        row = self._prompt_table.selectedRow()
        if row >= 0:
            self._selected_prompt_idx = row
            self._update_prompt_preview()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @objc.typedSelector(b"v@:@")
    def segmentChanged_(self, sender):
        mode = sender.selectedSegment()
        self._mode = mode
        self._prompt_container.setHidden_(mode != MODE_PROMPT)
        self._clone_container.setHidden_(mode != MODE_CLONE)
        self._blank_container.setHidden_(mode != MODE_BLANK)

    @objc.typedSelector(b"v@:@")
    def chooseLocation_(self, sender):
        panel = AppKit.NSOpenPanel.openPanel()
        panel.setCanChooseDirectories_(True)
        panel.setCanChooseFiles_(False)
        panel.setCanCreateDirectories_(True)
        panel.setPrompt_("Choose")
        panel.setMessage_("Select the parent folder for the new project:")

        current = self._location_field.stringValue()
        if current and Path(current).exists():
            panel.setDirectoryURL_(
                AppKit.NSURL.fileURLWithPath_(current)
            )

        result = panel.runModal()
        if result == AppKit.NSModalResponseOK:
            url = panel.URLs()[0]
            self._location_field.setStringValue_(url.path())

    @objc.typedSelector(b"v@:@")
    def profileChanged_(self, sender):
        idx = self._profile_popup.indexOfSelectedItem()
        selected = self._cursor_profiles[idx]
        from cursorhub.config import DEFAULT_PROFILE
        self._selected_profile = "" if selected["id"] == DEFAULT_PROFILE else selected["name"]

    @objc.typedSelector(b"v@:@")
    def cancel_(self, sender):
        self._window.close()

    @objc.typedSelector(b"v@:@")
    def createProject_(self, sender):
        project_name = self._name_field.stringValue().strip()
        location = self._location_field.stringValue().strip()

        if not project_name:
            self._show_alert("Please enter a project name.")
            return
        if not location or not Path(location).exists():
            self._show_alert("Please choose a valid location.")
            return

        folder_name = project_name.lower().replace(" ", "-").replace("_", "-")
        project_path = str(Path(location) / folder_name)

        if self._mode == MODE_PROMPT:
            self._create_from_prompt(project_name, project_path)
        elif self._mode == MODE_CLONE:
            self._create_from_clone(project_name, project_path)
        elif self._mode == MODE_BLANK:
            self._create_blank(project_name, project_path)

    # ------------------------------------------------------------------
    # Creation methods
    # ------------------------------------------------------------------

    def _create_from_prompt(self, project_name, project_path):
        if not self._prompts:
            self._show_alert("No starter prompts available. Add .md files to the prompts folder.")
            return

        idx = self._selected_prompt_idx
        if idx < 0 or idx >= len(self._prompts):
            self._show_alert("Please select a starter prompt.")
            return

        prompt = self._prompts[idx]

        try:
            # Check for template variables
            body = get_prompt_body(prompt["filename"])
            if body is None:
                self._show_alert("Could not read prompt content.")
                return

            all_vars = parse_variables(body)
            variables = {}

            from cursorhub.config import allocate_ports, is_port_variable, set_project_ports

            # Split port vars (auto-assigned) from regular vars (user fills in)
            port_vars = [v for v in all_vars if is_port_variable(v)]
            user_vars = [v for v in all_vars if not is_port_variable(v)]

            # Auto-assign ports
            if port_vars:
                port_assignments = allocate_ports(port_vars)
                variables.update({k: str(v) for k, v in port_assignments.items()})

            # Ask user for regular vars
            if user_vars:
                user_values = self._ask_for_variables(user_vars, port_preview=port_assignments if port_vars else {})
                if user_values is None:
                    return
                variables.update(user_values)

            Path(project_path).mkdir(parents=True, exist_ok=True)

            # Apply the prompt as a Cursor rule (with variable substitution)
            prompt_content = apply_prompt_to_project(
                prompt["filename"], project_path, variables=variables if variables else None
            )

            # Copy to clipboard
            subprocess.run(["pbcopy"], input=prompt_content.encode(), check=True)

            # Store port assignments in project config after creation
            if port_vars:
                self._pending_port_assignments = {k: int(v) for k, v in variables.items() if is_port_variable(k)}
            else:
                self._pending_port_assignments = {}

            self._finish_creation(
                project_name, project_path,
                "Starter prompt copied to clipboard — paste into your first chat!",
                created_via="prompt",
                prompt_filename=prompt["filename"],
                prompt_variables=variables,
            )
        except Exception as e:
            self._show_alert(f"Error creating project: {e}")

    def _ask_for_variables(self, var_names, port_preview=None):
        """Show a modal dialog asking the user to fill in template variable values.

        port_preview: dict of {port_var: port_number} already assigned — shown
        as read-only info above the input fields.
        Returns a dict of {var_name: value} or None if cancelled.
        """
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Fill In Template Variables")
        alert.setInformativeText_(
            "This prompt has variables that need values.\n"
            "Enter a value for each one:"
        )
        alert.addButtonWithTitle_("Create Project")
        alert.addButtonWithTitle_("Cancel")

        field_height = 28
        label_height = 16
        row_height = field_height + label_height + 8
        container_width = 350

        # Port preview rows at the top
        port_rows_height = 0
        if port_preview:
            port_rows_height = len(port_preview) * 20 + 20

        total_height = len(var_names) * row_height + 4 + port_rows_height

        container = AppKit.NSView.alloc().initWithFrame_(
            NSMakeRect(0, 0, container_width, total_height)
        )

        # Render port preview (read-only)
        if port_preview:
            py = total_height - 18
            header = AppKit.NSTextField.labelWithString_("Auto-assigned ports:")
            header.setFrame_(NSMakeRect(0, py, container_width, 16))
            header.setFont_(AppKit.NSFont.boldSystemFontOfSize_(11))
            container.addSubview_(header)
            py -= 20
            for pvar, pnum in port_preview.items():
                row_lbl = AppKit.NSTextField.labelWithString_(
                    f"  {pvar.replace('_port','').replace('_',' ').title()}: {pnum}"
                )
                row_lbl.setFrame_(NSMakeRect(0, py, container_width, 16))
                row_lbl.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
                row_lbl.setTextColor_(AppKit.NSColor.systemGreenColor())
                container.addSubview_(row_lbl)
                py -= 18

        fields = {}
        for i, var in enumerate(var_names):
            y = total_height - port_rows_height - (i + 1) * row_height + 4

            label = AppKit.NSTextField.labelWithString_(
                var.replace("_", " ").title() + ":"
            )
            label.setFrame_(NSMakeRect(0, y + field_height + 2, container_width, label_height))
            label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
            label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
            container.addSubview_(label)

            field = AppKit.NSTextField.alloc().initWithFrame_(
                NSMakeRect(0, y, container_width, field_height)
            )
            field.setPlaceholderString_(f"Enter {var.replace('_', ' ')}")
            container.addSubview_(field)
            fields[var] = field

        alert.setAccessoryView_(container)

        if var_names:
            alert.window().setInitialFirstResponder_(fields[var_names[0]])

        result = alert.runModal()
        if result != AppKit.NSAlertFirstButtonReturn:
            return None

        values = {}
        for var, field in fields.items():
            val = field.stringValue().strip()
            if val:
                values[var] = val
            else:
                values[var] = "{{" + var + "}}"  # leave unfilled vars as-is
        return values

    def _create_from_clone(self, project_name, project_path):
        clone_url = self._clone_url_field.stringValue().strip()
        if not clone_url:
            self._show_alert("Please enter a repository URL.")
            return

        # Convert SSH URLs to HTTPS so gh credential helper can authenticate
        clone_url = _ssh_to_https(clone_url)

        # Switch to the selected GitHub account before cloning
        selected_acct = str(self._clone_acct_popup.titleOfSelectedItem() or "")
        if selected_acct and not selected_acct.startswith("("):
            _switch_gh_account(selected_acct)

        # Disable button during clone
        self._create_btn.setEnabled_(False)
        self._create_btn.setTitle_("Cloning...")

        def _do_clone():
            try:
                env = dict(os.environ)
                result = subprocess.run(
                    ["git", "clone", clone_url, project_path],
                    capture_output=True, text=True, timeout=120,
                    env=env,
                )
                if result.returncode != 0:
                    error_msg = result.stderr.strip() or "git clone failed"
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self.onCloneError_, signature=b"v@:@"),
                        error_msg, False
                    )
                    return

                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.onCloneSuccess_, signature=b"v@:@"),
                    {"name": project_name, "path": project_path}, False
                )
            except subprocess.TimeoutExpired:
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.onCloneError_, signature=b"v@:@"),
                    "Clone timed out after 120 seconds.", False
                )
            except Exception as e:
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    objc.selector(self.onCloneError_, signature=b"v@:@"),
                    str(e), False
                )

        threading.Thread(target=_do_clone, daemon=True).start()

    @objc.typedSelector(b"v@:@")
    def onCloneSuccess_(self, info):
        self._create_btn.setEnabled_(True)
        self._create_btn.setTitle_("Create Project")

        prompt_filename = ""
        prompt_variables = None
        message = "Repository cloned successfully!"

        # Apply the selected starter prompt if one was chosen
        selected_idx = self._clone_prompt_popup.indexOfSelectedItem()
        # Index 0 = "None", 1 = separator, so prompts start at index 2
        prompt_list_idx = selected_idx - 2
        if prompt_list_idx >= 0 and prompt_list_idx < len(self._clone_prompts_list):
            prompt = self._clone_prompts_list[prompt_list_idx]
            prompt_filename = prompt["filename"]
            try:
                from cursorhub.config import allocate_ports, is_port_variable, set_project_ports
                body = get_prompt_body(prompt_filename)
                all_vars = parse_variables(body) if body else []

                port_vars = [v for v in all_vars if is_port_variable(v)]
                user_vars = [v for v in all_vars if not is_port_variable(v)]

                port_assignments = allocate_ports(port_vars) if port_vars else {}
                prompt_variables = {k: str(v) for k, v in port_assignments.items()}

                if user_vars:
                    user_values = self._ask_for_variables(user_vars, port_preview=port_assignments)
                    if user_values is None:
                        prompt_filename = ""
                    else:
                        prompt_variables.update(user_values)

                if prompt_filename:
                    prompt_content = apply_prompt_to_project(
                        prompt_filename, info["path"], variables=prompt_variables or None
                    )
                    subprocess.run(["pbcopy"], input=prompt_content.encode(), check=True)
                    self._pending_port_assignments = {k: int(v) for k, v in prompt_variables.items() if is_port_variable(k)}
                    port_note = ""
                    if port_assignments:
                        port_note = "  Ports: " + ", ".join(f"{k.replace('_port','').title()}={v}" for k, v in port_assignments.items())
                    message = (
                        "Repository cloned and starter prompt applied!\n"
                        "Prompt copied to clipboard — paste into your first chat."
                        + ("\n" + port_note if port_note else "")
                    )
            except Exception as e:
                message = f"Cloned successfully, but prompt failed: {e}"
                prompt_filename = ""

        self._finish_creation(info["name"], info["path"], message,
                              created_via="clone",
                              prompt_filename=prompt_filename,
                              prompt_variables=prompt_variables)

    @objc.typedSelector(b"v@:@")
    def onCloneError_(self, message):
        self._create_btn.setEnabled_(True)
        self._create_btn.setTitle_("Create Project")
        self._show_alert(f"Clone failed: {message}")

    def _create_blank(self, project_name, project_path):
        try:
            Path(project_path).mkdir(parents=True, exist_ok=True)
            self._finish_creation(project_name, project_path,
                                  "Blank project created!",
                                  created_via="blank")
        except Exception as e:
            self._show_alert(f"Error creating project: {e}")

    # ------------------------------------------------------------------
    # Shared finish / helpers
    # ------------------------------------------------------------------

    def _finish_creation(self, project_name, project_path, message,
                         created_via="", prompt_filename="", prompt_variables=None):
        """Register project, open in Cursor, notify, close window."""
        from cursorhub.config import (
            add_project, load_config, open_in_cursor, set_project_profile
        )
        from cursorhub.analytics import log_event

        display_name = project_name.replace("-", " ").replace("_", " ").title()
        add_project(display_name, project_path,
                    created_via=created_via,
                    prompt_filename=prompt_filename,
                    prompt_variables=prompt_variables)

        # Apply selected profile if any
        profile = getattr(self, "_selected_profile", "")
        if profile:
            set_project_profile(project_path, profile)

        # Save auto-assigned ports
        pending_ports = getattr(self, "_pending_port_assignments", {})
        if pending_ports:
            set_project_ports(project_path, pending_ports)
            self._pending_port_assignments = {}

        log_event("project_created", prompt_filename=prompt_filename or None,
                  project_path=project_path, method=created_via,
                  project_name=display_name)

        # Open in Cursor (profile-aware)
        config = load_config()
        cursor_app = config.get("cursor_app", "/Applications/Cursor.app")
        open_in_cursor(project_path)

        # Auto-paste prompt into Cursor's agent chat if a prompt was applied
        if prompt_filename:
            self._auto_paste_into_cursor(cursor_app)

        # Notify
        import rumps
        rumps.notification("CursorHub", f"Created: {display_name}", message)

        # Close the window
        self._window.close()

        # Callback so the menu bar app can refresh
        if self.on_project_created:
            self.on_project_created(display_name, project_path)

    @staticmethod
    def _auto_paste_into_cursor(cursor_app):
        """Wait for Cursor to activate, then open the agent chat and paste."""
        import time

        def _do_paste():
            app_name = Path(cursor_app).stem  # "Cursor" from the .app path
            time.sleep(3)

            # Wait up to 15 seconds for Cursor to be frontmost
            for _ in range(10):
                try:
                    result = subprocess.run(
                        ["osascript", "-e",
                         'tell application "System Events" to get name '
                         'of first process whose frontmost is true'],
                        capture_output=True, text=True, timeout=5,
                    )
                    if app_name.lower() in result.stdout.strip().lower():
                        break
                except Exception:
                    pass
                time.sleep(1.5)

            # Small extra pause for the window to fully render
            time.sleep(1)

            # Cmd+I to open the Agent chat, then Cmd+V to paste
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "{app_name}" to activate\n'
                 'delay 0.3\n'
                 'tell application "System Events"\n'
                 '  keystroke "i" using command down\n'
                 '  delay 0.5\n'
                 '  keystroke "v" using command down\n'
                 'end tell'],
                capture_output=True, timeout=10,
            )

        threading.Thread(target=_do_paste, daemon=True).start()

    def _update_prompt_preview(self):
        if not self._prompts:
            return
        idx = self._selected_prompt_idx
        if 0 <= idx < len(self._prompts):
            filename = self._prompts[idx]["filename"]
            # Check demo content first, then real prompts
            if filename in self._demo_contents:
                content = self._demo_contents[filename]
            else:
                content = get_prompt(filename)
            if content:
                self._preview_text.setString_(content)
            else:
                self._preview_text.setString_("(could not load prompt)")

    def _show_alert(self, message):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("CursorHub")
        alert.setInformativeText_(message)
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        alert.runModal()

    # ------------------------------------------------------------------
    # Public: show the window
    # ------------------------------------------------------------------

    def showWindow(self):
        """Display the picker window and bring it to front."""
        # Refresh prompts list each time the window opens, sorted by category
        self._prompts = sorted(
            list_prompts(),
            key=lambda p: (p.get("category", "") or "zzz", p["name"]),
        )
        self._selected_prompt_idx = 0
        self._prompt_table.reloadData()
        self._update_prompt_preview()

        # Select first row if available
        if self._prompts:
            idx_set = AppKit.NSIndexSet.indexSetWithIndex_(0)
            self._prompt_table.selectRowIndexes_byExtendingSelection_(idx_set, False)

        self._window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    # ------------------------------------------------------------------
    # Window delegate — clean up to prevent segfaults on dealloc
    # ------------------------------------------------------------------

    def windowWillClose_(self, notification):
        try:
            if hasattr(self, '_prompt_table') and self._prompt_table is not None:
                self._prompt_table.setDelegate_(None)
                self._prompt_table.setDataSource_(None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PromptManagerController — Manage Starter Prompts window
# ---------------------------------------------------------------------------

MGR_WIDTH = 860
MGR_HEIGHT = 620
UNCATEGORIZED = "Uncategorized"
NO_ENVIRONMENT = "General"


class PromptManagerController(NSObject):
    """Controller for the Starter Prompt Manager window.

    Outline sidebar hierarchy: Environment -> Category -> Prompt
    Each outline item is a unique string key:
      - "env::<EnvName>"             (environment group header)
      - "cat::<EnvName>::<CatName>"  (category group header)
      - "<filename>"                 (prompt leaf node)
    """

    def init(self):
        self = objc.super(PromptManagerController, self).init()
        if self is None:
            return None

        self._prompts = []          # flat list of prompt dicts
        # 3-level tree: [(env_key, [(cat_key, [filenames...])])]
        self._tree = []
        self._selected_filename = None
        self._dirty = False
        self._history_ctrl = None

        self._reload_data()
        self._build_window()
        self._select_first()
        return self

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _reload_data(self):
        """Reload prompts from disk and rebuild the 3-level tree."""
        self._prompts = list_prompts()

        # Batch-load analytics stats for all prompts
        try:
            from cursorhub.analytics import get_all_prompt_stats
            self._prompt_stats = get_all_prompt_stats()
        except Exception:
            self._prompt_stats = {}

        # Group: environment -> category -> [prompt dicts]
        env_groups = {}
        for p in self._prompts:
            env = p.get("environment", "") or NO_ENVIRONMENT
            cat = p.get("category", "") or UNCATEGORIZED
            env_groups.setdefault(env, {}).setdefault(cat, []).append(p)

        # Include empty environments and categories from taxonomy
        all_envs = set(env_groups.keys())
        for env in list_environments():
            all_envs.add(env)
        all_cats = set()
        for env in env_groups:
            all_cats.update(env_groups[env].keys())
        for cat in list_categories():
            all_cats.add(cat)

        # Sort environments: named first (alphabetical), General last
        env_names = sorted(k for k in all_envs if k != NO_ENVIRONMENT)
        if NO_ENVIRONMENT in all_envs or not env_names:
            env_names.append(NO_ENVIRONMENT)

        tree = []
        for env_name in env_names:
            env_key = f"env::{env_name}"
            cat_groups = env_groups.get(env_name, {})

            # For each environment, show its categories + any empty categories
            # (only show global empty categories under General to avoid clutter)
            used_cats = set(cat_groups.keys())
            cat_names_set = set(used_cats)
            if env_name == NO_ENVIRONMENT:
                # Show all known categories under General
                cat_names_set.update(all_cats)

            cat_names = sorted(k for k in cat_names_set if k != UNCATEGORIZED)
            if UNCATEGORIZED in cat_names_set or not cat_names:
                cat_names.append(UNCATEGORIZED)

            cat_list = []
            for cat_name in cat_names:
                cat_key = f"cat::{env_name}::{cat_name}"
                prompts_in_cat = cat_groups.get(cat_name, [])
                filenames = [p["filename"] for p in prompts_in_cat]
                cat_list.append((cat_key, filenames))
            tree.append((env_key, cat_list))
        self._tree = tree

    def _find_prompt(self, filename):
        for p in self._prompts:
            if p["filename"] == filename:
                return p
        return None

    def _env_name_from_key(self, key):
        """Extract environment display name from 'env::Name'."""
        return key.split("::", 1)[1] if "::" in key else key

    def _cat_name_from_key(self, key):
        """Extract category display name from 'cat::Env::Name'."""
        parts = key.split("::")
        return parts[2] if len(parts) >= 3 else key

    def _is_env_key(self, item):
        return isinstance(item, str) and item.startswith("env::")

    def _is_cat_key(self, item):
        return isinstance(item, str) and item.startswith("cat::")

    def _is_prompt_key(self, item):
        return isinstance(item, str) and not item.startswith("env::") and not item.startswith("cat::")

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self):
        _ensure_edit_menu()
        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
            | AppKit.NSResizableWindowMask
        )
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(150, 150, MGR_WIDTH, MGR_HEIGHT),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_("Starter Prompt Manager")
        self._window.setMinSize_(NSMakeSize(700, 480))
        self._window.setDelegate_(self)
        self._window.center()

        content = self._window.contentView()
        content.setAutoresizesSubviews_(True)

        # --- Toolbar row 1 (buttons) ---
        ty = MGR_HEIGHT - 46
        self._build_toolbar(content, ty)

        # --- Separator ---
        sep = AppKit.NSBox.alloc().initWithFrame_(NSMakeRect(0, ty - 38, MGR_WIDTH, 1))
        sep.setBoxType_(AppKit.NSBoxSeparator)
        sep.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        content.addSubview_(sep)

        # --- Main area: sidebar + editor ---
        main_top = ty - 42
        main_bottom = 52
        main_h = main_top - main_bottom
        sidebar_w = 240

        # Sidebar: outline view (Environment -> Category -> Prompt)
        sidebar_scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, main_bottom, sidebar_w, main_h)
        )
        sidebar_scroll.setHasVerticalScroller_(True)
        sidebar_scroll.setBorderType_(AppKit.NSBezelBorder)
        sidebar_scroll.setAutoresizingMask_(AppKit.NSViewHeightSizable)

        outline = AppKit.NSOutlineView.alloc().initWithFrame_(sidebar_scroll.bounds())
        col = AppKit.NSTableColumn.alloc().initWithIdentifier_("name")
        col.setWidth_(sidebar_w - 24)
        outline.addTableColumn_(col)
        outline.setOutlineTableColumn_(col)
        outline.setHeaderView_(None)
        outline.setIndentationPerLevel_(14)
        outline.setRowHeight_(22)
        outline.setDelegate_(self)
        outline.setDataSource_(self)

        sidebar_scroll.setDocumentView_(outline)
        content.addSubview_(sidebar_scroll)
        self._outline = outline

        # Editor: editable text view
        editor_x = sidebar_w + 1
        editor_w = MGR_WIDTH - editor_x

        editor_scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(editor_x, main_bottom, editor_w, main_h)
        )
        editor_scroll.setHasVerticalScroller_(True)
        editor_scroll.setBorderType_(AppKit.NSBezelBorder)
        editor_scroll.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        tv = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, editor_w - 16, main_h)
        )
        tv.setEditable_(True)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(12.5, 0.0))
        tv.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        tv.setTextContainerInset_(NSMakeSize(8, 8))
        tv.setAllowsUndo_(True)
        tv.setDelegate_(self)
        editor_scroll.setDocumentView_(tv)
        content.addSubview_(editor_scroll)
        self._editor = tv

        # --- Bottom bar ---
        self._build_bottom_bar(content)

        # Expand all nodes
        self._expand_all()

    def _build_toolbar(self, parent, y):
        x = 12

        new_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 65, 28))
        new_btn.setTitle_("+ New")
        new_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        new_btn.setTarget_(self)
        new_btn.setAction_(objc.selector(self.newPrompt_, signature=b"v@:@"))
        parent.addSubview_(new_btn)
        x += 71

        ren_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 72, 28))
        ren_btn.setTitle_("Rename")
        ren_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        ren_btn.setTarget_(self)
        ren_btn.setAction_(objc.selector(self.renamePrompt_, signature=b"v@:@"))
        parent.addSubview_(ren_btn)
        x += 78

        del_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 65, 28))
        del_btn.setTitle_("Delete")
        del_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        del_btn.setTarget_(self)
        del_btn.setAction_(objc.selector(self.deletePrompt_, signature=b"v@:@"))
        parent.addSubview_(del_btn)
        x += 71

        hist_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 70, 28))
        hist_btn.setTitle_("History")
        hist_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        hist_btn.setTarget_(self)
        hist_btn.setAction_(objc.selector(self.showHistory_, signature=b"v@:@"))
        parent.addSubview_(hist_btn)
        x += 78

        var_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 62, 28))
        var_btn.setTitle_("{} Var")
        var_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        var_btn.setTarget_(self)
        var_btn.setAction_(objc.selector(self.insertVariable_, signature=b"v@:@"))
        parent.addSubview_(var_btn)
        x += 68

        insights_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 75, 28))
        insights_btn.setTitle_("Insights")
        insights_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        insights_btn.setTarget_(self)
        insights_btn.setAction_(objc.selector(self.showInsights_, signature=b"v@:@"))
        parent.addSubview_(insights_btn)
        x += 81

        ai_btn = AppKit.NSButton.alloc().initWithFrame_(NSMakeRect(x, y, 90, 28))
        ai_btn.setTitle_("AI Analyze")
        ai_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        ai_btn.setTarget_(self)
        ai_btn.setAction_(objc.selector(self.aiAnalyze_, signature=b"v@:@"))
        parent.addSubview_(ai_btn)

        # --- Row 2: Environment + Category dropdowns ---
        y2 = y - 34
        x2 = 12

        env_lbl = AppKit.NSTextField.labelWithString_("Environment:")
        env_lbl.setFrame_(NSMakeRect(x2, y2 + 4, 82, 20))
        env_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        parent.addSubview_(env_lbl)
        x2 += 84

        env_w = 160
        env_popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            NSMakeRect(x2, y2, env_w, 28)
        )
        env_popup.setTarget_(self)
        env_popup.setAction_(objc.selector(self.envChanged_, signature=b"v@:@"))
        parent.addSubview_(env_popup)
        self._env_popup = env_popup
        x2 += env_w + 20

        cat_lbl = AppKit.NSTextField.labelWithString_("Category:")
        cat_lbl.setFrame_(NSMakeRect(x2, y2 + 4, 62, 20))
        cat_lbl.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        parent.addSubview_(cat_lbl)
        x2 += 64

        cat_w = 160
        cat_popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
            NSMakeRect(x2, y2, cat_w, 28)
        )
        cat_popup.setTarget_(self)
        cat_popup.setAction_(objc.selector(self.categoryChanged_, signature=b"v@:@"))
        parent.addSubview_(cat_popup)
        self._cat_popup = cat_popup

        self._rebuild_popups()

    def _rebuild_popups(self):
        """Rebuild both the Environment and Category dropdown menus."""
        # Environment popup
        self._env_popup.removeAllItems()
        self._env_popup.addItemWithTitle_(NO_ENVIRONMENT)
        for env in list_environments():
            self._env_popup.addItemWithTitle_(env)
        self._env_popup.menu().addItem_(AppKit.NSMenuItem.separatorItem())
        self._env_popup.addItemWithTitle_("New Environment...")
        self._env_popup.menu().addItem_(AppKit.NSMenuItem.separatorItem())
        self._env_popup.addItemWithTitle_("Rename Environment...")

        # Category popup
        self._cat_popup.removeAllItems()
        self._cat_popup.addItemWithTitle_(UNCATEGORIZED)
        for cat in list_categories():
            self._cat_popup.addItemWithTitle_(cat)
        self._cat_popup.menu().addItem_(AppKit.NSMenuItem.separatorItem())
        self._cat_popup.addItemWithTitle_("New Category...")
        self._cat_popup.menu().addItem_(AppKit.NSMenuItem.separatorItem())
        self._cat_popup.addItemWithTitle_("Rename Category...")

    def _build_bottom_bar(self, parent):
        bw = MGR_WIDTH

        revert_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(bw - 240, 12, 100, 28)
        )
        revert_btn.setTitle_("Revert")
        revert_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        revert_btn.setTarget_(self)
        revert_btn.setAction_(objc.selector(self.revertChanges_, signature=b"v@:@"))
        revert_btn.setEnabled_(False)
        revert_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        parent.addSubview_(revert_btn)
        self._revert_btn = revert_btn

        save_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(bw - 130, 12, 110, 28)
        )
        save_btn.setTitle_("Save")
        save_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        save_btn.setKeyEquivalent_("s")
        save_btn.setKeyEquivalentModifierMask_(AppKit.NSEventModifierFlagCommand)
        save_btn.setTarget_(self)
        save_btn.setAction_(objc.selector(self.saveChanges_, signature=b"v@:@"))
        save_btn.setEnabled_(False)
        save_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        parent.addSubview_(save_btn)
        self._save_btn = save_btn

        # Status label
        status = AppKit.NSTextField.labelWithString_("")
        status.setFrame_(NSMakeRect(12, 16, bw - 260, 18))
        status.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        status.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        status.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        parent.addSubview_(status)
        self._status_label = status

    def _expand_all(self):
        """Expand every environment and category node in the outline."""
        for env_key, cats in self._tree:
            self._outline.expandItem_(env_key)
            for cat_key, _ in cats:
                self._outline.expandItem_(cat_key)

    # ------------------------------------------------------------------
    # NSOutlineView data source (3-level: env -> cat -> prompt)
    # ------------------------------------------------------------------

    def outlineView_numberOfChildrenOfItem_(self, ov, item):
        if item is None:
            return len(self._tree)
        if self._is_env_key(item):
            for env_key, cats in self._tree:
                if env_key == item:
                    return len(cats)
        if self._is_cat_key(item):
            for env_key, cats in self._tree:
                for cat_key, filenames in cats:
                    if cat_key == item:
                        return len(filenames)
        return 0

    def outlineView_isItemExpandable_(self, ov, item):
        return self._is_env_key(item) or self._is_cat_key(item)

    def outlineView_child_ofItem_(self, ov, index, item):
        if item is None:
            return self._tree[index][0]  # env_key
        if self._is_env_key(item):
            for env_key, cats in self._tree:
                if env_key == item:
                    return cats[index][0]  # cat_key
        if self._is_cat_key(item):
            for env_key, cats in self._tree:
                for cat_key, filenames in cats:
                    if cat_key == item:
                        return filenames[index]  # filename string
        return None

    def outlineView_objectValueForTableColumn_byItem_(self, ov, col, item):
        if self._is_env_key(item):
            return self._env_name_from_key(item)
        if self._is_cat_key(item):
            return self._cat_name_from_key(item)
        # It's a filename — show the display name + badges
        p = self._find_prompt(item)
        if not p:
            return str(item)
        name = p["name"]
        badges = []
        # Variable count badge
        content = get_prompt(item)
        if content:
            var_count = len(parse_variables(content))
            if var_count > 0:
                badges.append(f"{var_count} var{'s' if var_count != 1 else ''}")
        # Usage count badge from analytics
        stats = getattr(self, '_prompt_stats', {}).get(item, {})
        times_used = stats.get("times_used", 0)
        if times_used > 0:
            badges.append(f"\u2713{times_used}")
        avg_rating = stats.get("avg_rating")
        if avg_rating is not None:
            stars = "\u2605" * round(avg_rating)
            badges.append(stars)
        if badges:
            name += "  (" + ", ".join(badges) + ")"
        return name

    # ------------------------------------------------------------------
    # NSOutlineView delegate
    # ------------------------------------------------------------------

    def outlineView_isGroupItem_(self, ov, item):
        return self._is_env_key(item)

    def outlineView_shouldSelectItem_(self, ov, item):
        return self._is_prompt_key(item)

    def outlineViewSelectionDidChange_(self, notification):
        row = self._outline.selectedRow()
        if row < 0:
            return
        item = self._outline.itemAtRow_(row)
        if item and self._is_prompt_key(item):
            self._load_prompt(item)

    # ------------------------------------------------------------------
    # NSTextView delegate (track edits)
    # ------------------------------------------------------------------

    def textDidChange_(self, notification):
        if self._selected_filename and not self._dirty:
            self._dirty = True
            self._save_btn.setEnabled_(True)
            self._revert_btn.setEnabled_(True)
            self._status_label.setStringValue_("Unsaved changes")

    # ------------------------------------------------------------------
    # Prompt loading
    # ------------------------------------------------------------------

    def _load_prompt(self, filename):
        """Load a prompt into the editor."""
        if self._dirty:
            if not self._confirm_discard():
                return

        self._selected_filename = filename
        content = get_prompt(filename) or ""
        self._editor.setString_(content)
        self._editor.setEditable_(True)
        self._editor.scrollRangeToVisible_(NSMakeRange(0, 0))
        self._dirty = False
        self._save_btn.setEnabled_(False)
        self._revert_btn.setEnabled_(False)

        # Update dropdowns
        p = self._find_prompt(filename)
        env = p.get("environment", "") if p else ""
        cat = p.get("category", "") if p else ""

        env_title = env or NO_ENVIRONMENT
        if self._env_popup.indexOfItemWithTitle_(env_title) >= 0:
            self._env_popup.selectItemWithTitle_(env_title)
        else:
            self._env_popup.selectItemWithTitle_(NO_ENVIRONMENT)

        cat_title = cat or UNCATEGORIZED
        if self._cat_popup.indexOfItemWithTitle_(cat_title) >= 0:
            self._cat_popup.selectItemWithTitle_(cat_title)
        else:
            self._cat_popup.selectItemWithTitle_(UNCATEGORIZED)

        prompt_name = p["name"] if p else filename

        # Build status with usage stats
        stats = getattr(self, '_prompt_stats', {}).get(filename, {})
        times_used = stats.get("times_used", 0)
        avg_rating = stats.get("avg_rating")
        stat_parts = [f"Editing: {prompt_name}"]
        if times_used > 0:
            stat_parts.append(f"Used {times_used}x")
            if avg_rating is not None:
                stat_parts.append(f"Avg rating: {avg_rating}/4")
            last_used = stats.get("last_used")
            if last_used:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(last_used)
                    stat_parts.append(f"Last: {dt.strftime('%b %d')}")
                except Exception:
                    pass
        else:
            stat_parts.append("Not yet used")
        self._status_label.setStringValue_("  \u2014  ".join(stat_parts))

        from cursorhub.analytics import log_event
        log_event("prompt_viewed", prompt_filename=filename)

    def _select_first(self):
        """Select the first prompt in the outline."""
        for env_key, cats in self._tree:
            for cat_key, filenames in cats:
                if filenames:
                    fn = filenames[0]
                    self._outline.expandItem_(env_key)
                    self._outline.expandItem_(cat_key)
                    row = self._outline.rowForItem_(fn)
                    if row >= 0:
                        idx_set = AppKit.NSIndexSet.indexSetWithIndex_(row)
                        self._outline.selectRowIndexes_byExtendingSelection_(idx_set, False)
                        self._load_prompt(fn)
                        return
        # No prompts
        self._editor.setString_(
            "No starter prompts yet.\n\n"
            "Click \"+ New\" in the toolbar above to create your first one.\n\n"
            "Starter prompts define a role and instructions for your AI\n"
            "assistant when you kick off a new project.\n"
        )
        self._editor.setEditable_(False)
        self._status_label.setStringValue_("Click \"+ New\" to create a starter prompt")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @objc.typedSelector(b"v@:@")
    def newPrompt_(self, sender):
        """Create a new starter prompt."""
        if self._dirty and not self._confirm_discard():
            return

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("New Starter Prompt")
        alert.setInformativeText_("Enter a name for the new prompt:")
        alert.addButtonWithTitle_("Create")
        alert.addButtonWithTitle_("Cancel")

        name_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setPlaceholderString_("e.g. Full-Stack Web App")
        alert.setAccessoryView_(name_field)
        alert.window().setInitialFirstResponder_(name_field)

        result = alert.runModal()
        if result != AppKit.NSAlertFirstButtonReturn:
            return

        name = name_field.stringValue().strip()
        if not name:
            return

        skeleton = (
            f"# {name}\n\n"
            f"You are an expert AI assistant.\n\n"
            f"## Role\n\n"
            f"Describe the AI's role and expertise here.\n\n"
            f"## Instructions\n\n"
            f"- Step-by-step instructions for the AI\n"
            f"- Technologies to use\n"
            f"- Architecture decisions\n"
            f"- Any other setup steps\n"
        )

        # Use current dropdown selections
        env = self._env_popup.titleOfSelectedItem()
        if env in (NO_ENVIRONMENT, "New Environment...", "Rename Environment..."):
            env = ""
        cat = self._cat_popup.titleOfSelectedItem()
        if cat in (UNCATEGORIZED, "New Category...", "Rename Category..."):
            cat = ""

        path = create_prompt(name, skeleton, category=cat, environment=env)
        self._dirty = False
        self._refresh_and_select(path.name)
        self._status_label.setStringValue_(
            f"Created \"{name}\" \u2014 Edit the content, then Save (\u2318S)"
        )

    @objc.typedSelector(b"v@:@")
    def renamePrompt_(self, sender):
        """Rename the selected prompt."""
        if not self._selected_filename:
            self._show_alert("No prompt selected.\n\nSelect a prompt from the sidebar first.")
            return

        p = self._find_prompt(self._selected_filename)
        current_name = p["name"] if p else self._selected_filename

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Rename Starter Prompt")
        alert.setInformativeText_(f"Current name: {current_name}\n\nEnter a new name:")
        alert.addButtonWithTitle_("Rename")
        alert.addButtonWithTitle_("Cancel")

        name_field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 300, 24))
        name_field.setStringValue_(current_name)
        alert.setAccessoryView_(name_field)
        alert.window().setInitialFirstResponder_(name_field)

        result = alert.runModal()
        if result != AppKit.NSAlertFirstButtonReturn:
            return

        new_name = name_field.stringValue().strip()
        if not new_name or new_name == current_name:
            return

        try:
            new_filename = rename_prompt(self._selected_filename, new_name)
            self._refresh_and_select(new_filename)
            self._status_label.setStringValue_(f"Renamed to \"{new_name}\"")
        except FileExistsError as e:
            self._show_alert(str(e))
        except Exception as e:
            self._show_alert(f"Could not rename: {e}")

    @objc.typedSelector(b"v@:@")
    def deletePrompt_(self, sender):
        """Delete the selected prompt."""
        if not self._selected_filename:
            self._show_alert("No prompt selected.\n\nSelect a prompt from the sidebar first.")
            return

        p = self._find_prompt(self._selected_filename)
        display = p["name"] if p else self._selected_filename

        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Delete Starter Prompt")
        alert.setInformativeText_(
            f"Are you sure you want to delete \"{display}\"?\n\n"
            "Edit history will be preserved."
        )
        alert.setAlertStyle_(AppKit.NSAlertStyleWarning)
        alert.addButtonWithTitle_("Delete")
        alert.addButtonWithTitle_("Cancel")

        if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
            return

        delete_prompt(self._selected_filename)
        self._selected_filename = None
        self._dirty = False
        self._editor.setString_("")
        self._refresh_and_select(None)
        self._status_label.setStringValue_("Prompt deleted.")

    @objc.typedSelector(b"v@:@")
    def showHistory_(self, sender):
        """Show the version history for the selected prompt."""
        try:
            if not self._selected_filename:
                self._show_alert("No prompt selected.")
                return

            history = get_prompt_history(self._selected_filename)
            if not history:
                self._show_alert(
                    "No edit history for this prompt yet.\n\n"
                    "History is created each time you save changes."
                )
                return

            HistorySheetController._init_filename = self._selected_filename
            HistorySheetController._init_history = history
            HistorySheetController._init_parent = self._window
            ctrl = HistorySheetController.alloc().init()
            if ctrl is None:
                self._show_alert("Failed to open history panel.")
                return
            ctrl.on_restored = lambda: self._on_history_restored()
            self._history_ctrl = ctrl
            ctrl.show()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_alert(f"Could not show history: {e}")

    @objc.typedSelector(b"v@:@")
    def insertVariable_(self, sender):
        """Insert a {{variable}} placeholder at the cursor or around selected text."""
        try:
            if not self._selected_filename:
                self._show_alert("No prompt selected.\n\nSelect a prompt first, then use this button.")
                return

            # Capture editor state BEFORE any dialogs
            editor_text = self._editor.string()
            sel_loc = self._editor.selectedRange().location
            sel_len = self._editor.selectedRange().length

            # Find existing variables in the prompt
            existing_vars = parse_variables(editor_text)

            # --- Build a single combined dialog ---
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Insert Variable")
            alert.addButtonWithTitle_("Insert")
            alert.addButtonWithTitle_("Cancel")

            # Container view with popup (if existing vars) + text field for new name
            container_width = 300
            row_gap = 8
            field_h = 28
            label_h = 16

            # Calculate height
            rows = 1  # always have the "new variable name" field
            if existing_vars:
                rows += 1  # popup for existing vars
            total_h = rows * (field_h + label_h + row_gap) + row_gap

            container = AppKit.NSView.alloc().initWithFrame_(
                NSMakeRect(0, 0, container_width, total_h)
            )

            y = total_h  # build top-down

            popup = None
            if existing_vars:
                # Label for existing vars
                y -= label_h + 4
                lbl = AppKit.NSTextField.labelWithString_("Reuse existing variable:")
                lbl.setFrame_(NSMakeRect(0, y, container_width, label_h))
                lbl.setFont_(AppKit.NSFont.systemFontOfSize_(11))
                lbl.setTextColor_(AppKit.NSColor.secondaryLabelColor())
                container.addSubview_(lbl)

                y -= field_h + row_gap
                popup = AppKit.NSPopUpButton.alloc().initWithFrame_(
                    NSMakeRect(0, y, container_width, field_h)
                )
                popup.addItemWithTitle_("— Pick existing —")
                for v in existing_vars:
                    popup.addItemWithTitle_(v)
                container.addSubview_(popup)

                alert.setInformativeText_(
                    "Pick an existing variable above, OR type a new\n"
                    "variable name below. The new name takes priority."
                )
            else:
                alert.setInformativeText_(
                    "Enter a name for the new variable.\n"
                    "Use letters, numbers, and underscores (e.g. app_name)."
                )

            # Label for new variable name
            y -= label_h + 4
            lbl2 = AppKit.NSTextField.labelWithString_("New variable name:")
            lbl2.setFrame_(NSMakeRect(0, y, container_width, label_h))
            lbl2.setFont_(AppKit.NSFont.systemFontOfSize_(11))
            lbl2.setTextColor_(AppKit.NSColor.secondaryLabelColor())
            container.addSubview_(lbl2)

            y -= field_h + row_gap
            name_field = AppKit.NSTextField.alloc().initWithFrame_(
                NSMakeRect(0, y, container_width, field_h)
            )
            name_field.setPlaceholderString_("e.g. app_name")
            container.addSubview_(name_field)

            alert.setAccessoryView_(container)
            alert.window().setInitialFirstResponder_(name_field)

            # Run the single dialog
            result = alert.runModal()
            if result != AppKit.NSAlertFirstButtonReturn:
                return

            # Determine the variable name: typed name takes priority over popup
            typed_name = name_field.stringValue().strip()
            if typed_name:
                var_name = typed_name.lower().replace(" ", "_").replace("-", "_")
                # Strip non-word chars
                import re
                var_name = re.sub(r"[^\w]", "", var_name)
            elif popup is not None:
                selected = popup.titleOfSelectedItem()
                if selected and selected != "— Pick existing —":
                    var_name = selected
                else:
                    self._status_label.setStringValue_("No variable name entered.")
                    return
            else:
                self._status_label.setStringValue_("No variable name entered.")
                return

            if not var_name:
                self._status_label.setStringValue_("No variable name entered.")
                return

            # Build the replacement text
            replacement = "{{" + var_name + "}}"

            # Insert via text storage (reliable after modal dialogs)
            ts = self._editor.textStorage()
            replace_range = NSMakeRange(sel_loc, sel_len)
            ts.replaceCharactersInRange_withString_(replace_range, replacement)

            # Place cursor after the inserted variable
            new_pos = sel_loc + len(replacement)
            self._editor.setSelectedRange_(NSMakeRange(new_pos, 0))

            # Mark as dirty
            if not self._dirty:
                self._dirty = True
                self._save_btn.setEnabled_(True)
                self._revert_btn.setEnabled_(True)
            self._status_label.setStringValue_(f"Inserted variable: {replacement}")

            from cursorhub.analytics import log_event
            log_event("variable_inserted", prompt_filename=self._selected_filename,
                      variable_name=var_name)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_alert(f"Could not insert variable: {e}")

    def _on_history_restored(self):
        if self._selected_filename:
            self._load_prompt(self._selected_filename)
            self._status_label.setStringValue_("Version restored.")

    # ------------------------------------------------------------------
    # Insights panel
    # ------------------------------------------------------------------

    @objc.typedSelector(b"v@:@")
    def showInsights_(self, sender):
        """Show the analytics insights panel."""
        try:
            from cursorhub.analytics import (
                get_all_prompt_stats, get_overall_stats,
                get_recent_activity, compute_prompt_health,
            )

            overall = get_overall_stats()
            all_stats = get_all_prompt_stats()
            activity = get_recent_activity(15)

            # Build prompt name lookup
            name_map = {}
            for p in self._prompts:
                name_map[p["filename"]] = p["name"]

            # Compute health for each prompt
            prompt_rows = []
            for p in self._prompts:
                fn = p["filename"]
                stats = all_stats.get(fn, {
                    "times_used": 0, "last_used": None,
                    "avg_rating": None, "rating_count": 0,
                    "edit_count": 0, "projects": [],
                })
                health = compute_prompt_health(stats)
                prompt_rows.append((p["name"], fn, stats, health))

            # Sort: needs_attention first, then by usage desc
            health_order = {"needs_attention": 0, "unused": 1, "new": 2, "good": 3, "great": 4}
            prompt_rows.sort(key=lambda r: (health_order.get(r[3], 5), -r[2].get("times_used", 0)))

            # --- Build the text content ---
            lines = []
            lines.append("CURSORHUB INSIGHTS")
            lines.append("=" * 50)
            lines.append("")

            # Overall stats
            lines.append("OVERVIEW")
            lines.append("-" * 30)
            lines.append(f"  Projects created:      {overall['total_projects_created']}")
            lines.append(f"  Prompts applied:       {overall['total_prompt_applications']}")
            lines.append(f"  Unique prompts used:   {overall['total_prompts_used']}")
            if overall["most_used_prompt"]:
                most_name = name_map.get(overall["most_used_prompt"],
                                         overall["most_used_prompt"])
                lines.append(f"  Most used prompt:      {most_name}")
            if overall["avg_rating_all"] is not None:
                lines.append(f"  Overall avg rating:    {overall['avg_rating_all']}/4")
            lines.append(f"  Events (last 30 days): {overall['events_last_30_days']}")
            lines.append("")

            # Needs attention
            attention = [r for r in prompt_rows if r[3] == "needs_attention"]
            if attention:
                lines.append("NEEDS ATTENTION")
                lines.append("-" * 30)
                for name, fn, stats, health in attention:
                    reason = ""
                    if stats.get("avg_rating") and stats["avg_rating"] < 2.5:
                        reason = f"low rating ({stats['avg_rating']}/4)"
                    elif stats.get("edit_count", 0) > stats.get("times_used", 0) * 2:
                        reason = "frequently edited after use"
                    lines.append(f"  \u26a0 {name}: {reason}")
                lines.append("")

            # Top prompts
            used = [r for r in prompt_rows if r[2].get("times_used", 0) > 0]
            if used:
                used.sort(key=lambda r: -r[2]["times_used"])
                lines.append("TOP PROMPTS")
                lines.append("-" * 30)
                for name, fn, stats, health in used[:5]:
                    rating_str = f", {stats['avg_rating']}/4" if stats.get("avg_rating") else ""
                    lines.append(f"  \u2713 {name}: used {stats['times_used']}x{rating_str}")
                lines.append("")

            # Unused prompts
            unused = [r for r in prompt_rows
                      if r[2].get("times_used", 0) == 0 and r[3] != "new"]
            if unused:
                lines.append("UNUSED PROMPTS")
                lines.append("-" * 30)
                for name, fn, stats, health in unused:
                    lines.append(f"  \u25cb {name}: created but never applied")
                lines.append("")

            # New prompts (no usage data yet)
            new_prompts = [r for r in prompt_rows if r[3] == "new"]
            if new_prompts:
                lines.append("NEW (no data yet)")
                lines.append("-" * 30)
                for name, fn, stats, health in new_prompts:
                    lines.append(f"  \u25cb {name}")
                lines.append("")

            # Recent activity
            if activity:
                lines.append("RECENT ACTIVITY")
                lines.append("-" * 30)
                for evt in activity:
                    from datetime import datetime as _dt
                    try:
                        ts = _dt.fromisoformat(evt["timestamp"]).strftime("%b %d %H:%M")
                    except Exception:
                        ts = evt["timestamp"][:16]
                    event_name = evt["event"].replace("_", " ").title()
                    detail = ""
                    if evt.get("prompt_filename"):
                        pname = name_map.get(evt["prompt_filename"],
                                             evt["prompt_filename"])
                        detail = f" — {pname}"
                    elif evt.get("project_path"):
                        detail = f" — {Path(evt['project_path']).name}"
                    lines.append(f"  {ts}  {event_name}{detail}")
                lines.append("")

            # Health summary
            lines.append("PROMPT HEALTH SUMMARY")
            lines.append("-" * 30)
            for name, fn, stats, health in prompt_rows:
                icon = {"great": "\u2605", "good": "\u2713", "needs_attention": "\u26a0",
                        "unused": "\u25cb", "new": "\u25cf"}.get(health, "?")
                lines.append(f"  {icon} {name}: {health.replace('_', ' ')}")
            lines.append("")

            report = "\n".join(lines)

            # --- Show in a window ---
            self._show_insights_window(report)

            # --- Check if Gemini key is configured and append AI overview ---
            from cursorhub.config import get_config_value
            api_key = get_config_value("gemini_api_key")
            if api_key:
                # Append a placeholder, then fetch AI overview in background
                placeholder = (
                    "\n\n" + "=" * 50 + "\n"
                    "AI-POWERED OVERVIEW (Gemini)\n"
                    "=" * 50 + "\n\n"
                    "Loading AI analysis..."
                )
                self._insights_tv.setString_(report + placeholder)

                import threading

                def _fetch_overview():
                    from cursorhub.ai_analysis import analyze_overview
                    try:
                        ai_text = analyze_overview(api_key)
                        full_text = (
                            report + "\n\n" + "=" * 50 + "\n"
                            "AI-POWERED OVERVIEW (Gemini)\n"
                            "=" * 50 + "\n\n" + ai_text
                        )
                    except Exception as exc:
                        full_text = (
                            report + "\n\n" + "=" * 50 + "\n"
                            "AI-POWERED OVERVIEW (Gemini)\n"
                            "=" * 50 + "\n\n"
                            f"Error: {exc}"
                        )
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self._updateInsightsText_, signature=b"v@:@"),
                        full_text,
                        False,
                    )

                t = threading.Thread(target=_fetch_overview, daemon=True)
                t.start()
            else:
                # No API key — show a hint so the user knows AI insights are available
                hint = (
                    "\n\n" + "-" * 50 + "\n"
                    "TIP: Add a Gemini API key to get AI-powered insights.\n"
                    "  cursorhub config set gemini_api_key YOUR_KEY\n"
                    "-" * 50
                )
                self._insights_tv.setString_(report + hint)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_alert(f"Could not load insights: {e}")

    @objc.typedSelector(b"v@:@")
    def _updateInsightsText_(self, text):
        """Update the insights text view content (called on main thread)."""
        try:
            if hasattr(self, "_insights_tv") and self._insights_tv:
                self._insights_tv.setString_(text)
        except Exception:
            pass

    def _show_insights_window(self, report_text):
        """Display the insights report in a window."""
        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
            | AppKit.NSResizableWindowMask
        )
        win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 150, 560, 520),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("Prompt Insights")
        win.setMinSize_(NSMakeSize(400, 300))
        win.center()

        content = win.contentView()

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(content.bounds())
        scroll.setHasVerticalScroller_(True)
        scroll.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        tv = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 540, 500)
        )
        tv.setEditable_(False)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(12, 0.0))
        tv.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        tv.setTextContainerInset_(NSMakeSize(12, 12))
        tv.setString_(report_text)

        scroll.setDocumentView_(tv)
        content.addSubview_(scroll)

        # Keep reference to prevent GC
        self._insights_window = win
        self._insights_tv = tv

        win.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    @objc.typedSelector(b"v@:@")
    def aiAnalyze_(self, sender):
        """Run AI analysis on the currently selected prompt or full portfolio."""
        try:
            from cursorhub.config import get_config_value

            api_key = get_config_value("gemini_api_key")
            if not api_key:
                self._show_alert(
                    "No Gemini API key configured.\n\n"
                    "Set one from the terminal:\n"
                    "  cursorhub config set gemini_api_key YOUR_KEY"
                )
                return

            # Determine if we're analysing a specific prompt or the whole portfolio
            filename = None
            if self._selected_filename:
                filename = self._selected_filename

            # Show a "working" indicator window immediately
            self._show_ai_working_window()

            # Run analysis in background thread to keep UI responsive
            import threading

            def _run_analysis():
                from cursorhub.ai_analysis import analyze_prompt, analyze_overview
                from cursorhub.analytics import log_event

                try:
                    if filename:
                        result = analyze_prompt(filename, api_key)
                        log_event("ai_analysis_prompt", prompt_filename=filename)
                    else:
                        result = analyze_overview(api_key)
                        log_event("ai_analysis_overview")

                    # Update UI on main thread
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self._showAIResult_, signature=b"v@:@"),
                        result,
                        False,
                    )
                except Exception as exc:
                    import traceback
                    traceback.print_exc()
                    error_msg = f"AI analysis failed: {exc}"
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        objc.selector(self._showAIResult_, signature=b"v@:@"),
                        error_msg,
                        False,
                    )

            t = threading.Thread(target=_run_analysis, daemon=True)
            t.start()

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_alert(f"Could not start AI analysis: {e}")

    def _show_ai_working_window(self):
        """Show a small window indicating AI analysis is in progress."""
        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
            | AppKit.NSResizableWindowMask
        )
        win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 150, 560, 520),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("AI Analysis — Gemini")
        win.setMinSize_(NSMakeSize(400, 300))
        win.center()

        content = win.contentView()

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(content.bounds())
        scroll.setHasVerticalScroller_(True)
        scroll.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        tv = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, 540, 500)
        )
        tv.setEditable_(False)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(12, 0.0))
        tv.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        tv.setTextContainerInset_(NSMakeSize(12, 12))
        tv.setString_("Calling Gemini AI for analysis...\n\nThis may take a few seconds.")

        scroll.setDocumentView_(tv)
        content.addSubview_(scroll)

        self._ai_window = win
        self._ai_text_view = tv

        win.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    @objc.typedSelector(b"v@:@")
    def _showAIResult_(self, result_text):
        """Update the AI analysis window with the result (called on main thread)."""
        try:
            if hasattr(self, "_ai_text_view") and self._ai_text_view:
                self._ai_text_view.setString_(result_text)
                # Scroll to top
                self._ai_text_view.scrollRangeToVisible_(AppKit.NSMakeRange(0, 0))
            if hasattr(self, "_ai_window") and self._ai_window:
                self._ai_window.setTitle_("AI Analysis — Gemini (Complete)")
        except Exception:
            import traceback
            traceback.print_exc()

    @objc.typedSelector(b"v@:@")
    def envChanged_(self, sender):
        """Handle environment popup selection."""
        selected = self._env_popup.titleOfSelectedItem()

        if selected == "New Environment...":
            new_val = self._ask_for_name("New Environment",
                                          "Enter a name for the new environment:\n\n"
                                          "This creates the environment. You can then\n"
                                          "assign prompts to it from this dropdown.",
                                          "e.g. Cursor, ChatGPT, Figma")
            if new_val:
                add_environment(new_val)
                self._rebuild_popups()
                # Don't assign to current prompt — just select it in dropdown
                self._env_popup.selectItemWithTitle_(new_val)
                self._status_label.setStringValue_(
                    f"Created environment \"{new_val}\" \u2014 "
                    f"Select a prompt and choose it to assign"
                )
            else:
                self._revert_env_popup()
            return

        if selected == "Rename Environment...":
            self._rename_environment_flow()
            return

        # Regular selection — move current prompt to this environment
        if not self._selected_filename:
            return
        env = "" if selected == NO_ENVIRONMENT else selected
        p = self._find_prompt(self._selected_filename)
        prompt_name = p["name"] if p else self._selected_filename
        set_prompt_environment(self._selected_filename, env)
        self._refresh_and_select(self._selected_filename)
        self._status_label.setStringValue_(
            f"Moved \"{prompt_name}\" to {selected}"
        )

    @objc.typedSelector(b"v@:@")
    def categoryChanged_(self, sender):
        """Handle category popup selection."""
        selected = self._cat_popup.titleOfSelectedItem()

        if selected == "New Category...":
            new_val = self._ask_for_name("New Category",
                                          "Enter a name for the new category:\n\n"
                                          "This creates the category. You can then\n"
                                          "assign prompts to it from this dropdown.",
                                          "e.g. Web Development")
            if new_val:
                add_category(new_val)
                self._rebuild_popups()
                self._cat_popup.selectItemWithTitle_(new_val)
                self._status_label.setStringValue_(
                    f"Created category \"{new_val}\" \u2014 "
                    f"Select a prompt and choose it to assign"
                )
            else:
                self._revert_cat_popup()
            return

        if selected == "Rename Category...":
            self._rename_category_flow()
            return

        # Regular selection — move current prompt to this category
        if not self._selected_filename:
            return
        cat = "" if selected == UNCATEGORIZED else selected
        p = self._find_prompt(self._selected_filename)
        prompt_name = p["name"] if p else self._selected_filename
        set_prompt_category(self._selected_filename, cat)
        self._refresh_and_select(self._selected_filename)
        self._status_label.setStringValue_(
            f"Moved \"{prompt_name}\" to {selected}"
        )

    @objc.typedSelector(b"v@:@")
    def saveChanges_(self, sender):
        """Save edits to the current prompt (with history backup)."""
        if not self._selected_filename:
            return
        new_content = self._editor.string()
        edit_prompt(self._selected_filename, new_content)
        self._dirty = False
        self._save_btn.setEnabled_(False)
        self._revert_btn.setEnabled_(False)
        self._reload_data()
        p = self._find_prompt(self._selected_filename)
        name = p["name"] if p else self._selected_filename
        self._status_label.setStringValue_(
            f"Saved \"{name}\" \u2014 Previous version archived in History"
        )

    @objc.typedSelector(b"v@:@")
    def revertChanges_(self, sender):
        """Discard unsaved edits and reload from disk."""
        if self._selected_filename:
            self._load_prompt(self._selected_filename)
            self._status_label.setStringValue_("Reverted to saved version.")

    # ------------------------------------------------------------------
    # Rename flows for environments & categories
    # ------------------------------------------------------------------

    def _rename_environment_flow(self):
        """Ask which environment to rename, then rename it across all prompts."""
        envs = list_environments()
        if not envs:
            self._show_alert("No environments to rename.\n\nAssign an environment to a prompt first.")
            self._revert_env_popup()
            return

        # Pick which env to rename
        old_name = self._pick_from_list("Rename Environment",
                                         "Select the environment to rename:", envs)
        if not old_name:
            self._revert_env_popup()
            return

        new_name = self._ask_for_name("Rename Environment",
                                       f"Rename \"{old_name}\" to:", old_name)
        if not new_name or new_name == old_name:
            self._revert_env_popup()
            return

        count = rename_environment(old_name, new_name)
        self._refresh_and_select(self._selected_filename)
        self._status_label.setStringValue_(
            f"Renamed environment \"{old_name}\" \u2192 \"{new_name}\" ({count} prompts updated)"
        )

    def _rename_category_flow(self):
        """Ask which category to rename, then rename it across all prompts."""
        cats = list_categories()
        if not cats:
            self._show_alert("No categories to rename.\n\nAssign a category to a prompt first.")
            self._revert_cat_popup()
            return

        old_name = self._pick_from_list("Rename Category",
                                         "Select the category to rename:", cats)
        if not old_name:
            self._revert_cat_popup()
            return

        new_name = self._ask_for_name("Rename Category",
                                       f"Rename \"{old_name}\" to:", old_name)
        if not new_name or new_name == old_name:
            self._revert_cat_popup()
            return

        count = rename_category(old_name, new_name)
        self._refresh_and_select(self._selected_filename)
        self._status_label.setStringValue_(
            f"Renamed category \"{old_name}\" \u2192 \"{new_name}\" ({count} prompts updated)"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_and_select(self, filename):
        """Reload data, rebuild outline, expand all, and select a prompt by filename."""
        self._dirty = False
        self._reload_data()
        self._outline.reloadData()
        self._rebuild_popups()
        self._expand_all()
        if filename:
            row = self._outline.rowForItem_(filename)
            if row >= 0:
                idx_set = AppKit.NSIndexSet.indexSetWithIndex_(row)
                self._outline.selectRowIndexes_byExtendingSelection_(idx_set, False)
                self._load_prompt(filename)
                return
        self._select_first()

    def _revert_env_popup(self):
        """Revert env popup to current prompt's environment."""
        p = self._find_prompt(self._selected_filename) if self._selected_filename else None
        env = p.get("environment", "") if p else ""
        self._env_popup.selectItemWithTitle_(env or NO_ENVIRONMENT)

    def _revert_cat_popup(self):
        """Revert cat popup to current prompt's category."""
        p = self._find_prompt(self._selected_filename) if self._selected_filename else None
        cat = p.get("category", "") if p else ""
        self._cat_popup.selectItemWithTitle_(cat or UNCATEGORIZED)

    def _ask_for_name(self, title, info, placeholder=""):
        """Show a text input dialog. Returns the entered string or None."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(info)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")

        field = AppKit.NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 280, 24))
        field.setPlaceholderString_(placeholder)
        if placeholder and not placeholder.startswith("e.g."):
            field.setStringValue_(placeholder)
        alert.setAccessoryView_(field)
        alert.window().setInitialFirstResponder_(field)

        if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
            return None
        val = field.stringValue().strip()
        return val if val else None

    def _pick_from_list(self, title, info, items):
        """Show a popup-based picker dialog. Returns selected string or None."""
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(info)
        alert.addButtonWithTitle_("Select")
        alert.addButtonWithTitle_("Cancel")

        popup = AppKit.NSPopUpButton.alloc().initWithFrame_(NSMakeRect(0, 0, 280, 28))
        for item in items:
            popup.addItemWithTitle_(item)
        alert.setAccessoryView_(popup)

        if alert.runModal() != AppKit.NSAlertFirstButtonReturn:
            return None
        return popup.titleOfSelectedItem()

    def _confirm_discard(self) -> bool:
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("Unsaved Changes")
        alert.setInformativeText_("You have unsaved changes. Discard them?")
        alert.addButtonWithTitle_("Discard")
        alert.addButtonWithTitle_("Cancel")
        return alert.runModal() == AppKit.NSAlertFirstButtonReturn

    def _show_alert(self, message):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("CursorHub")
        alert.setInformativeText_(message)
        alert.runModal()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def showWindow(self):
        """Display the manager window."""
        self._reload_data()
        self._outline.reloadData()
        self._rebuild_popups()
        self._expand_all()
        self._select_first()
        self._window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

    # ------------------------------------------------------------------
    # Window delegate — clean up to prevent segfaults on dealloc
    # ------------------------------------------------------------------

    def windowWillClose_(self, notification):
        """Nil out delegates before the window is deallocated."""
        try:
            if hasattr(self, '_outline') and self._outline is not None:
                self._outline.setDelegate_(None)
                self._outline.setDataSource_(None)
            if hasattr(self, '_editor') and self._editor is not None:
                self._editor.setDelegate_(None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HistorySheetController — version history panel (sheet)
# ---------------------------------------------------------------------------

HIST_WIDTH = 560
HIST_HEIGHT = 420


class HistorySheetController(NSObject):
    """Controller for the version history sheet."""

    on_restored = None  # callback after a version is restored

    # Set these class attrs before alloc().init()
    _init_filename = None
    _init_history = None
    _init_parent = None

    def init(self):
        self = objc.super(HistorySheetController, self).init()
        if self is None:
            return None

        self._filename = HistorySheetController._init_filename
        self._history = HistorySheetController._init_history or []
        self._parent = HistorySheetController._init_parent
        self._selected_idx = -1
        self._hist_table = None  # set before _build_sheet so data source callbacks don't crash

        self._build_sheet()
        return self

    def _build_sheet(self):
        self._sheet = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, HIST_WIDTH, HIST_HEIGHT),
            AppKit.NSTitledWindowMask,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._sheet.setTitle_(f"History: {self._filename}")

        content = self._sheet.contentView()

        # Version list (top half)
        list_h = 160
        list_scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(16, HIST_HEIGHT - list_h - 16, HIST_WIDTH - 32, list_h)
        )
        list_scroll.setHasVerticalScroller_(True)
        list_scroll.setBorderType_(AppKit.NSBezelBorder)
        list_scroll.setAutoresizingMask_(AppKit.NSViewWidthSizable)

        table = AppKit.NSTableView.alloc().initWithFrame_(list_scroll.bounds())

        ts_col = AppKit.NSTableColumn.alloc().initWithIdentifier_("timestamp")
        ts_col.setTitle_("Date")
        ts_col.setWidth_(300)
        table.addTableColumn_(ts_col)

        sz_col = AppKit.NSTableColumn.alloc().initWithIdentifier_("size")
        sz_col.setTitle_("Size")
        sz_col.setWidth_(80)
        table.addTableColumn_(sz_col)

        table.setRowHeight_(22)
        table.setDelegate_(self)
        table.setDataSource_(self)

        list_scroll.setDocumentView_(table)
        content.addSubview_(list_scroll)
        self._hist_table = table

        # Preview label
        preview_top = HIST_HEIGHT - list_h - 28
        plabel = AppKit.NSTextField.labelWithString_("Preview:")
        plabel.setFrame_(NSMakeRect(16, preview_top, 100, 18))
        plabel.setFont_(AppKit.NSFont.boldSystemFontOfSize_(11))
        content.addSubview_(plabel)

        # Preview text view (bottom half)
        preview_h = preview_top - 60
        preview_scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(16, 50, HIST_WIDTH - 32, preview_h)
        )
        preview_scroll.setHasVerticalScroller_(True)
        preview_scroll.setBorderType_(AppKit.NSBezelBorder)
        preview_scroll.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )

        tv = AppKit.NSTextView.alloc().initWithFrame_(preview_scroll.bounds())
        tv.setEditable_(False)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.monospacedSystemFontOfSize_weight_(11, 0.0))
        tv.setTextContainerInset_(NSMakeSize(6, 6))
        preview_scroll.setDocumentView_(tv)
        content.addSubview_(preview_scroll)
        self._preview = tv

        # Buttons
        close_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(HIST_WIDTH - 220, 12, 80, 28)
        )
        close_btn.setTitle_("Close")
        close_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        close_btn.setKeyEquivalent_("\x1b")
        close_btn.setTarget_(self)
        close_btn.setAction_(objc.selector(self.closeSheet_, signature=b"v@:@"))
        close_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        content.addSubview_(close_btn)

        restore_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(HIST_WIDTH - 130, 12, 110, 28)
        )
        restore_btn.setTitle_("Restore This")
        restore_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        restore_btn.setTarget_(self)
        restore_btn.setAction_(objc.selector(self.restoreVersion_, signature=b"v@:@"))
        restore_btn.setAutoresizingMask_(AppKit.NSViewMinXMargin)
        content.addSubview_(restore_btn)
        self._restore_btn = restore_btn

    # NSTableView data source / delegate

    def numberOfRowsInTableView_(self, table):
        return len(self._history)

    def tableView_objectValueForTableColumn_row_(self, table, col, row):
        if row >= len(self._history):
            return ""
        h = self._history[row]
        cid = col.identifier()
        if cid == "timestamp":
            return h.get("timestamp", "")
        elif cid == "size":
            size = h.get("size", 0)
            if size > 1024:
                return f"{size / 1024:.1f} KB"
            return f"{size} B"
        return ""

    def tableViewSelectionDidChange_(self, notification):
        row = notification.object().selectedRow()
        if 0 <= row < len(self._history):
            self._selected_idx = row
            h = self._history[row]
            content = get_history_content(self._filename, h["filename"])
            self._preview.setString_(content or "(could not load)")
            self._preview.scrollRangeToVisible_(NSMakeRange(0, 0))

    # Actions

    @objc.typedSelector(b"v@:@")
    def closeSheet_(self, sender):
        try:
            self._parent.endSheet_(self._sheet)
        except Exception:
            self._sheet.close()

    @objc.typedSelector(b"v@:@")
    def restoreVersion_(self, sender):
        if self._selected_idx < 0 or self._selected_idx >= len(self._history):
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("CursorHub")
            alert.setInformativeText_("Select a version to restore.")
            alert.runModal()
            return

        h = self._history[self._selected_idx]
        restore_history_version(self._filename, h["filename"])

        try:
            self._parent.endSheet_(self._sheet)
        except Exception:
            self._sheet.close()

        if self.on_restored:
            self.on_restored()

    # Public

    def show(self):
        try:
            self._parent.beginSheet_completionHandler_(self._sheet, None)
        except Exception:
            # Fallback: show as a regular window if sheet presentation fails
            import traceback
            traceback.print_exc()
            self._sheet.center()
            self._sheet.makeKeyAndOrderFront_(None)
