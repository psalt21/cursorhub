#!/usr/bin/env python3
"""Seed CursorHub with realistic mock data for visual/functional testing.

Clears all existing analytics data and populates with several months of
simulated usage across multiple projects, prompts, and feedback ratings.

Run: ./venv/bin/python scripts/seed_mock_data.py
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

CONFIG_DIR = Path.home() / ".cursorhub"
CONFIG_FILE = CONFIG_DIR / "config.json"
DB_PATH = CONFIG_DIR / "analytics.db"
PROMPTS_DIR = CONFIG_DIR / "prompts"
TAXONOMY_FILE = CONFIG_DIR / "taxonomy.json"

random.seed(42)  # reproducible

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

NOW = datetime.now()

def rand_ts(days_ago_min, days_ago_max):
    """Random timestamp between days_ago_max and days_ago_min days ago."""
    delta = timedelta(
        days=random.uniform(days_ago_min, days_ago_max),
        hours=random.randint(8, 22),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return (NOW - delta).isoformat()

def sequential_ts(base_iso, hours_after_min=1, hours_after_max=72):
    """Return a timestamp some hours after the base."""
    base = datetime.fromisoformat(base_iso)
    delta = timedelta(hours=random.uniform(hours_after_min, hours_after_max))
    return (base + delta).isoformat()


# ---------------------------------------------------------------------------
# 1. Create a rich set of starter prompts
# ---------------------------------------------------------------------------

PROMPTS = [
    # (filename, frontmatter, body)
    ("react-saas-starter.md", {"category": "Web Apps", "environment": "Cursor"},
     "# React SaaS Starter\n\nYou are a senior full-stack engineer building a modern SaaS application.\n\n"
     "## Tech Stack\n- React 18 with TypeScript\n- Tailwind CSS\n- Supabase (auth + database)\n- Stripe for billing\n\n"
     "## Your Role\nBuild a production-ready SaaS with {{app_name}} as the product name.\n"
     "The target audience is {{target_audience}}.\n\n"
     "## Instructions\n1. Set up the project with Vite + React + TypeScript\n"
     "2. Implement auth flows (sign up, login, forgot password)\n"
     "3. Create a dashboard layout with sidebar navigation\n"
     "4. Set up Stripe integration for {{pricing_model}} billing\n"
     "5. Add a landing page with hero, features, and pricing sections\n"),

    ("python-cli-tool.md", {"category": "CLI Tools", "environment": "Cursor"},
     "# Python CLI Tool\n\nYou are an expert Python developer specializing in CLI applications.\n\n"
     "## Tech Stack\n- Python 3.11+\n- Click or argparse\n- Rich for terminal UI\n\n"
     "## Your Role\nBuild a CLI tool called {{tool_name}} that {{tool_purpose}}.\n\n"
     "## Instructions\n1. Use pyproject.toml for packaging\n"
     "2. Implement subcommands with clear --help text\n"
     "3. Add color output using Rich\n"
     "4. Write comprehensive tests with pytest\n"
     "5. Include a README with installation and usage instructions\n"),

    ("swift-ios-app.md", {"category": "Mobile", "environment": "Cursor"},
     "# Swift iOS App\n\nYou are a senior iOS developer building a native Swift application.\n\n"
     "## Tech Stack\n- Swift 5.9 / SwiftUI\n- Core Data or SwiftData\n- Combine\n\n"
     "## Your Role\nBuild an iOS app called {{app_name}} for {{app_purpose}}.\n\n"
     "## Instructions\n1. Use SwiftUI with MVVM architecture\n"
     "2. Implement navigation with NavigationStack\n"
     "3. Add persistence with SwiftData\n"
     "4. Include onboarding flow for first-time users\n"
     "5. Support dark mode and Dynamic Type\n"),

    ("figma-design-system.md", {"category": "Design Systems", "environment": "Figma"},
     "# Design System Builder\n\nCreate a comprehensive design system for {{brand_name}}.\n\n"
     "## Components\n- Typography scale (headings, body, captions)\n- Color palette (primary, secondary, neutral, semantic)\n"
     "- Spacing system (4px grid)\n- Button variants (primary, secondary, ghost, destructive)\n"
     "- Form inputs (text, select, checkbox, radio, toggle)\n- Card components\n- Navigation patterns\n\n"
     "## Guidelines\n- Mobile-first responsive breakpoints\n- WCAG 2.1 AA accessibility\n- Consistent border radius: {{border_radius}}\n"),

    ("chatgpt-research-assistant.md", {"category": "Research", "environment": "ChatGPT"},
     "# Research Assistant\n\nYou are a thorough research assistant helping analyze {{research_topic}}.\n\n"
     "## Approach\n1. Start with a broad literature review\n"
     "2. Identify key themes and contradictions\n"
     "3. Synthesize findings into actionable insights\n"
     "4. Cite sources with links when available\n\n"
     "## Output Format\n- Executive summary (3-5 sentences)\n"
     "- Key findings (bullet points)\n- Detailed analysis (organized by theme)\n"
     "- Recommendations\n- Sources and further reading\n"),

    ("chatgpt-writing-coach.md", {"category": "Writing", "environment": "ChatGPT"},
     "# Writing Coach\n\nYou are a professional writing coach helping improve {{content_type}} for {{audience}}.\n\n"
     "## Guidelines\n- Maintain the author's voice\n- Focus on clarity and conciseness\n"
     "- Suggest structural improvements\n- Flag jargon that might confuse readers\n"
     "- Provide specific examples for abstract feedback\n\n"
     "## Process\n1. Read the full draft first\n2. Provide high-level structural feedback\n"
     "3. Then do line-level edits\n4. Summarize top 3 improvements made\n"),

    ("nextjs-landing-page.md", {"category": "Web Apps", "environment": "Cursor"},
     "# Next.js Landing Page\n\nBuild a high-converting landing page for {{product_name}}.\n\n"
     "## Tech Stack\n- Next.js 14 (App Router)\n- Tailwind CSS + Framer Motion\n- Vercel deployment\n\n"
     "## Sections\n1. Hero with animated headline and CTA\n"
     "2. Social proof / logos bar\n3. Feature grid (3-4 features with icons)\n"
     "4. Testimonials carousel\n5. Pricing table\n6. FAQ accordion\n7. Footer with newsletter signup\n\n"
     "## Requirements\n- Mobile-first responsive\n- < 3s load time\n- SEO optimized with meta tags\n"),

    ("api-backend-starter.md", {"category": "Backend", "environment": "Cursor"},
     "# API Backend Starter\n\nYou are a backend engineer building a REST API for {{service_name}}.\n\n"
     "## Tech Stack\n- Node.js / Express or Fastify\n- PostgreSQL with Prisma ORM\n- JWT auth\n- Docker + docker-compose\n\n"
     "## Instructions\n1. Set up project with TypeScript\n"
     "2. Implement auth (register, login, refresh tokens)\n"
     "3. Create CRUD endpoints for core resources\n"
     "4. Add input validation with Zod\n"
     "5. Write integration tests\n6. Include Dockerfile and docker-compose.yml\n"),

    ("figma-app-redesign.md", {"category": "UI/UX", "environment": "Figma"},
     "# App Redesign\n\nRedesign the {{app_name}} app with a focus on {{design_goal}}.\n\n"
     "## Deliverables\n- User flow diagrams\n- Wireframes (low-fidelity)\n- High-fidelity mockups\n"
     "- Interactive prototype\n- Design specifications document\n\n"
     "## Principles\n- Reduce cognitive load\n- Consistent visual hierarchy\n"
     "- Accessible color contrast\n- Thumb-friendly touch targets (44px min)\n"),

    ("data-pipeline.md", {"category": "Data Engineering", "environment": "Cursor"},
     "# Data Pipeline\n\nBuild an ETL pipeline for {{data_source}} data.\n\n"
     "## Tech Stack\n- Python 3.11+\n- Apache Airflow or Prefect\n- PostgreSQL / BigQuery\n- dbt for transformations\n\n"
     "## Instructions\n1. Set up ingestion from {{data_source}} API\n"
     "2. Implement incremental loading with change detection\n"
     "3. Create dbt models for staging, intermediate, and mart layers\n"
     "4. Add data quality checks\n5. Set up monitoring and alerting\n"),
]

print("Creating starter prompts...")
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
for filename, meta, body in PROMPTS:
    path = PROMPTS_DIR / filename
    fm_lines = []
    for k, v in meta.items():
        if v:
            fm_lines.append(f"{k}: {v}")
    fm = "---\n" + "\n".join(fm_lines) + "\n---\n" if fm_lines else ""
    path.write_text(fm + body)
    print(f"  + {filename}")


# ---------------------------------------------------------------------------
# 2. Update taxonomy
# ---------------------------------------------------------------------------

print("\nUpdating taxonomy...")
taxonomy = {
    "environments": ["Cursor", "Figma", "ChatGPT"],
    "categories": [
        "Web Apps", "CLI Tools", "Mobile", "Backend",
        "Design Systems", "UI/UX", "Research", "Writing",
        "Data Engineering", "Base Starters",
    ],
}
TAXONOMY_FILE.write_text(json.dumps(taxonomy, indent=2))
print(f"  Environments: {taxonomy['environments']}")
print(f"  Categories: {taxonomy['categories']}")


# ---------------------------------------------------------------------------
# 3. Update config.json with enriched project metadata
# ---------------------------------------------------------------------------

print("\nUpdating project config...")
config = json.loads(CONFIG_FILE.read_text())

# Enrich existing projects with creation metadata
enrichments = {
    "/Users/philpersonal/Projects/personal-tool-tray": {
        "created_at": rand_ts(150, 160),
        "created_via": "prompt",
        "prompt_filename": "python-cli-tool.md",
    },
    "/Users/philpersonal/Projects/cursor-hub": {
        "created_at": rand_ts(90, 100),
        "created_via": "prompt",
        "prompt_filename": "mac-menu-bar-app.md",
    },
    "/Users/philpersonal/Projects/Signal Scout/signal-scout": {
        "created_at": rand_ts(60, 70),
        "created_via": "prompt",
        "prompt_filename": "react-saas-starter.md",
        "prompt_variables": {"app_name": "Signal Scout", "target_audience": "traders", "pricing_model": "subscription"},
    },
    "/Users/philpersonal/Projects/visassist": {
        "created_at": rand_ts(120, 130),
        "created_via": "prompt",
        "prompt_filename": "swift-ios-app.md",
        "prompt_variables": {"app_name": "VisAssist", "app_purpose": "visual accessibility tools"},
    },
    "/Users/philpersonal/Projects/dj-player": {
        "created_at": rand_ts(30, 40),
        "created_via": "prompt",
        "prompt_filename": "react-saas-starter.md",
        "prompt_variables": {"app_name": "DJ Player", "target_audience": "DJs and music producers", "pricing_model": "freemium"},
    },
    "/Users/philpersonal/Projects/team-rad-tool-tray": {
        "created_at": rand_ts(100, 110),
        "created_via": "clone",
    },
    "/Users/philpersonal/Projects/Rads Tray/rads-tray": {
        "created_at": rand_ts(80, 90),
        "created_via": "blank",
    },
    "/Users/philpersonal/Projects/test-project-1a": {
        "created_at": rand_ts(5, 10),
        "created_via": "prompt",
        "prompt_filename": "nextjs-landing-page.md",
        "prompt_variables": {"product_name": "Test Product 1A"},
    },
}

for p in config["projects"]:
    enrich = enrichments.get(p["path"], {})
    for k, v in enrich.items():
        p[k] = v

# Add a couple of archived projects for testing
config["archived_projects"] = [
    {
        "name": "Old Prototype",
        "path": "/Users/philpersonal/Projects/old-prototype",
        "created_at": rand_ts(200, 210),
        "created_via": "blank",
    },
    {
        "name": "Recipe App V1",
        "path": "/Users/philpersonal/Projects/recipe-app-v1",
        "created_at": rand_ts(180, 190),
        "created_via": "prompt",
        "prompt_filename": "swift-ios-app.md",
        "prompt_variables": {"app_name": "RecipeBox", "app_purpose": "recipe management"},
    },
]

CONFIG_FILE.write_text(json.dumps(config, indent=2))
print(f"  Enriched {len(enrichments)} projects with creation metadata")
print(f"  Added {len(config['archived_projects'])} archived projects")


# ---------------------------------------------------------------------------
# 4. Populate analytics database
# ---------------------------------------------------------------------------

print("\nPopulating analytics database...")

conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event TEXT NOT NULL,
        prompt_filename TEXT,
        project_path TEXT,
        meta TEXT
    )
""")
# Clear existing data
conn.execute("DELETE FROM events")
conn.commit()

events = []

def add_event(ts, event, prompt_fn=None, project_path=None, **meta):
    events.append((ts, event, prompt_fn, project_path,
                    json.dumps(meta) if meta else None))

# -- All prompt filenames (existing + new)
ALL_PROMPTS = [
    "generic-starter-prompt-1.md", "mac-menu-bar-app.md", "test-prompt.md",
    "react-saas-starter.md", "python-cli-tool.md", "swift-ios-app.md",
    "figma-design-system.md", "chatgpt-research-assistant.md",
    "chatgpt-writing-coach.md", "nextjs-landing-page.md",
    "api-backend-starter.md", "figma-app-redesign.md", "data-pipeline.md",
]

PROJECTS = [p["path"] for p in config["projects"]]

# --- Prompt creation events (staggered over months) ---
prompt_creation_dates = {}
for i, fn in enumerate(ALL_PROMPTS):
    days_ago = 180 - i * 12 + random.randint(-3, 3)
    ts = rand_ts(max(days_ago - 2, 1), max(days_ago + 2, 3))
    prompt_creation_dates[fn] = ts
    add_event(ts, "prompt_created", prompt_fn=fn)

# --- Prompt edits (each prompt edited 2-8 times over its lifetime) ---
for fn in ALL_PROMPTS:
    creation = prompt_creation_dates[fn]
    num_edits = random.randint(2, 8)
    last_ts = creation
    for j in range(num_edits):
        edit_ts = sequential_ts(last_ts, hours_after_min=12, hours_after_max=336)
        # Don't go into the future
        if datetime.fromisoformat(edit_ts) > NOW:
            break
        diff_chars = random.randint(15, 800)
        add_event(edit_ts, "prompt_edited", prompt_fn=fn, diff_chars=diff_chars)
        last_ts = edit_ts

# --- Prompt applications (the core usage data) ---
# Map projects to prompts they were created from
project_prompt_map = {}
for p in config["projects"]:
    if p.get("prompt_filename"):
        project_prompt_map[p["path"]] = p["prompt_filename"]

# Log prompt_applied for each real project that used a prompt
for path, fn in project_prompt_map.items():
    proj = next((p for p in config["projects"] if p["path"] == path), None)
    if proj and proj.get("created_at"):
        ts = proj["created_at"]
    else:
        ts = rand_ts(30, 150)
    var_names = []
    if proj and proj.get("prompt_variables"):
        var_names = list(proj["prompt_variables"].keys())
    add_event(ts, "prompt_applied", prompt_fn=fn, project_path=path,
              variable_names=var_names, project_name=proj["name"] if proj else "")

# Also simulate some additional uses of popular prompts (reuse by creating other projects)
extra_uses = [
    ("react-saas-starter.md", "/Users/philpersonal/Projects/saas-dashboard", "SaaS Dashboard", 45),
    ("react-saas-starter.md", "/Users/philpersonal/Projects/client-portal", "Client Portal", 25),
    ("python-cli-tool.md", "/Users/philpersonal/Projects/deploy-tool", "Deploy Tool", 95),
    ("python-cli-tool.md", "/Users/philpersonal/Projects/log-analyzer", "Log Analyzer", 55),
    ("nextjs-landing-page.md", "/Users/philpersonal/Projects/product-site", "Product Site", 20),
    ("nextjs-landing-page.md", "/Users/philpersonal/Projects/event-page", "Event Page", 12),
    ("api-backend-starter.md", "/Users/philpersonal/Projects/payment-api", "Payment API", 70),
    ("api-backend-starter.md", "/Users/philpersonal/Projects/notification-svc", "Notification Svc", 35),
    ("swift-ios-app.md", "/Users/philpersonal/Projects/fitness-tracker", "Fitness Tracker", 50),
    ("chatgpt-research-assistant.md", None, "Ad-hoc Research", 80),
    ("chatgpt-research-assistant.md", None, "Market Analysis", 40),
    ("chatgpt-writing-coach.md", None, "Blog Post Review", 65),
    ("chatgpt-writing-coach.md", None, "Proposal Edit", 30),
    ("figma-design-system.md", None, "Brand Refresh", 100),
    ("figma-app-redesign.md", None, "Mobile Redesign", 75),
    ("data-pipeline.md", "/Users/philpersonal/Projects/analytics-pipe", "Analytics Pipeline", 42),
]

for fn, path, name, days_ago in extra_uses:
    ts = rand_ts(max(days_ago - 3, 1), days_ago + 3)
    add_event(ts, "prompt_applied", prompt_fn=fn, project_path=path,
              variable_names=[], project_name=name)

# --- Project created events ---
for p in config["projects"]:
    ts = p.get("created_at", rand_ts(30, 150))
    method = p.get("created_via", "blank")
    fn = p.get("prompt_filename")
    add_event(ts, "project_created", prompt_fn=fn, project_path=p["path"],
              method=method, project_name=p["name"])

# Extra project_created for the simulated uses
for fn, path, name, days_ago in extra_uses:
    if path:
        ts = rand_ts(max(days_ago - 3, 1), days_ago + 3)
        add_event(ts, "project_created", prompt_fn=fn, project_path=path,
                  method="prompt", project_name=name)

# --- Project opened events (simulate regular usage) ---
for p in config["projects"]:
    # Each real project opened 5-30 times
    num_opens = random.randint(5, 30)
    for _ in range(num_opens):
        ts = rand_ts(0, 120)
        add_event(ts, "project_opened", project_path=p["path"])

# --- Prompt viewed events (browsing in the manager) ---
for fn in ALL_PROMPTS:
    num_views = random.randint(3, 20)
    for _ in range(num_views):
        ts = rand_ts(0, 150)
        add_event(ts, "prompt_viewed", prompt_fn=fn)

# --- Variable inserted events ---
prompts_with_vars = [
    "react-saas-starter.md", "python-cli-tool.md", "swift-ios-app.md",
    "figma-design-system.md", "chatgpt-research-assistant.md",
    "chatgpt-writing-coach.md", "nextjs-landing-page.md",
    "api-backend-starter.md", "figma-app-redesign.md", "data-pipeline.md",
    "mac-menu-bar-app.md",
]
var_examples = ["app_name", "target_audience", "tool_name", "tool_purpose",
                "brand_name", "research_topic", "product_name", "service_name",
                "content_type", "audience", "pricing_model", "data_source",
                "role_name", "design_goal", "border_radius", "app_purpose"]

for fn in prompts_with_vars:
    num_inserts = random.randint(1, 5)
    for _ in range(num_inserts):
        ts = rand_ts(1, 120)
        var = random.choice(var_examples)
        add_event(ts, "variable_inserted", prompt_fn=fn, variable_name=var)

# --- History restored events (occasional version rollbacks) ---
for fn in random.sample(ALL_PROMPTS, 5):
    ts = rand_ts(5, 100)
    add_event(ts, "history_restored", prompt_fn=fn,
              history_version=f"{fn.replace('.md', '')}_{random.randint(20250901, 20260210)}_{random.randint(100000, 235959)}.md")

# --- Feedback events (ratings for prompt-based projects) ---
# Give most prompt-based projects a rating
feedback_targets = []
for p in config["projects"]:
    if p.get("prompt_filename") and p.get("created_at"):
        feedback_targets.append((p["prompt_filename"], p["path"], p["name"], p["created_at"]))

for fn, path, name, days_ago in extra_uses:
    if path:
        ts = rand_ts(max(days_ago - 3, 1), days_ago + 3)
        feedback_targets.append((fn, path, name, ts))

# Rate ~75% of them
for fn, path, name, created_ts in feedback_targets:
    if random.random() < 0.75:
        # Rating distribution: skewed positive
        rating = random.choices([4, 3, 2, 1], weights=[40, 35, 15, 10])[0]
        fb_ts = sequential_ts(created_ts, hours_after_min=24, hours_after_max=168)
        if datetime.fromisoformat(fb_ts) < NOW:
            add_event(fb_ts, "feedback_given", prompt_fn=fn,
                      project_path=path, rating=rating, project_name=name)

# A few skipped feedback
for _ in range(4):
    fn = random.choice(ALL_PROMPTS)
    path = random.choice(PROJECTS)
    ts = rand_ts(5, 60)
    add_event(ts, "feedback_skipped", prompt_fn=fn, project_path=path)

# --- Project archived/deleted events (for the archived projects) ---
for p in config.get("archived_projects", []):
    created = p.get("created_at", rand_ts(180, 200))
    archive_ts = sequential_ts(created, hours_after_min=720, hours_after_max=2160)
    if datetime.fromisoformat(archive_ts) < NOW:
        add_event(archive_ts, "project_archived", project_path=p["path"],
                  project_name=p["name"])

# --- Make one prompt look "needs attention" (low ratings, many edits) ---
# generic-starter-prompt-1.md: give it low ratings and lots of edits
for _ in range(6):
    ts = rand_ts(5, 90)
    add_event(ts, "prompt_edited", prompt_fn="generic-starter-prompt-1.md",
              diff_chars=random.randint(50, 300))
for _ in range(3):
    ts = rand_ts(5, 60)
    add_event(ts, "prompt_applied", prompt_fn="generic-starter-prompt-1.md",
              project_path="/Users/philpersonal/Projects/test-" + str(random.randint(1, 99)),
              variable_names=[], project_name="Test Project")
    fb_ts = sequential_ts(ts, 24, 120)
    if datetime.fromisoformat(fb_ts) < NOW:
        add_event(fb_ts, "feedback_given", prompt_fn="generic-starter-prompt-1.md",
                  rating=random.choice([1, 1, 2]),
                  project_name="Test Project")

# --- Sort all events by timestamp and insert ---
events.sort(key=lambda e: e[0])

conn.executemany(
    "INSERT INTO events (timestamp, event, prompt_filename, project_path, meta) "
    "VALUES (?, ?, ?, ?, ?)",
    events,
)
conn.commit()

# Print summary
total = conn.execute("SELECT COUNT(*) as cnt FROM events").fetchone()[0]
by_type = conn.execute(
    "SELECT event, COUNT(*) as cnt FROM events GROUP BY event ORDER BY cnt DESC"
).fetchall()
conn.close()

print(f"\n  Inserted {total} events:")
for row in by_type:
    print(f"    {row[0]:30s} {row[1]:>5d}")

print(f"\n  Date range: {events[0][0][:10]} to {events[-1][0][:10]}")
print("\nDone! Restart CursorHub to see the data.")
