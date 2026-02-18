#!/bin/bash
# CursorHub installer - sets up the menu bar app to auto-start on login.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.cursorhub.app.plist"

echo "=== CursorHub Installer ==="
echo ""

# Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Install/upgrade
echo "Installing CursorHub..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$SCRIPT_DIR"

# Auto-discover projects
echo "Scanning for existing Cursor projects..."
"$VENV_DIR/bin/cursorhub" scan

# Set up LaunchAgent
echo "Setting up auto-start..."
mkdir -p "$PLIST_DIR"

cat > "$PLIST_FILE" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cursorhub.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>${VENV_DIR}/bin/cursorhub</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${HOME}/.cursorhub/cursorhub.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/.cursorhub/cursorhub.err.log</string>
</dict>
</plist>
PLIST

# Load the agent
launchctl unload "$PLIST_FILE" 2>/dev/null || true
launchctl load "$PLIST_FILE"

echo ""
echo "=== Done! ==="
echo "CursorHub is now running in your menu bar (look for the * icon)."
echo "It will auto-start on login."
echo ""
echo "CLI commands:"
echo "  cursorhub list      - List projects"
echo "  cursorhub open NAME - Open a project in Cursor"
echo "  cursorhub backup    - Backup chat history"
echo "  cursorhub scan      - Discover new projects"
echo ""
echo "To stop auto-start:  launchctl unload $PLIST_FILE"
echo "To uninstall:        rm $PLIST_FILE && rm -rf ~/.cursorhub"
