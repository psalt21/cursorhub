"""AI-powered analysis of prompts and usage patterns using Gemini.

Sends local analytics data and prompt content to the Gemini API
for intelligent analysis and recommendations.  The user must
explicitly configure a Gemini API key for this module to work.

The ``google-genai`` package is an **optional** dependency.
All public functions in this module return a user-friendly error
string when the package is missing, so the rest of the app
continues to work without it.
"""

import json
import traceback
from typing import Any, Optional

from cursorhub.analytics import (
    compute_prompt_health,
    get_all_prompt_stats,
    get_overall_stats,
    get_prompt_stats,
    get_recent_activity,
)
from cursorhub.prompts import get_prompt_body, get_prompt_metadata, list_prompts

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    _HAS_GENAI = False


_GENAI_MISSING_MSG = (
    "The google-genai package is not installed.\n"
    "Install it with:  pip install 'cursorhub[ai]'"
)


# ---------------------------------------------------------------------------
# Gemini client helper
# ---------------------------------------------------------------------------

def _get_client(api_key: str):
    """Create and return a Gemini client."""
    if not _HAS_GENAI:
        raise ImportError(_GENAI_MISSING_MSG)
    return genai.Client(api_key=api_key)


_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash"]


def _generate_with_fallback(
    client,
    user_message: str,
    system_instruction: str,
    max_tokens: int = 2048,
) -> str:
    """Try each model in _MODELS until one succeeds.

    Falls back to the next model on rate-limit (429) errors.
    """
    import time

    last_error = None
    for model in _MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_message,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text or "(No response from Gemini)"
        except Exception as exc:
            last_error = exc
            exc_str = str(exc)
            # Only fall back on rate-limit; re-raise other errors
            if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                time.sleep(2)  # brief pause before trying next model
                continue
            raise

    # All models exhausted
    return (
        f"Gemini API rate limit reached. Please try again in a minute.\n"
        f"(Last error: {last_error})"
    )


# ---------------------------------------------------------------------------
# Single-prompt analysis
# ---------------------------------------------------------------------------

def analyze_prompt(filename: str, api_key: str) -> str:
    """Analyse a single starter prompt with Gemini.

    Returns a formatted markdown string with the analysis, or an error
    message if something goes wrong.
    """
    if not _HAS_GENAI:
        return _GENAI_MISSING_MSG
    try:
        # Gather all the data Gemini needs
        body = get_prompt_body(filename)
        if body is None:
            return f"Error: prompt '{filename}' not found."

        meta = get_prompt_metadata(filename)
        stats = get_prompt_stats(filename)
        health = compute_prompt_health(stats)

        prompt_data = {
            "filename": filename,
            "environment": meta.get("environment", "Unknown"),
            "category": meta.get("category", "Unknown"),
            "health_score": health,
            "times_used": stats["times_used"],
            "avg_rating": stats["avg_rating"],
            "rating_count": stats["rating_count"],
            "edit_count": stats["edit_count"],
            "projects_count": len(stats["projects"]),
            "last_used": stats["last_used"],
        }

        system_instruction = (
            "You are CursorHub Analyst, an expert at evaluating AI coding prompts "
            "and their real-world effectiveness.  The user manages a library of "
            "'starter prompts' that are used to kick off new coding projects in "
            "the Cursor IDE.  You will be given a prompt's full text, its metadata, "
            "and usage analytics.  Provide a concise, actionable analysis."
        )

        user_message = (
            f"Analyze the following starter prompt.\n\n"
            f"## Metadata & Analytics\n```json\n{json.dumps(prompt_data, indent=2)}\n```\n\n"
            f"## Prompt Content\n```\n{body}\n```\n\n"
            f"Provide your analysis in the following sections:\n"
            f"1. **Quality Score** (1-10) — How well-written is this prompt?\n"
            f"2. **Strengths** — 2-3 bullet points\n"
            f"3. **Weaknesses / Risks** — 2-3 bullet points\n"
            f"4. **Improvement Suggestions** — Specific, actionable recommendations\n"
            f"5. **Usage Insights** — What the analytics data tells us about "
            f"   how effective this prompt is in practice\n"
            f"6. **Rewrite Suggestion** — If you'd rewrite one section, which "
            f"   and how?  (Keep it brief.)\n"
        )

        client = _get_client(api_key)
        response = _generate_with_fallback(
            client, user_message, system_instruction, max_tokens=2048,
        )
        return response

    except Exception as exc:
        traceback.print_exc()
        return f"Error during analysis: {exc}"


# ---------------------------------------------------------------------------
# Portfolio / overview analysis
# ---------------------------------------------------------------------------

def analyze_overview(api_key: str) -> str:
    """Analyse the full prompt portfolio and usage patterns with Gemini.

    Returns a formatted markdown string with the analysis.
    """
    if not _HAS_GENAI:
        return _GENAI_MISSING_MSG
    try:
        # Gather overall stats
        overall = get_overall_stats()
        all_stats = get_all_prompt_stats()
        prompts = list_prompts()
        recent = get_recent_activity(limit=30)

        # Build a summary of each prompt
        prompt_summaries = []
        for p in prompts:
            fn = p["filename"]
            s = all_stats.get(fn, {})
            health = compute_prompt_health(s) if s else "new"
            prompt_summaries.append({
                "filename": fn,
                "name": p["name"],
                "environment": p["environment"] or "Uncategorized",
                "category": p["category"] or "Uncategorized",
                "health": health,
                "times_used": s.get("times_used", 0),
                "avg_rating": s.get("avg_rating"),
                "edit_count": s.get("edit_count", 0),
            })

        # Summarise recent activity for context
        activity_summary = []
        for evt in recent[:20]:
            activity_summary.append({
                "event": evt["event"],
                "prompt": evt.get("prompt_filename"),
                "timestamp": evt["timestamp"][:16],  # trim
            })

        system_instruction = (
            "You are CursorHub Analyst, an expert at evaluating AI prompt "
            "libraries and usage patterns.  The user manages a library of "
            "'starter prompts' used to kick off coding projects.  You have "
            "access to portfolio-level analytics.  Provide a concise executive "
            "summary with actionable recommendations."
        )

        user_message = (
            "Analyse my full prompt portfolio and usage.\n\n"
            f"## Overall Stats\n```json\n{json.dumps(overall, indent=2)}\n```\n\n"
            f"## Prompts ({len(prompt_summaries)} total)\n"
            f"```json\n{json.dumps(prompt_summaries, indent=2)}\n```\n\n"
            f"## Recent Activity (last {len(activity_summary)} events)\n"
            f"```json\n{json.dumps(activity_summary, indent=2)}\n```\n\n"
            "Provide your analysis in these sections:\n"
            "1. **Portfolio Health** — Overall assessment of the prompt library\n"
            "2. **Top Performers** — Which prompts are working best and why\n"
            "3. **Needs Attention** — Prompts that should be improved or retired\n"
            "4. **Usage Patterns** — Trends, frequency, any red flags\n"
            "5. **Gaps & Opportunities** — What's missing from the library?\n"
            "6. **Top 3 Recommendations** — Most impactful things to do next\n"
        )

        client = _get_client(api_key)
        response = _generate_with_fallback(
            client, user_message, system_instruction, max_tokens=3000,
        )
        return response

    except Exception as exc:
        traceback.print_exc()
        return f"Error during analysis: {exc}"
