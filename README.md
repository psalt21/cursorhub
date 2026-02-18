# CursorHub

A macOS menu bar app for managing [Cursor IDE](https://cursor.sh) projects, starter prompts, and AI-powered analysis.

**The problem:** Cursor ties your chat history to internal workspace hashes. Open a folder slightly differently and your history vanishes. There's no built-in project switcher and no way to build up a reusable prompt library.

**The fix:** CursorHub lives in your menu bar. One click to switch projects (history intact), a full prompt library with AI analysis, and automatic backups.

---

## Install

### Prerequisites

- macOS 12 or later
- [Cursor IDE](https://cursor.sh) installed
- Python 3.9+ — check with `python3 --version`

### One-line install (recommended)

```bash
git clone https://github.com/psalt21/cursorhub.git && cd cursorhub && bash install.sh
```

This will:
1. Create a Python virtual environment
2. Install all dependencies
3. Scan for your existing Cursor projects
4. Set CursorHub to auto-start at login

The **✲** icon will appear in your menu bar.

---

## First-time setup

### 1. Set your Gemini API key (for AI features)

AI-powered prompt analysis requires a free Google Gemini key.

**Get one:**
1. Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click **Create API key** → copy it

**Add it to CursorHub:**

Click the **✲** menu bar icon → **Set Gemini API Key...** → paste your key → Save.

That's it. The menu item will change to **Gemini API Key ✓** to confirm it's active.

> You can also set it from the terminal:
> ```bash
> cursorhub config set gemini_api_key YOUR_KEY_HERE
> ```

### 2. Sync the shared prompt library (team setup)

If you're part of a team that shares prompts, you can pull the entire library with one click.

Click **✲ → Sync Prompts** → enter the shared repo URL → **Save & Sync**.

CursorHub will clone the repo and import all prompts automatically. Run **Sync Prompts** any time to pull updates.

---

## What it does

### Menu bar icon → your projects
Click any project to open it in Cursor — with your full chat history exactly where you left it.

### New Project...
Three ways to create a project:
- **From Starter Prompt** — pick a prompt from your library; CursorHub creates the folder, embeds the prompt as a Cursor rule, copies it to your clipboard, and opens Cursor
- **Clone Repository** — paste a GitHub URL (SSH or HTTPS); optionally attach a starter prompt that auto-pastes into the agent chat when Cursor opens
- **Blank Project** — just a folder

### Manage Starter Prompts...
A full visual editor for your prompt library. Create, edit, organize by environment and category, view version history, and run AI analysis on any prompt.

### AI Analysis (Gemini)
With a Gemini key configured:
- Select a prompt → **AI Analyze** — get a quality score, strengths, weaknesses, and a suggested rewrite
- No prompt selected → **AI Analyze** — get a review of your entire library with top recommendations

### Sync Prompts
Pull the latest prompts from a shared GitHub repo. Great for teams — one person updates the library and everyone else syncs with one click.

### Backup History Now
Snapshot all your Cursor chat history, composer state, and workspace data to `~/.cursorhub/backups/`.

---

## CLI

Everything is also available from the terminal:

```bash
cursorhub list                              # List all projects
cursorhub open "My Project"                 # Open in Cursor
cursorhub scan                              # Auto-discover projects
cursorhub backup                            # Backup chat history
cursorhub analyze                           # AI analysis of prompt library
cursorhub config set gemini_api_key KEY     # Set Gemini key
cursorhub config set prompt_sync_repo URL   # Set sync repo
cursorhub config list                       # View all settings
```

---

## Data location

All data is stored locally in `~/.cursorhub/`:

```
~/.cursorhub/
├── config.json          # Projects list and settings
├── prompts/             # Your starter prompt .md files
├── taxonomy.json        # Environments and categories
├── analytics.db         # Usage tracking (local only)
└── backups/             # Cursor chat history snapshots
```

---

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.cursorhub.app.plist
rm ~/Library/LaunchAgents/com.cursorhub.app.plist
rm -rf ~/.cursorhub
rm -rf ~/path/to/cursorhub   # the cloned repo folder
```
