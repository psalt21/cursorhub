"""Guided tour of CursorHub — narrated interactive walkthrough of every feature."""

import AppKit
import objc
from Foundation import (
    NSObject,
    NSMakeRect,
    NSMakeSize,
    NSMakeRange,
)

from cursorhub import __version__


# ---------------------------------------------------------------------------
# Voice configuration
# ---------------------------------------------------------------------------

# Preferred voices in order.  We try each until one is available.
_VOICE_PREFS = [
    "com.apple.voice.compact.en-US.Samantha",
    "com.apple.eloquence.en-US.Shelley",
    "com.apple.eloquence.en-US.Sandy",
    "com.apple.eloquence.en-US.Flo",
]

_SPEECH_RATE = 185.0  # words-per-minute — comfortable listening pace


def _pick_voice():
    """Return the identifier of the best available female English voice."""
    available = set(AppKit.NSSpeechSynthesizer.availableVoices() or [])
    for v in _VOICE_PREFS:
        if v in available:
            return v
    return AppKit.NSSpeechSynthesizer.defaultVoice()


# ---------------------------------------------------------------------------
# Tour step definitions
# ---------------------------------------------------------------------------

TOUR_STEPS = [
    # ------------------------------------------------------------------
    # 1. Welcome
    # ------------------------------------------------------------------
    {
        "title": "Welcome to CursorHub",
        "body": (
            "CursorHub is your personal command center for Cursor IDE.\n\n"

            "It lives right in your macOS menu bar and gives you:\n\n"

            "  \u2022  Instant project switching \u2014 one click to jump back into\n"
            "     any project with all your AI conversations intact\n\n"

            "  \u2022  Starter prompts \u2014 reusable instructions that tell the AI\n"
            "     exactly what to build when you kick off a new project\n\n"

            "  \u2022  Built-in analytics \u2014 the tool tracks which prompts\n"
            "     actually work and helps you improve them over time\n\n"

            "  \u2022  AI-powered analysis \u2014 connects to Google's Gemini to\n"
            "     review your prompts and give you expert feedback\n\n"

            "  \u2022  One-click backups of all your Cursor chat history\n\n"

            "This tour will walk you through everything. On some steps\n"
            "you can click \"Try It\" to see the real thing.\n\n"

            "Click Next to get started."
        ),
        "narration": (
            "Hi! Welcome to CursorHub. "
            "I'm going to walk you through everything this tool does "
            "and why it matters for your workflow. "
            "CursorHub is a little app that lives in your Mac's menu bar, "
            "right up at the top of your screen. "
            "It's built to make working with Cursor IDE way smoother. "
            "You can switch between projects instantly, "
            "build up a library of reusable starter prompts, "
            "and the tool actually learns which prompts work best "
            "over time. "
            "On some of these steps you'll be able to click Try It "
            "to see the real feature. "
            "Let's get into it. Click Next."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 2. Your Command Center
    # ------------------------------------------------------------------
    {
        "title": "Your Command Center",
        "body": (
            "The CursorHub icon sits in your menu bar at the top of\n"
            "your screen. Click it and you see all your projects.\n\n"

            "Click any project name and it opens in Cursor \u2014 with\n"
            "your full chat history, composer threads, and settings\n"
            "exactly where you left them.\n\n"

            "Why this matters: Cursor ties conversations to internal\n"
            "workspace hashes. Open a folder a slightly different way\n"
            "and your history disappears. CursorHub always opens\n"
            "projects the same way, so that never happens.\n\n"

            "You can also:\n"
            "  \u2022  Archive projects you're not actively using\n"
            "  \u2022  Delete projects when you're truly done\n"
            "  \u2022  Scan to auto-discover every project Cursor knows about"
        ),
        "narration": (
            "So, the first thing you'll notice is this little icon "
            "in your menu bar. Click it and you get a dropdown "
            "with all your projects. "
            "Tap any project name and it opens right up in Cursor "
            "with your full chat history intact. "
            "This is a bigger deal than it sounds. "
            "Cursor can lose track of your conversations if you "
            "open a folder in a slightly different way. "
            "CursorHub makes sure that never happens by always "
            "opening things consistently. "
            "You can also archive old projects to keep things tidy, "
            "or scan to automatically find every project Cursor "
            "has on your machine."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 3. Starting a New Project
    # ------------------------------------------------------------------
    {
        "title": "Starting a New Project",
        "body": (
            "Click \"New Project\" in the menu to open the creation wizard.\n"
            "You get three options:\n\n"

            "FROM STARTER PROMPT  (the powerful one)\n"
            "  Pick a prompt from your library. When you create the\n"
            "  project, CursorHub does four things automatically:\n"
            "    1. Creates the project folder\n"
            "    2. Embeds the prompt as a Cursor rule (so the AI\n"
            "       reads it automatically on every chat)\n"
            "    3. Copies the prompt to your clipboard\n"
            "    4. Opens the project in Cursor \u2014 paste and go\n\n"

            "CLONE A REPOSITORY\n"
            "  Paste a Git URL. CursorHub clones it in the background\n"
            "  and opens it in Cursor when it's done.\n\n"

            "BLANK PROJECT\n"
            "  Just a name and a location. Simple.\n\n"

            "Click \"Try It\" to see the creation wizard."
        ),
        "narration": (
            "When you're ready to start something new, "
            "you click New Project in the menu and get three choices. "
            "The first, and the most powerful, is From Starter Prompt. "
            "You pick a prompt from your library, give the project a name, "
            "and CursorHub does the rest. "
            "It creates the folder, embeds your prompt as a rule "
            "so Cursor's AI sees it automatically, "
            "copies it to your clipboard, "
            "and opens the project. You just paste and go. "
            "You can also clone a Git repo by pasting a URL, "
            "or just create a blank project. "
            "Click Try It to see the creation wizard in action."
        ),
        "action": "demo_new_project",
    },

    # ------------------------------------------------------------------
    # 4. Your Prompt Library
    # ------------------------------------------------------------------
    {
        "title": "Your Prompt Library",
        "body": (
            "The Prompt Manager is where you build and organize your\n"
            "collection of starter prompts.\n\n"

            "It's a full visual editor with:\n"
            "  \u2022  A sidebar showing all your prompts, grouped into a\n"
            "     three-level hierarchy:\n"
            "       Environment  \u2192  Category  \u2192  Prompt\n\n"

            "  \u2022  A text editor where you write and refine the prompt\n\n"

            "  \u2022  A toolbar with everything you need: create, rename,\n"
            "     delete, view history, insert variables, see insights,\n"
            "     and run AI analysis\n\n"

            "ENVIRONMENTS are where the prompt will be used:\n"
            "  Cursor, ChatGPT, Figma, or anything you define.\n\n"

            "CATEGORIES organize prompts within an environment:\n"
            "  Web Development, Data Science, Design Systems, etc.\n\n"

            "Click \"Try It\" to open the Prompt Manager."
        ),
        "narration": (
            "This is the Prompt Manager, and it's really the heart "
            "of the tool. "
            "Think of it as a visual library for all your starter "
            "prompts. On the left you have a sidebar with everything "
            "organized in a clean hierarchy: "
            "Environment, then Category, then Prompt. "
            "Environments are where the prompt will be used, "
            "like Cursor, ChatGPT, or Figma. "
            "Categories are how you group things within that, "
            "like Web Development or Design Systems. "
            "On the right you have a full text editor where you "
            "write and refine each prompt. "
            "And the toolbar at the top gives you everything, "
            "create, rename, delete, history, variables, insights, "
            "and AI analysis. "
            "Click Try It to open it up and look around."
        ),
        "action": "demo_prompt_manager",
    },

    # ------------------------------------------------------------------
    # 5. Template Variables
    # ------------------------------------------------------------------
    {
        "title": "Template Variables",
        "body": (
            "Starter prompts support template variables \u2014 placeholders\n"
            "you fill in each time you use the prompt.\n\n"

            "In the prompt text, they look like this:\n\n"
            "  \"Build a web app called {{app_name}} using\n"
            "   {{framework}} with a {{database}} backend.\"\n\n"

            "When you create a project from this prompt, CursorHub\n"
            "shows you a form to fill in each variable:\n\n"
            "  app_name   \u2192  \"TaskFlow\"\n"
            "  framework  \u2192  \"Next.js\"\n"
            "  database   \u2192  \"PostgreSQL\"\n\n"

            "The prompt becomes fully customized before it's applied.\n\n"

            "To add a variable, select text in the editor and click\n"
            "the \"{} Var\" button \u2014 or pick from existing variables\n"
            "to keep names consistent across prompts.\n\n"

            "The sidebar shows how many variables each prompt has,\n"
            "so you can tell at a glance which ones are customizable."
        ),
        "narration": (
            "Here's something really useful: template variables. "
            "When you write a prompt, you can put placeholders in it "
            "using double curly braces, like app name or framework. "
            "Then when someone creates a project from that prompt, "
            "CursorHub pops up a little form asking them to fill in "
            "each variable. So you write the prompt once, "
            "and it adapts to whatever project you're starting. "
            "You can add variables by selecting text in the editor "
            "and clicking the Var button. "
            "And the sidebar shows a little badge with the variable "
            "count so you can see at a glance which prompts "
            "are customizable."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 6. Version History
    # ------------------------------------------------------------------
    {
        "title": "Version History",
        "body": (
            "Every time you save a prompt, the previous version is\n"
            "automatically archived. Nothing is ever lost.\n\n"

            "Click \"History\" in the toolbar to see all past versions:\n\n"
            "  \u2022  Each version has a timestamp\n"
            "  \u2022  You can preview the full content\n"
            "  \u2022  Click \"Restore This\" to roll back\n\n"

            "When you restore an old version, your current version\n"
            "is saved first \u2014 so you can always undo the undo.\n\n"

            "This means you can experiment freely. Try a new approach,\n"
            "and if it doesn't work, go back with one click."
        ),
        "narration": (
            "Every time you save changes to a prompt, the old version "
            "gets archived automatically. "
            "So you always have a full history you can browse through. "
            "Click the History button and you'll see every past version "
            "with timestamps. You can preview any of them and "
            "restore one with a single click. "
            "And here's the nice part: when you restore an old version, "
            "your current version gets saved first. "
            "So you can never actually lose anything. "
            "It makes it really safe to experiment."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 7. How CursorHub Knows What's Working
    # ------------------------------------------------------------------
    {
        "title": "How CursorHub Knows What's Working",
        "body": (
            "CursorHub quietly tracks how your prompts are used,\n"
            "so you can see what's actually working.\n\n"

            "WHAT IT TRACKS (all local, nothing leaves your machine)\n"
            "  \u2022  Which prompts you use and how often\n"
            "  \u2022  Which projects were created from which prompts\n"
            "  \u2022  How many times each prompt has been edited\n"
            "  \u2022  Your feedback ratings (more on that next)\n\n"

            "FROM THIS, EACH PROMPT GETS A HEALTH SCORE\n\n"
            "  \u2605  Great   \u2014  highly rated, consistently used\n"
            "  \u2713  Good    \u2014  solid usage or decent ratings\n"
            "  \u26a0  Needs attention  \u2014  low ratings or too many edits\n"
            "  \u25cb  Unused  \u2014  exists but nobody has tried it yet\n"
            "  \u25cf  New     \u2014  just created, no data yet\n\n"

            "These scores show up in the sidebar as little badges\n"
            "next to each prompt name, plus detailed stats when\n"
            "you select a prompt."
        ),
        "narration": (
            "Now here's where it gets really interesting. "
            "CursorHub quietly keeps track of how your prompts "
            "are actually being used. "
            "It's all stored locally on your machine, nothing "
            "goes anywhere. "
            "It knows which prompts get used the most, "
            "which projects came from which prompts, "
            "how many times you've edited a prompt, "
            "and what feedback ratings you've given. "
            "From all of that, each prompt gets a health score. "
            "Great means it's highly rated and consistently used. "
            "Good means it's solid. "
            "Needs Attention means it's getting low ratings "
            "or being edited a lot, which usually means "
            "something isn't quite right. "
            "You can see these scores right in the sidebar "
            "as little badges."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 8. The Feedback Loop
    # ------------------------------------------------------------------
    {
        "title": "The Feedback Loop",
        "body": (
            "After you create a project from a starter prompt,\n"
            "CursorHub checks in with you.\n\n"

            "About an hour after creation, a feedback item appears\n"
            "right in your menu bar dropdown:\n\n"
            "  \"How did React SaaS Starter work?\"\n\n"

            "You pick one of four quick ratings:\n\n"
            "  4  \u2014  Great, no changes needed\n"
            "  3  \u2014  Good, but I tweaked it\n"
            "  2  \u2014  It was okay\n"
            "  1  \u2014  Not very useful\n\n"

            "That rating feeds directly into the prompt's health\n"
            "score. Over time, your best prompts rise to the top\n"
            "and the ones that need work get flagged.\n\n"

            "You can also skip \u2014 it won't ask again for that\n"
            "particular project."
        ),
        "narration": (
            "Here's how the feedback actually works. "
            "After you create a project from a prompt, CursorHub "
            "waits about an hour to give you time to actually use it. "
            "Then a little feedback item shows up right in your "
            "menu bar dropdown. It asks: how did this prompt work? "
            "You just pick a quick rating. "
            "Great, no changes needed. Good, but I tweaked it. "
            "It was okay. Or, not very useful. "
            "That rating goes straight into the prompt's health score. "
            "So over time, your best prompts naturally rise to the top "
            "and the ones that need improvement get flagged. "
            "It's a really simple feedback loop, but it adds up fast."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 9. AI-Powered Analysis
    # ------------------------------------------------------------------
    {
        "title": "AI-Powered Analysis",
        "body": (
            "CursorHub connects to Google's Gemini AI to give you\n"
            "expert-level analysis of your prompts.\n\n"

            "ANALYZE A SINGLE PROMPT\n"
            "  Select a prompt and click \"AI Analyze\" in the toolbar.\n"
            "  Gemini reviews the prompt text alongside its usage data\n"
            "  and gives you:\n"
            "    \u2022  A quality score (1\u201310)\n"
            "    \u2022  Strengths and weaknesses\n"
            "    \u2022  Specific improvement suggestions\n"
            "    \u2022  Usage insights from the analytics\n"
            "    \u2022  A suggested rewrite for the weakest section\n\n"

            "ANALYZE YOUR WHOLE LIBRARY\n"
            "  Click \"AI Analyze\" with no prompt selected and Gemini\n"
            "  reviews your entire portfolio:\n"
            "    \u2022  Overall library health\n"
            "    \u2022  Top performers and underperformers\n"
            "    \u2022  Usage patterns and red flags\n"
            "    \u2022  Gaps in your library\n"
            "    \u2022  Top 3 things to do next\n\n"

            "The Insights panel also includes an AI overview when\n"
            "a Gemini key is configured."
        ),
        "narration": (
            "This is probably the coolest part. "
            "CursorHub can connect to Google's Gemini AI "
            "to analyze your prompts for you. "
            "Select any prompt and click AI Analyze. "
            "Gemini looks at both the prompt itself and "
            "all the usage data, and gives you a quality score, "
            "strengths, weaknesses, specific suggestions for "
            "improvement, and even a suggested rewrite for "
            "the weakest section. "
            "You can also run it on your whole library at once "
            "to get a big picture view: which prompts are your "
            "best performers, which need attention, "
            "what's missing from your collection, "
            "and the top three things you should do next. "
            "It's like having a prompt consultant built into the tool."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 10. Protecting Your Work
    # ------------------------------------------------------------------
    {
        "title": "Protecting Your Work",
        "body": (
            "Click \"Backup History Now\" in the menu to create\n"
            "a snapshot of all your Cursor data.\n\n"

            "WHAT GETS BACKED UP\n"
            "  \u2022  Every project's chat history and composer state\n"
            "  \u2022  Global Cursor data shared across projects\n"
            "  \u2022  Workspace metadata\n\n"

            "Backups are stored in timestamped folders:\n"
            "  ~/.cursorhub/backups/20260212_143022/\n\n"

            "Each one includes a manifest showing exactly what\n"
            "was captured and how much space it takes.\n\n"

            "Click \"Show Backups\" to open the folder in Finder."
        ),
        "narration": (
            "Backups. This one is simple but important. "
            "Click Backup History Now and CursorHub takes a "
            "snapshot of all your Cursor data, "
            "your chat history, your composer state, "
            "everything. "
            "It does this in a safe way that works even when "
            "Cursor has its databases locked. "
            "Backups are stored in timestamped folders "
            "so you always know when each one was taken. "
            "It's your safety net."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 11. The Command Line
    # ------------------------------------------------------------------
    {
        "title": "The Command Line",
        "body": (
            "Everything in the menu bar is also available as\n"
            "terminal commands.\n\n"

            "  cursorhub list              See all projects\n"
            "  cursorhub new \"My App\"      Create a new project\n"
            "  cursorhub open \"My App\"     Open in Cursor\n"
            "  cursorhub analyze           AI analysis of your library\n"
            "  cursorhub stats             Analytics dashboard\n"
            "  cursorhub backup            Create a backup\n"
            "  cursorhub config list       View settings\n\n"

            "Useful for automation, scripting, and quick actions\n"
            "without leaving the terminal."
        ),
        "narration": (
            "And for anyone who likes working in the terminal, "
            "everything in the menu bar is also available as "
            "command-line commands. "
            "You can list projects, create new ones, "
            "run AI analysis, check your stats, "
            "make backups, and manage settings. "
            "It's the same tool, just a different way to use it."
        ),
        "action": None,
    },

    # ------------------------------------------------------------------
    # 12. You're Ready
    # ------------------------------------------------------------------
    {
        "title": "You're Ready",
        "body": (
            "That's the full tour! Here's the quick summary:\n\n"

            "YOUR DAILY WORKFLOW\n"
            "  1. Click the CursorHub icon in the menu bar\n"
            "  2. Click a project to open it \u2014 history intact\n"
            "  3. When you're done, just close Cursor. Done.\n\n"

            "STARTING SOMETHING NEW\n"
            "  1. New Project \u2192 pick a starter prompt\n"
            "  2. Fill in any template variables\n"
            "  3. Paste the clipboard into your first chat\n"
            "  4. The AI knows its role and hits the ground running\n\n"

            "IMPROVING OVER TIME\n"
            "  1. Rate prompts when CursorHub asks\n"
            "  2. Check Insights to see what's working\n"
            "  3. Use AI Analyze for expert suggestions\n"
            "  4. Iterate, improve, repeat\n\n"

            f"CursorHub v{__version__}\n"
            "Thanks for taking the tour!"
        ),
        "narration": (
            "And that's it! You've seen everything CursorHub can do. "
            "Your daily workflow is really simple: click the icon, "
            "open a project, and your history is right there. "
            "When you start something new, pick a starter prompt, "
            "fill in the variables, paste, and go. "
            "And over time, the analytics and AI analysis help you "
            "figure out which prompts are working and how to "
            "make them better. "
            "Thanks for taking the tour! "
            "I hope CursorHub makes your workflow a lot smoother."
        ),
        "action": None,
    },
]


# ---------------------------------------------------------------------------
# Tour window constants
# ---------------------------------------------------------------------------

TOUR_WIDTH = 680
TOUR_HEIGHT = 580


# ---------------------------------------------------------------------------
# TourWindowController
# ---------------------------------------------------------------------------

class TourWindowController(NSObject):
    """Controller for the guided tour window with voice narration."""

    def init(self):
        self = objc.super(TourWindowController, self).init()
        if self is None:
            return None

        self._step = 0
        self._demo_controllers = []
        self._speaking = False

        # Set up speech synthesizer
        voice_id = _pick_voice()
        self._synth = AppKit.NSSpeechSynthesizer.alloc().initWithVoice_(voice_id)
        if self._synth:
            self._synth.setRate_(_SPEECH_RATE)
            self._synth.setDelegate_(self)

        self._build_window()
        self._render_step()
        return self

    # ------------------------------------------------------------------
    # Window construction
    # ------------------------------------------------------------------

    def _build_window(self):
        style = (
            AppKit.NSTitledWindowMask
            | AppKit.NSClosableWindowMask
        )
        self._window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(200, 200, TOUR_WIDTH, TOUR_HEIGHT),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_("CursorHub Tour")
        self._window.setDelegate_(self)
        self._window.center()

        content = self._window.contentView()

        # --- Progress bar (thin, at very top) ---
        self._progress = AppKit.NSProgressIndicator.alloc().initWithFrame_(
            NSMakeRect(0, TOUR_HEIGHT - 4, TOUR_WIDTH, 4)
        )
        self._progress.setStyle_(AppKit.NSProgressIndicatorStyleBar)
        self._progress.setIndeterminate_(False)
        self._progress.setMinValue_(0)
        self._progress.setMaxValue_(len(TOUR_STEPS))
        self._progress.setDoubleValue_(1)
        self._progress.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        content.addSubview_(self._progress)

        # --- Step counter at top ---
        step_label = AppKit.NSTextField.labelWithString_("")
        step_label.setFrame_(NSMakeRect(20, TOUR_HEIGHT - 38, TOUR_WIDTH - 40, 18))
        step_label.setFont_(AppKit.NSFont.systemFontOfSize_(11))
        step_label.setTextColor_(AppKit.NSColor.secondaryLabelColor())
        step_label.setAlignment_(AppKit.NSTextAlignmentRight)
        content.addSubview_(step_label)
        self._step_label = step_label

        # --- Title ---
        title_label = AppKit.NSTextField.labelWithString_("")
        title_label.setFrame_(NSMakeRect(24, TOUR_HEIGHT - 68, TOUR_WIDTH - 48, 28))
        title_label.setFont_(AppKit.NSFont.boldSystemFontOfSize_(20))
        content.addSubview_(title_label)
        self._title_label = title_label

        # --- Separator under title ---
        sep = AppKit.NSBox.alloc().initWithFrame_(
            NSMakeRect(20, TOUR_HEIGHT - 76, TOUR_WIDTH - 40, 1)
        )
        sep.setBoxType_(AppKit.NSBoxSeparator)
        content.addSubview_(sep)

        # --- Body text (scrollable) ---
        body_top = TOUR_HEIGHT - 84
        body_bottom = 60
        body_height = body_top - body_bottom

        scroll = AppKit.NSScrollView.alloc().initWithFrame_(
            NSMakeRect(20, body_bottom, TOUR_WIDTH - 40, body_height)
        )
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSNoBorder)
        scroll.setDrawsBackground_(False)

        tv = AppKit.NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, TOUR_WIDTH - 56, body_height)
        )
        tv.setEditable_(False)
        tv.setRichText_(False)
        tv.setFont_(AppKit.NSFont.systemFontOfSize_(13))
        tv.setTextContainerInset_(NSMakeSize(4, 8))
        tv.setDrawsBackground_(False)
        scroll.setDocumentView_(tv)
        content.addSubview_(scroll)
        self._body_text = tv

        # --- Bottom bar ---
        bar_y = 16

        # Back button
        back_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(20, bar_y, 80, 32)
        )
        back_btn.setTitle_("Back")
        back_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        back_btn.setTarget_(self)
        back_btn.setAction_(objc.selector(self.goBack_, signature=b"v@:@"))
        content.addSubview_(back_btn)
        self._back_btn = back_btn

        # Speaker / Narration toggle button
        speak_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(110, bar_y, 100, 32)
        )
        speak_btn.setTitle_("\U0001f50a Narrating...")
        speak_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        speak_btn.setTarget_(self)
        speak_btn.setAction_(objc.selector(self.toggleNarration_, signature=b"v@:@"))
        content.addSubview_(speak_btn)
        self._speak_btn = speak_btn

        # Try It button (shown only on steps with an action)
        try_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(TOUR_WIDTH // 2 - 55, bar_y, 130, 32)
        )
        try_btn.setTitle_("Try It")
        try_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        try_btn.setTarget_(self)
        try_btn.setAction_(objc.selector(self.tryAction_, signature=b"v@:@"))
        content.addSubview_(try_btn)
        self._try_btn = try_btn

        # Next / Done button
        next_btn = AppKit.NSButton.alloc().initWithFrame_(
            NSMakeRect(TOUR_WIDTH - 100, bar_y, 80, 32)
        )
        next_btn.setTitle_("Next")
        next_btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
        next_btn.setKeyEquivalent_("\r")
        next_btn.setTarget_(self)
        next_btn.setAction_(objc.selector(self.goNext_, signature=b"v@:@"))
        content.addSubview_(next_btn)
        self._next_btn = next_btn

    # ------------------------------------------------------------------
    # Step rendering
    # ------------------------------------------------------------------

    def _render_step(self):
        total = len(TOUR_STEPS)
        step = TOUR_STEPS[self._step]

        self._step_label.setStringValue_(f"Step {self._step + 1} of {total}")
        self._title_label.setStringValue_(step["title"])
        self._body_text.setString_(step["body"])
        self._progress.setDoubleValue_(self._step + 1)

        # Scroll to top
        self._body_text.scrollRangeToVisible_(NSMakeRange(0, 0))

        # Button states
        self._back_btn.setEnabled_(self._step > 0)

        is_last = self._step == total - 1
        self._next_btn.setTitle_("Done" if is_last else "Next")

        action = step.get("action")
        has_action = action is not None
        self._try_btn.setHidden_(not has_action)
        if has_action:
            labels = {
                "demo_new_project": "Try It \u2014 New Project",
                "demo_prompt_manager": "Try It \u2014 Prompt Manager",
            }
            self._try_btn.setTitle_(labels.get(action, "Try It"))

        # Start narration
        self._start_narration()

    # ------------------------------------------------------------------
    # Speech / narration
    # ------------------------------------------------------------------

    def _start_narration(self):
        """Begin speaking the current step's narration text."""
        if self._synth:
            self._synth.stopSpeaking()
        narration = TOUR_STEPS[self._step].get("narration", "")
        if narration and self._synth:
            self._synth.startSpeakingString_(narration)
            self._speaking = True
            self._speak_btn.setTitle_("\U0001f50a Narrating...")
        else:
            self._speaking = False
            self._speak_btn.setTitle_("\U0001f508 Replay")

    def _stop_narration(self):
        """Stop any current speech."""
        if self._synth:
            self._synth.stopSpeaking()
        self._speaking = False
        self._speak_btn.setTitle_("\U0001f508 Replay")

    # NSSpeechSynthesizerDelegate method
    @objc.typedSelector(b"v@:@B")
    def speechSynthesizer_didFinishSpeaking_(self, sender, finished_ok):
        """Called when speech finishes."""
        self._speaking = False
        self._speak_btn.setTitle_("\U0001f508 Replay")

    @objc.typedSelector(b"v@:@")
    def toggleNarration_(self, sender):
        """Toggle between pause/resume/replay narration."""
        if self._speaking:
            self._stop_narration()
        else:
            self._start_narration()

    # ------------------------------------------------------------------
    # Navigation actions
    # ------------------------------------------------------------------

    @objc.typedSelector(b"v@:@")
    def goBack_(self, sender):
        if self._step > 0:
            self._stop_narration()
            self._step -= 1
            self._render_step()

    @objc.typedSelector(b"v@:@")
    def goNext_(self, sender):
        if self._step < len(TOUR_STEPS) - 1:
            self._stop_narration()
            self._step += 1
            self._render_step()
        else:
            self._stop_narration()
            self._window.close()

    @objc.typedSelector(b"v@:@")
    def tryAction_(self, sender):
        try:
            step = TOUR_STEPS[self._step]
            action = step.get("action")
            if action == "demo_new_project":
                self._open_demo_picker()
            elif action == "demo_prompt_manager":
                self._open_prompt_manager()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error(f"Unexpected error: {e}")

    # ------------------------------------------------------------------
    # Demo launchers
    # ------------------------------------------------------------------

    def _open_demo_picker(self):
        """Open the New Project window in demo mode."""
        try:
            from cursorhub.ui import NewProjectWindowController

            # Reuse an existing window that's still open
            for ctrl in self._demo_controllers:
                if (isinstance(ctrl, NewProjectWindowController)
                        and ctrl._window and ctrl._window.isVisible()):
                    ctrl._window.makeKeyAndOrderFront_(None)
                    return

            NewProjectWindowController._init_demo = True
            ctrl = NewProjectWindowController.alloc().init()
            if ctrl is None:
                self._show_error("Failed to create New Project window.")
                return
            ctrl.showWindow()
            self._demo_controllers.append(ctrl)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error(f"Could not open demo: {e}")

    def _open_prompt_manager(self):
        """Open the Prompt Manager window."""
        try:
            from cursorhub.ui import PromptManagerController

            # Reuse an existing window that's still open
            for ctrl in self._demo_controllers:
                if (isinstance(ctrl, PromptManagerController)
                        and ctrl._window and ctrl._window.isVisible()):
                    ctrl._window.makeKeyAndOrderFront_(None)
                    return

            ctrl = PromptManagerController.alloc().init()
            if ctrl is None:
                self._show_error("Failed to create Prompt Manager window.")
                return
            ctrl.showWindow()
            self._demo_controllers.append(ctrl)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._show_error(f"Could not open Prompt Manager: {e}")

    def _show_error(self, message):
        alert = AppKit.NSAlert.alloc().init()
        alert.setMessageText_("CursorHub")
        alert.setInformativeText_(message)
        alert.runModal()

    # ------------------------------------------------------------------
    # Window delegate
    # ------------------------------------------------------------------

    def windowWillClose_(self, notification):
        """Stop narration when the window closes."""
        self._stop_narration()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def showWindow(self):
        """Display the tour window."""
        self._step = 0
        self._render_step()
        self._window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)
