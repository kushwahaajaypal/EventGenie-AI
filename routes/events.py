"""
EventGenie AI - Event API Routes
Enterprise-grade REST endpoints with input sanitization, modern SQLAlchemy 2.0 API,
and strict type validation.
"""
import re
import json
import logging
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, Tuple

from flask import Blueprint, jsonify, request, Response

from extensions import db
from models import Event, EventPlan, BudgetItem, Task, ChatMessage
import ai_service
from services.budget_service import parse_ai_budget_items, check_budget_overrun, calculate_budget_totals

logger = logging.getLogger(__name__)
events_bp = Blueprint('events', __name__, url_prefix='/api/events')


def _sanitize_text(val: Optional[str], max_len: int = 1000) -> Optional[str]:
    """Sanitize input string by trimming, removing dangerous control chars, and capping length."""
    if val is None:
        return None
    cleaned = str(val).strip()
    if not cleaned:
        return None
    # Strip HTML tags to prevent stored XSS
    cleaned = re.sub(r'<[^>]*?>', '', cleaned)
    # Strip null bytes and non-printable control characters
    cleaned = ''.join(c for c in cleaned if c.isprintable() or c in '\n\r\t')
    return cleaned[:max_len]


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Safely parse date from multiple accepted formats."""
    if not date_str:
        return None
    clean_str = str(date_str).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(clean_str, fmt).date()
        except ValueError:
            continue
    return None


def _json_error(message: str, status: int = 400) -> Tuple[Response, int]:
    """Helper to return consistent JSON error response."""
    return jsonify({'success': False, 'error': message}), status


def _json_ok(data: Any = None, message: Optional[str] = None, status: int = 200) -> Tuple[Response, int]:
    """Helper to return consistent JSON success response."""
    resp: Dict[str, Any] = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


# ─── Create Event ─────────────────────────────────────────────────────────────

@events_bp.route('', methods=['POST'])
def create_event():
    """Create a new event with input validation and sanitization."""
    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    name = _sanitize_text(body.get('name'), 200)
    raw_type = body.get('event_type')
    event_type = _sanitize_text(raw_type, 100)
    if not name:
        return _json_error('Event name is required')
    if not event_type:
        return _json_error('Event type is required')

    valid_types = {'wedding', 'birthday', 'college', 'community', 'custom'}
    if event_type.lower() not in valid_types:
        return _json_error(f"event_type must be one of: {', '.join(sorted(valid_types))}")

    budget = body.get('budget')
    if budget is not None and str(budget).strip() != '':
        try:
            budget = float(budget)
            if budget < 0:
                return _json_error('Budget cannot be negative')
            if budget > 1_000_000_000:
                return _json_error('Budget exceeds maximum allowable limit (₹100 Crore)')
        except (TypeError, ValueError):
            return _json_error('Budget must be a number')
    else:
        budget = None

    guest_count = body.get('guest_count')
    if guest_count is not None and str(guest_count).strip() != '':
        try:
            guest_count = int(guest_count)
            if guest_count < 0:
                return _json_error('Guest count cannot be negative')
            if guest_count > 1_000_000:
                return _json_error('Guest count exceeds maximum allowable limit (1,000,000)')
        except (TypeError, ValueError):
            return _json_error('Guest count must be an integer')
    else:
        guest_count = None

    event = Event(
        name=name,
        event_type=event_type.lower(),
        location=_sanitize_text(body.get('location'), 300),
        event_date=_parse_date(body.get('event_date')),
        guest_count=guest_count,
        budget=budget,
        theme=_sanitize_text(body.get('theme'), 200),
        preferences=_sanitize_text(body.get('preferences'), 3000),
        description=_sanitize_text(body.get('description'), 5000),
        status='planning',
    )
    db.session.add(event)
    db.session.commit()
    return _json_ok(event.to_dict(), 'Event created successfully', 201)


# ─── List Events ──────────────────────────────────────────────────────────────

@events_bp.route('', methods=['GET'])
def list_events():
    """List all events ordered by creation date descending."""
    events = Event.query.order_by(Event.created_at.desc()).all()
    return _json_ok([e.to_dict() for e in events])


# ─── Get Event ────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id: int):
    """Retrieve an event by ID including its associated plan sections."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)
    data = event.to_dict()

    # Include latest plans
    plans = EventPlan.query.filter_by(event_id=event_id).order_by(EventPlan.created_at.desc()).all()
    data['plans'] = [p.to_dict() for p in plans]
    return _json_ok(data)


# ─── Update Event ─────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['PUT'])
def update_event(event_id: int):
    """Update event fields with validation."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    field_caps = {
        'name': 200,
        'location': 300,
        'theme': 200,
        'preferences': 3000,
        'description': 5000,
        'status': 50
    }
    for field, max_len in field_caps.items():
        if field in body:
            setattr(event, field, _sanitize_text(body[field], max_len))

    if 'event_type' in body:
        et = _sanitize_text(body['event_type'], 100)
        valid_types = {'wedding', 'birthday', 'college', 'community', 'custom'}
        if et and et.lower() not in valid_types:
            return _json_error(f"event_type must be one of: {', '.join(sorted(valid_types))}")
        if et:
            event.event_type = et.lower()

    if 'event_date' in body:
        event.event_date = _parse_date(body['event_date'])

    if 'budget' in body:
        val = body['budget']
        if val is None or str(val).strip() == '':
            event.budget = None
        else:
            try:
                b = float(val)
                if b < 0:
                    return _json_error('Budget cannot be negative')
                event.budget = b
            except (TypeError, ValueError):
                return _json_error('Budget must be a number')

    if 'guest_count' in body:
        val = body['guest_count']
        if val is None or str(val).strip() == '':
            event.guest_count = None
        else:
            try:
                g = int(val)
                if g < 0:
                    return _json_error('Guest count cannot be negative')
                event.guest_count = g
            except (TypeError, ValueError):
                return _json_error('Guest count must be an integer')

    event.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return _json_ok(event.to_dict(), 'Event updated successfully')


# ─── Delete Event ─────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['DELETE'])
def delete_event(event_id: int):
    """Delete an event and cascade-remove all child tasks, budget items, and plans."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)
    db.session.delete(event)
    db.session.commit()
    return _json_ok(message='Event deleted successfully')


# ─── Export Event Plan ────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/export', methods=['GET'])
def export_event(event_id: int):
    """Export complete event data including plans, budget, and tasks as structured JSON."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    plans = EventPlan.query.filter_by(event_id=event_id).all()
    budget_items = BudgetItem.query.filter_by(event_id=event_id).all()
    tasks = Task.query.filter_by(event_id=event_id).order_by(Task.due_date.asc()).all()

    export_payload = {
        'event': event.to_dict(),
        'plans': {p.plan_type: p.to_dict()['content'] for p in plans},
        'budget': {
            'items': [b.to_dict() for b in budget_items],
            'summary': check_budget_overrun([b.to_dict() for b in budget_items], event.budget or 0)
        },
        'tasks': [t.to_dict() for t in tasks],
        'exported_at': datetime.now(timezone.utc).isoformat()
    }
    return _json_ok(export_payload, 'Event exported successfully')


# ─── Generate Plan ────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/generate-plan', methods=['POST'])
def generate_plan(event_id: int):
    """Trigger AI event plan generation and populate budget & task checklists."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    try:
        plan_data = ai_service.generate_event_plan(event.to_dict())
    except ValueError as e:
        return _json_error(str(e), 400)
    except RuntimeError as e:
        return _json_error(str(e), 503)
    except Exception as e:
        logger.error(f"Unexpected error generating plan: {e}")
        return _json_error('Failed to generate plan. Please try again.', 500)

    # Save plan sections
    for plan_type in ['overview', 'preparation_timeline', 'event_day_schedule',
                      'vendor_checklist', 'ideas']:
        if plan_type in plan_data:
            existing = EventPlan.query.filter_by(event_id=event_id, plan_type=plan_type).first()
            content_json = json.dumps(plan_data[plan_type])
            if existing:
                existing.content = content_json
                existing.version += 1
            else:
                ep = EventPlan(
                    event_id=event_id,
                    plan_type=plan_type,
                    title=f"{plan_type.replace('_', ' ').title()}",
                    content=content_json,
                )
                db.session.add(ep)

    # Save budget items
    if 'budget_breakdown' in plan_data and event.budget:
        BudgetItem.query.filter_by(event_id=event_id).delete()
        parsed_items = parse_ai_budget_items(plan_data['budget_breakdown'], event.budget)
        for item in parsed_items:
            bi = BudgetItem(event_id=event_id, **item)
            db.session.add(bi)

    # Save tasks from preparation_timeline
    if 'preparation_timeline' in plan_data:
        Task.query.filter_by(event_id=event_id).delete()
        for phase in plan_data['preparation_timeline']:
            weeks_before = phase.get('weeks_before', 0)
            for task_data in phase.get('tasks', []):
                due_date = None
                if event.event_date and weeks_before:
                    from datetime import timedelta
                    try:
                        due_date = event.event_date - timedelta(weeks=int(weeks_before))
                    except (ValueError, TypeError):
                        due_date = None

                task = Task(
                    event_id=event_id,
                    title=_sanitize_text(task_data.get('title', 'Task'), 300) or 'Task',
                    description=_sanitize_text(task_data.get('description', ''), 2000),
                    category=_sanitize_text(task_data.get('category', 'general'), 100),
                    priority=task_data.get('priority', 'medium').lower() if task_data.get('priority') in ('low', 'medium', 'high', 'urgent') else 'medium',
                    status='pending',
                    due_date=due_date,
                    relative_deadline=_sanitize_text(phase.get('phase', ''), 200),
                )
                db.session.add(task)

    db.session.commit()

    # Return full event data with plan
    result = event.to_dict()
    result['plan'] = plan_data
    result['budget_summary'] = check_budget_overrun(
        [b.to_dict() for b in event.budget_items],
        event.budget or 0
    )
    return _json_ok(result, 'Event plan generated successfully')


# ─── Chat ─────────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/chat', methods=['POST'])
def chat(event_id: int):
    """Chat with the Gemini AI event planner assistant with full context."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    user_message = _sanitize_text(body.get('message'), 2000)
    if not user_message:
        return _json_error('Message is required')

    # Save user message
    user_msg = ChatMessage(event_id=event_id, role='user', content=user_message)
    db.session.add(user_msg)
    db.session.flush()

    # Get conversation history
    history = ChatMessage.query.filter_by(event_id=event_id).order_by(
        ChatMessage.created_at.asc()
    ).all()
    history_dicts = [m.to_dict() for m in history[:-1]]  # exclude just-added message

    try:
        assistant_text = ai_service.chat_with_assistant(
            event.to_dict(), history_dicts, user_message
        )
    except ValueError as e:
        db.session.rollback()
        return _json_error(str(e), 400)
    except RuntimeError as e:
        db.session.rollback()
        return _json_error(str(e), 503)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Chat error: {e}")
        return _json_error('AI assistant is unavailable. Please try again.', 500)

    # Save assistant response
    ai_msg = ChatMessage(event_id=event_id, role='assistant', content=assistant_text)
    db.session.add(ai_msg)
    db.session.commit()

    return _json_ok({
        'message': assistant_text,
        'user_message': user_message,
        'message_id': ai_msg.id,
    })


# ─── Budget ───────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/budget', methods=['GET'])
def get_budget(event_id: int):
    """Get all budget items and overrun summary for an event."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    items = BudgetItem.query.filter_by(event_id=event_id).all()
    items_data = [i.to_dict() for i in items]
    summary = check_budget_overrun(items_data, event.budget or 0)
    return _json_ok({'items': items_data, 'summary': summary, 'total_budget': event.budget})


@events_bp.route('/<int:event_id>/budget', methods=['PUT'])
def update_budget(event_id: int):
    """Batch update or add budget items with live arithmetic recalculation."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    items_data = body.get('items', [])
    if not isinstance(items_data, list):
        return _json_error('items must be a list')

    # Update each existing item
    for item_data in items_data:
        item_id = item_data.get('id')
        if item_id:
            item = BudgetItem.query.filter_by(id=item_id, event_id=event_id).first()
            if item:
                if 'amount' in item_data:
                    try:
                        amt = float(item_data['amount'])
                        if amt < 0:
                            return _json_error('Budget item amount cannot be negative')
                        item.amount = amt
                    except (TypeError, ValueError):
                        return _json_error(f"Invalid amount for item {item_id}")
                if 'category' in item_data:
                    item.category = _sanitize_text(item_data['category'], 200) or 'Miscellaneous'
                if 'notes' in item_data:
                    item.notes = _sanitize_text(item_data.get('notes', ''), 1000)
                if 'is_confirmed' in item_data:
                    item.is_confirmed = bool(item_data['is_confirmed'])
                item.updated_at = datetime.now(timezone.utc)

    # Handle new items
    for item_data in items_data:
        if not item_data.get('id'):
            try:
                amount = float(item_data.get('amount', 0))
                if amount < 0:
                    amount = 0.0
            except (TypeError, ValueError):
                amount = 0.0
            new_item = BudgetItem(
                event_id=event_id,
                category=_sanitize_text(item_data.get('category'), 200) or 'Miscellaneous',
                description=_sanitize_text(item_data.get('description', ''), 500),
                estimated_amount=amount,
                amount=amount,
                notes=_sanitize_text(item_data.get('notes', ''), 1000),
                is_confirmed=bool(item_data.get('is_confirmed', False)),
            )
            db.session.add(new_item)

    db.session.commit()
    items = BudgetItem.query.filter_by(event_id=event_id).all()
    items_data = [i.to_dict() for i in items]
    summary = check_budget_overrun(items_data, event.budget or 0)
    return _json_ok({'items': items_data, 'summary': summary}, 'Budget updated')


@events_bp.route('/<int:event_id>/budget/<int:item_id>', methods=['DELETE'])
def delete_budget_item(event_id: int, item_id: int):
    """Delete a single budget item."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    item = BudgetItem.query.filter_by(id=item_id, event_id=event_id).first()
    if not item:
        return _json_error('Budget item not found', 404)

    db.session.delete(item)
    db.session.commit()

    items = BudgetItem.query.filter_by(event_id=event_id).all()
    items_data = [i.to_dict() for i in items]
    summary = check_budget_overrun(items_data, event.budget or 0)
    return _json_ok({'items': items_data, 'summary': summary}, 'Budget item removed')


# ─── Tasks ────────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/tasks', methods=['GET'])
def get_tasks(event_id: int):
    """Get all tasks for an event ordered by due date."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    tasks = Task.query.filter_by(event_id=event_id).order_by(Task.due_date.asc()).all()
    return _json_ok([t.to_dict() for t in tasks])


@events_bp.route('/<int:event_id>/tasks', methods=['POST'])
def create_task(event_id: int):
    """Add a new task to an event with validation."""
    event = db.session.get(Event, event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    title = _sanitize_text(body.get('title'), 300)
    if not title:
        return _json_error('Task title is required')

    valid_priorities = {'low', 'medium', 'high', 'urgent'}
    priority = (body.get('priority') or 'medium').lower()
    if priority not in valid_priorities:
        priority = 'medium'

    task = Task(
        event_id=event_id,
        title=title,
        description=_sanitize_text(body.get('description'), 2000),
        category=_sanitize_text(body.get('category'), 100),
        priority=priority,
        status='pending',
        due_date=_parse_date(body.get('due_date')),
        relative_deadline=_sanitize_text(body.get('relative_deadline'), 200),
    )
    db.session.add(task)
    db.session.commit()
    return _json_ok(task.to_dict(), 'Task created', 201)
