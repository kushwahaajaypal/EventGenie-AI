"""
EventGenie AI - Event API Routes
"""
import json
import logging
from datetime import datetime, date

from flask import Blueprint, jsonify, request

from extensions import db
from models import Event, EventPlan, BudgetItem, Task, ChatMessage
import ai_service
from services.budget_service import parse_ai_budget_items, check_budget_overrun, calculate_budget_totals

logger = logging.getLogger(__name__)
events_bp = Blueprint('events', __name__, url_prefix='/api/events')


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _json_error(message, status=400):
    return jsonify({'success': False, 'error': message}), status


def _json_ok(data=None, message=None, status=200):
    resp = {'success': True}
    if data is not None:
        resp['data'] = data
    if message:
        resp['message'] = message
    return jsonify(resp), status


# ─── Create Event ─────────────────────────────────────────────────────────────

@events_bp.route('', methods=['POST'])
def create_event():
    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    name = (body.get('name') or '').strip()
    event_type = (body.get('event_type') or '').strip()
    if not name:
        return _json_error('Event name is required')
    if not event_type:
        return _json_error('Event type is required')

    valid_types = {'wedding', 'birthday', 'college', 'community', 'custom'}
    if event_type.lower() not in valid_types:
        return _json_error(f"event_type must be one of: {', '.join(valid_types)}")

    budget = body.get('budget')
    if budget is not None:
        try:
            budget = float(budget)
            if budget < 0:
                return _json_error('Budget cannot be negative')
        except (TypeError, ValueError):
            return _json_error('Budget must be a number')

    guest_count = body.get('guest_count')
    if guest_count is not None:
        try:
            guest_count = int(guest_count)
            if guest_count < 0:
                return _json_error('Guest count cannot be negative')
        except (TypeError, ValueError):
            return _json_error('Guest count must be an integer')

    event = Event(
        name=name,
        event_type=event_type.lower(),
        location=(body.get('location') or '').strip() or None,
        event_date=_parse_date(body.get('event_date')),
        guest_count=guest_count,
        budget=budget,
        theme=(body.get('theme') or '').strip() or None,
        preferences=(body.get('preferences') or '').strip() or None,
        description=(body.get('description') or '').strip() or None,
        status='planning',
    )
    db.session.add(event)
    db.session.commit()
    return _json_ok(event.to_dict(), 'Event created successfully', 201)


# ─── List Events ──────────────────────────────────────────────────────────────

@events_bp.route('', methods=['GET'])
def list_events():
    events = Event.query.order_by(Event.created_at.desc()).all()
    return _json_ok([e.to_dict() for e in events])


# ─── Get Event ────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)
    data = event.to_dict()

    # Include latest plans
    plans = EventPlan.query.filter_by(event_id=event_id).order_by(EventPlan.created_at.desc()).all()
    data['plans'] = [p.to_dict() for p in plans]
    return _json_ok(data)


# ─── Update Event ─────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    updatable = ['name', 'location', 'theme', 'preferences', 'description', 'status']
    for field in updatable:
        if field in body:
            setattr(event, field, (body[field] or '').strip() or None)

    if 'event_type' in body:
        et = (body['event_type'] or '').strip().lower()
        valid_types = {'wedding', 'birthday', 'college', 'community', 'custom'}
        if et not in valid_types:
            return _json_error(f"event_type must be one of: {', '.join(valid_types)}")
        event.event_type = et

    if 'event_date' in body:
        event.event_date = _parse_date(body['event_date'])

    if 'budget' in body:
        try:
            event.budget = float(body['budget']) if body['budget'] is not None else None
        except (TypeError, ValueError):
            return _json_error('Budget must be a number')

    if 'guest_count' in body:
        try:
            event.guest_count = int(body['guest_count']) if body['guest_count'] is not None else None
        except (TypeError, ValueError):
            return _json_error('Guest count must be an integer')

    event.updated_at = datetime.utcnow()
    db.session.commit()
    return _json_ok(event.to_dict(), 'Event updated successfully')


# ─── Delete Event ─────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)
    db.session.delete(event)
    db.session.commit()
    return _json_ok(message='Event deleted successfully')


# ─── Generate Plan ────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/generate-plan', methods=['POST'])
def generate_plan(event_id):
    event = Event.query.get(event_id)
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
        # Remove old AI-generated items (keep user-edited ones)
        BudgetItem.query.filter_by(event_id=event_id).delete()
        parsed_items = parse_ai_budget_items(plan_data['budget_breakdown'], event.budget)
        for item in parsed_items:
            bi = BudgetItem(event_id=event_id, **item)
            db.session.add(bi)

    # Save tasks from preparation_timeline
    if 'preparation_timeline' in plan_data:
        # Clear previously AI-generated tasks
        Task.query.filter_by(event_id=event_id).delete()
        for phase in plan_data['preparation_timeline']:
            weeks_before = phase.get('weeks_before', 0)
            for task_data in phase.get('tasks', []):
                due_date = None
                if event.event_date and weeks_before:
                    from datetime import timedelta
                    due_date = event.event_date - timedelta(weeks=int(weeks_before))

                task = Task(
                    event_id=event_id,
                    title=task_data.get('title', 'Task'),
                    description=task_data.get('description', ''),
                    category=task_data.get('category', 'general'),
                    priority=task_data.get('priority', 'medium'),
                    status='pending',
                    due_date=due_date,
                    relative_deadline=phase.get('phase', ''),
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
def chat(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    user_message = (body.get('message') or '').strip()
    if not user_message:
        return _json_error('Message is required')
    if len(user_message) > 2000:
        return _json_error('Message is too long (max 2000 characters)')

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
def get_budget(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)

    items = BudgetItem.query.filter_by(event_id=event_id).all()
    items_data = [i.to_dict() for i in items]
    summary = check_budget_overrun(items_data, event.budget or 0)
    return _json_ok({'items': items_data, 'summary': summary, 'total_budget': event.budget})


@events_bp.route('/<int:event_id>/budget', methods=['PUT'])
def update_budget(event_id):
    event = Event.query.get(event_id)
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
                        item.amount = float(item_data['amount'])
                    except (TypeError, ValueError):
                        return _json_error(f"Invalid amount for item {item_id}")
                if 'category' in item_data:
                    item.category = str(item_data['category']).strip()
                if 'notes' in item_data:
                    item.notes = str(item_data.get('notes', ''))
                if 'is_confirmed' in item_data:
                    item.is_confirmed = bool(item_data['is_confirmed'])
                item.updated_at = datetime.utcnow()

    # Handle new items
    for item_data in items_data:
        if not item_data.get('id'):
            try:
                amount = float(item_data.get('amount', 0))
            except (TypeError, ValueError):
                amount = 0
            new_item = BudgetItem(
                event_id=event_id,
                category=str(item_data.get('category', 'Miscellaneous')).strip(),
                description=str(item_data.get('description', '')),
                estimated_amount=amount,
                amount=amount,
                notes=str(item_data.get('notes', '')),
                is_confirmed=bool(item_data.get('is_confirmed', False)),
            )
            db.session.add(new_item)

    db.session.commit()
    items = BudgetItem.query.filter_by(event_id=event_id).all()
    items_data = [i.to_dict() for i in items]
    summary = check_budget_overrun(items_data, event.budget or 0)
    return _json_ok({'items': items_data, 'summary': summary}, 'Budget updated')


# ─── Tasks ────────────────────────────────────────────────────────────────────

@events_bp.route('/<int:event_id>/tasks', methods=['GET'])
def get_tasks(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)

    tasks = Task.query.filter_by(event_id=event_id).order_by(Task.due_date.asc()).all()
    return _json_ok([t.to_dict() for t in tasks])


@events_bp.route('/<int:event_id>/tasks', methods=['POST'])
def create_task(event_id):
    event = Event.query.get(event_id)
    if not event:
        return _json_error('Event not found', 404)

    body = request.get_json(silent=True)
    if not body:
        return _json_error('Request body must be JSON')

    title = (body.get('title') or '').strip()
    if not title:
        return _json_error('Task title is required')

    valid_priorities = {'low', 'medium', 'high', 'urgent'}
    priority = (body.get('priority') or 'medium').lower()
    if priority not in valid_priorities:
        priority = 'medium'

    task = Task(
        event_id=event_id,
        title=title,
        description=(body.get('description') or '').strip() or None,
        category=(body.get('category') or '').strip() or None,
        priority=priority,
        status='pending',
        due_date=_parse_date(body.get('due_date')),
        relative_deadline=(body.get('relative_deadline') or '').strip() or None,
    )
    db.session.add(task)
    db.session.commit()
    return _json_ok(task.to_dict(), 'Task created', 201)
