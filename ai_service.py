"""
EventGenie AI - Gemini AI Service
All AI requests are handled server-side here. The API key is never exposed to the frontend.
"""
import re
import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are EventGenie AI, a specialized event planning assistant.
Your sole purpose is to help users plan weddings, birthdays, college events, community celebrations, and custom events.

IMPORTANT RULES:
1. Only discuss topics related to event planning. Politely decline unrelated requests.
2. Never invent vendor contact details, confirmed bookings, or verified availability.
3. Clearly distinguish between ESTIMATED costs and confirmed quotations.
4. All cost estimates are approximate and in Indian Rupees (INR).
5. Adapt recommendations to the specific event type, guest count, budget, and preferences.
6. Be practical, friendly, and encouraging.
7. When generating structured data, always return valid JSON.

You can help with:
- Generating comprehensive event plans
- Budget breakdowns and cost-saving tips
- Preparation timelines and checklists
- Event-day schedules
- Vendor checklists
- Creative theme and decoration ideas
- Answering follow-up questions about any aspect of event planning
"""

EVENT_PLAN_PROMPT = """Generate a comprehensive event plan for the following event. 
Return ONLY a valid JSON object (no markdown, no extra text) with this exact structure:

{{
  "overview": {{
    "summary": "2-3 sentence overview of the event plan",
    "key_highlights": ["highlight1", "highlight2", "highlight3"],
    "estimated_duration": "e.g. 6 hours",
    "recommended_venue_type": "description of ideal venue"
  }},
  "preparation_timeline": [
    {{
      "phase": "Phase name (e.g. 3 Months Before)",
      "weeks_before": 12,
      "tasks": [
        {{
          "title": "Task title",
          "description": "Task description",
          "priority": "high|medium|low",
          "category": "venue|catering|decoration|vendor|logistics|invitations|clothing|entertainment"
        }}
      ]
    }}
  ],
  "event_day_schedule": [
    {{
      "time": "HH:MM AM/PM",
      "activity": "Activity name",
      "duration_minutes": 30,
      "notes": "Preparation notes",
      "responsible": "Who handles this"
    }}
  ],
  "vendor_checklist": [
    {{
      "category": "Vendor category",
      "tasks": [
        {{
          "title": "Task title",
          "description": "What to check/arrange",
          "priority": "high|medium|low"
        }}
      ]
    }}
  ],
  "ideas": {{
    "themes": ["theme1", "theme2", "theme3"],
    "color_combinations": [
      {{"name": "Palette name", "colors": ["color1", "color2", "color3"]}}
    ],
    "decoration_ideas": ["idea1", "idea2", "idea3"],
    "menu_suggestions": ["item1", "item2", "item3"],
    "entertainment": ["entertainment1", "entertainment2"],
    "budget_saving_tips": ["tip1", "tip2", "tip3"]
  }},
  "budget_breakdown": [
    {{
      "category": "Category name",
      "description": "What this covers",
      "estimated_amount": 50000,
      "percentage": 25.0,
      "notes": "Cost-saving tips or notes",
      "priority": "essential|important|optional"
    }}
  ]
}}

Event Details:
- Event Name: {event_name}
- Event Type: {event_type}
- Location: {location}
- Event Date: {event_date}
- Guest Count: {guest_count}
- Total Budget (INR): {budget}
- Theme: {theme}
- Preferences: {preferences}
- Additional Details: {description}

Make the plan specific to this event type. Budget allocations must sum to approximately the total budget.
Never assign the same percentage split to every event - adapt to event type and context."""

CHAT_PROMPT = """You are helping plan the following event. Answer the user's question helpfully.
If they ask to modify the plan, provide specific actionable suggestions.

Event: {event_name} ({event_type})
Location: {location}
Date: {event_date}
Guests: {guest_count}
Budget: ₹{budget}
Theme: {theme}

Previous conversation context is provided. Stay focused on event planning."""


def _get_client():
    """Get Gemini client, raise clear error if key missing."""
    api_key = os.getenv('GEMINI_API_KEY', '')
    if not api_key or api_key == 'your_gemini_api_key_here':
        raise ValueError(
            "GEMINI_API_KEY is not configured. Please add your API key to the .env file."
        )
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        raise ImportError("google-genai package is not installed. Run: pip install google-genai")


def _get_model_name() -> str:
    """Return model name from environment or standard default."""
    return os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')


def generate_event_plan(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a full structured event plan using Gemini AI.
    Returns parsed dict. Raises on failure.
    """
    client = _get_client()
    model = _get_model_name()

    prompt = EVENT_PLAN_PROMPT.format(
        event_name=event.get('name', 'My Event'),
        event_type=event.get('event_type', 'Custom Event'),
        location=event.get('location', 'Not specified'),
        event_date=event.get('event_date', 'Date TBD'),
        guest_count=event.get('guest_count', 'Not specified'),
        budget=f"{event.get('budget', 0):,.0f}" if event.get('budget') else 'Not specified',
        theme=event.get('theme', 'No specific theme'),
        preferences=event.get('preferences', 'No specific preferences'),
        description=event.get('description', 'No additional details'),
    )

    full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"

    try:
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
        )
        raw_text = response.text.strip()

        # Robustly strip markdown code fences
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw_text)
        if match:
            raw_text = match.group(1).strip()
        else:
            raw_text = re.sub(r'^```[a-zA-Z]*\n?', '', raw_text).rstrip('`').strip()

        parsed = json.loads(raw_text)
        _validate_plan(parsed)
        return parsed

    except json.JSONDecodeError as e:
        logger.error(f"AI returned invalid JSON: {e}")
        raise ValueError(f"AI returned invalid JSON response: {e}")
    except Exception as e:
        error_msg = str(e)
        if 'quota' in error_msg.lower() or '429' in error_msg:
            raise RuntimeError("Gemini API quota exceeded. Please try again later.")
        elif 'timeout' in error_msg.lower():
            raise RuntimeError("AI request timed out. Please try again.")
        elif 'api_key' in error_msg.lower() or '401' in error_msg or '403' in error_msg:
            raise ValueError("Invalid or unauthorized Gemini API key.")
        else:
            logger.error(f"Gemini API error: {e}")
            raise RuntimeError(f"AI service error: {error_msg}")


def chat_with_assistant(event: Dict[str, Any], conversation_history: List[Dict[str, Any]], user_message: str) -> str:
    """
    Send a message to the AI assistant with full conversation context.
    Returns the assistant's text response.
    """
    client = _get_client()
    model = _get_model_name()

    # Build context prompt
    context = CHAT_PROMPT.format(
        event_name=event.get('name', 'My Event'),
        event_type=event.get('event_type', 'Custom Event'),
        location=event.get('location', 'Not specified'),
        event_date=event.get('event_date', 'Date TBD'),
        guest_count=event.get('guest_count', 'Not specified'),
        budget=f"{event.get('budget', 0):,.0f}" if event.get('budget') else 'Not specified',
        theme=event.get('theme', 'No specific theme'),
    )

    # Build conversation string
    history_text = ""
    for msg in conversation_history[-10:]:  # Keep last 10 messages for context
        role = "User" if msg.get('role') == 'user' else "EventGenie"
        history_text += f"\n{role}: {msg.get('content', '')}"

    full_prompt = (
        f"{SYSTEM_PROMPT}\n\n{context}"
        + (f"\n\nConversation so far:{history_text}" if history_text else "")
        + f"\n\nUser: {user_message}\nEventGenie:"
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=full_prompt,
        )
        return response.text.strip()
    except Exception as e:
        error_msg = str(e)
        if 'quota' in error_msg.lower() or '429' in error_msg:
            raise RuntimeError("Gemini API quota exceeded. Please try again later.")
        elif 'timeout' in error_msg.lower():
            raise RuntimeError("AI request timed out. Please try again.")
        elif 'api_key' in error_msg.lower() or '401' in error_msg or '403' in error_msg:
            raise ValueError("Invalid or unauthorized Gemini API key.")
        else:
            logger.error(f"Gemini chat error: {e}")
            raise RuntimeError(f"AI service error: {error_msg}")


def _validate_plan(plan: Dict[str, Any]) -> None:
    """Basic validation of the AI-generated plan structure."""
    required_keys = ['overview', 'preparation_timeline', 'budget_breakdown']
    for key in required_keys:
        if key not in plan:
            raise ValueError(f"AI response missing required section: '{key}'")

    if not isinstance(plan.get('budget_breakdown'), list):
        raise ValueError("budget_breakdown must be a list")

    if not isinstance(plan.get('preparation_timeline'), list):
        raise ValueError("preparation_timeline must be a list")
